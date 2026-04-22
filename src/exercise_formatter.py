import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import OllamaLLM
from loguru import logger
from markitdown import MarkItDown
from pydantic import BaseModel, Field, ValidationError, field_validator

from src.workflow_prompts import (
    get_content_cleaner_prompt,
    get_exercise_formatter_prompt,
    get_json_repair_prompt,
)


# -----------------------------------------------------------------------------
# Esquema de validación
# -----------------------------------------------------------------------------

class ExtractedExercise(BaseModel):
    statement: str = Field(min_length=10)
    starter_code: str | None = None
    solutions: list[str] = Field(default_factory=list)
    difficulty: Literal[1, 2, 3, 4]
    difficulty_justification: str = Field(min_length=5, max_length=300)

    @field_validator("statement", "difficulty_justification")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


# -----------------------------------------------------------------------------
# Formatter
# -----------------------------------------------------------------------------

class ExerciseFormatter:

    # Umbral por encima del cual no se limpia el documento completo de golpe
    # sino sección por sección. Ajusta según la ventana de contexto del LLM.
    FULL_CLEAN_MAX_CHARS = 12_000

    # Regex que detecta cabeceras H1 de markdown. Las secciones se usan como
    # hint de dificultad para el LLM.
    SECTION_HEADER_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

    # Detecta inicio de ejercicio: línea con "1.", "1)", "Ejercicio 3:", etc.
    # No dispara dentro de bloques de código gracias al pre-mascarado.
    EXERCISE_START_RE = re.compile(
        r"^(?:\d+[.)]\s+|(?:Ejercicio|Exercise|Problem|Problema)\s*\d+[:.)\s])",
        re.MULTILINE | re.IGNORECASE,
    )

    # Bloques de código que debemos proteger del splitter
    CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

    def __init__(
        self,
        model: str = "gemma4:e4b-it-q4_K_M",
        chunk_size: int = 2_000,
        max_repair_attempts: int = 1,
    ):
        self.markitdown = MarkItDown()
        self.llm = OllamaLLM(model=model)
        self.parser = JsonOutputParser()
        self.chunk_size = chunk_size
        self.max_repair_attempts = max_repair_attempts

    # -------------------------------------------------------------------------
    # API pública
    # -------------------------------------------------------------------------

    def format_file(self, input_file_path: str, output_file_path: str) -> bool:
        try:
            input_path = Path(input_file_path)
            logger.info(f"Processing file: {input_path.name}")
            notebook = input_path.stem
            content = self.markitdown.convert(str(input_path)).markdown
            exercises = self._extract_from_content(content, notebook=notebook)
            return self._save(exercises, output_file_path)
        except Exception as e:
            logger.exception(f"Error processing file {input_file_path}: {e}")
            return False

    def format_dir(self, input_dir: str, output_file_path: str) -> bool:
        try:
            input_path = Path(input_dir)
            files = sorted(
                p for ext in ("*.pdf", "*.docx", "*.txt", "*.md")
                for p in input_path.glob(ext)
            )
            if not files:
                logger.error(f"No supported files found in: {input_dir}")
                return False

            all_exercises = {}
            for file_path in files:
                logger.info(f"Processing file: {file_path.name}")
                try:
                    content = self.markitdown.convert(str(file_path)).markdown
                    exercises = self._extract_from_content(
                        content, notebook=file_path.stem,
                    )
                    for ex in exercises:
                        # Las colisiones son esperables si hay ejercicios
                        # duplicados entre cuadernos; nos quedamos con el
                        # primero para que sea idempotente.
                        all_exercises.setdefault(ex["id"], ex)
                except Exception as e:
                    logger.exception(f"Skipping {file_path.name}: {e}")

            return self._save_dict(all_exercises, output_file_path)
        except Exception as e:
            logger.exception(f"Error processing directory: {e}")
            return False

    # -------------------------------------------------------------------------
    # Pipeline central
    # -------------------------------------------------------------------------

    def _extract_from_content(
        self, content: str, notebook: str,
    ) -> list[dict]:
        sections = self._split_into_sections(content)
        logger.info(f"Document split into {len(sections)} section(s)")

        # Cleaning: documento completo si cabe, si no, por sección.
        if len(content) <= self.FULL_CLEAN_MAX_CHARS:
            logger.info("Cleaning full document in one LLM call")
            cleaned_full = self._clean_content(content)
            sections = self._split_into_sections(cleaned_full)
        else:
            logger.info("Document too large; cleaning per-section")
            sections = [
                (name, self._clean_content(body)) for name, body in sections
            ]

        all_exercises: list[dict] = []
        for section_name, section_body in sections:
            batches = self._build_batches(section_body)
            logger.info(
                f"Section {section_name!r}: {len(batches)} batch(es)"
            )
            for batch_idx, batch in enumerate(batches, 1):
                logger.debug(f"  Batch {batch_idx}/{len(batches)}")
                try:
                    extracted = self._extract_batch(batch, section_name)
                except Exception as e:
                    logger.error(
                        f"  Batch {batch_idx} failed after retries: {e}"
                    )
                    continue

                for ex in extracted:
                    ex_dict = ex.model_dump()
                    ex_dict["notebook"] = notebook
                    ex_dict["section"] = section_name
                    ex_dict["id"] = self._deterministic_id(
                        notebook, ex.statement,
                    )
                    all_exercises.append(ex_dict)

        logger.success(
            f"Extracted {len(all_exercises)} exercise(s) from {notebook}"
        )
        return all_exercises

    # -------------------------------------------------------------------------
    # Secciones y batches
    # -------------------------------------------------------------------------

    def _split_into_sections(self, content: str) -> list[tuple[str, str]]:
        """
        Divide el documento por cabeceras H1. Devuelve [(section_name, body), ...].
        Si no hay cabeceras, devuelve una única sección con name=None.
        """
        matches = list(self.SECTION_HEADER_RE.finditer(content))
        if not matches:
            return [(None, content.strip())]

        sections = []
        # Contenido antes de la primera cabecera, si lo hay
        if matches[0].start() > 0:
            prefix = content[: matches[0].start()].strip()
            if prefix:
                sections.append((None, prefix))

        for i, m in enumerate(matches):
            name = m.group(1).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            if body:
                sections.append((name, body))

        return sections

    def _build_batches(self, section_body: str) -> list[str]:
        """
        Dentro de una sección, parte por ejercicios y agrupa por tamaño.
        Enmascara bloques de código para que el regex no dispare en comentarios.
        """
        exercises = self._split_exercises_protecting_code(section_body)
        if not exercises:
            return []

        batches, current, size = [], [], 0
        for ex in exercises:
            ex_size = len(ex)
            if ex_size > self.chunk_size:
                # Un solo ejercicio excede el chunk: va solo.
                if current:
                    batches.append("\n\n---\n\n".join(current))
                    current, size = [], 0
                batches.append(ex)
                continue
            if size + ex_size > self.chunk_size and current:
                batches.append("\n\n---\n\n".join(current))
                current, size = [ex], ex_size
            else:
                current.append(ex)
                size += ex_size + 10
        if current:
            batches.append("\n\n---\n\n".join(current))
        return batches

    def _split_exercises_protecting_code(self, text: str) -> list[str]:
        # 1. Extrae fences de código con un placeholder para no splitear dentro
        fences = []
        def _stash(m):
            fences.append(m.group(0))
            return f"§§FENCE{len(fences) - 1}§§"
        masked = self.CODE_FENCE_RE.sub(_stash, text)

        # 2. Encuentra inicios de ejercicio en el texto enmascarado
        starts = [m.start() for m in self.EXERCISE_START_RE.finditer(masked)]
        if len(starts) <= 1:
            restored = self._restore_fences(masked, fences).strip()
            return [restored] if restored else []

        # 3. Trocea por esos offsets
        pieces_masked = []
        for i, s in enumerate(starts):
            e = starts[i + 1] if i + 1 < len(starts) else len(masked)
            pieces_masked.append(masked[s:e])

        # 4. Restaura los fences
        pieces = [self._restore_fences(p, fences).strip() for p in pieces_masked]
        return [p for p in pieces if p]

    @staticmethod
    def _restore_fences(text: str, fences: list[str]) -> str:
        return re.sub(
            r"§§FENCE(\d+)§§",
            lambda m: fences[int(m.group(1))],
            text,
        )

    # -------------------------------------------------------------------------
    # Llamadas al LLM
    # -------------------------------------------------------------------------

    def _clean_content(self, content: str) -> str:
        if len(content.strip()) < 300:
            return content
        try:
            prompt = get_content_cleaner_prompt(content)
            response = self.llm.invoke(prompt).strip()
            # Colapsa múltiples líneas vacías por si el modelo las deja
            return re.sub(r"\n{3,}", "\n\n", response)
        except Exception as e:
            logger.warning(f"Cleaning failed, returning raw content: {e}")
            return content

    def _extract_batch(
        self, batch: str, section_hint: str | None,
    ) -> list[ExtractedExercise]:
        prompt = get_exercise_formatter_prompt(batch, section_hint)
        response = self.llm.invoke(prompt)
        exercises = self._parse_and_validate(response)

        for attempt in range(self.max_repair_attempts):
            if exercises is not None:
                return exercises
            logger.warning(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")
            repair_prompt = get_json_repair_prompt(
                response, error_msg="invalid JSON or schema",
            )
            response = self.llm.invoke(repair_prompt)
            exercises = self._parse_and_validate(response)

        if exercises is None:
            raise ValueError("Failed to extract valid JSON after repairs")
        return exercises

    def _parse_and_validate(
        self, response: str,
    ) -> list[ExtractedExercise] | None:
        try:
            # Quita fences por si el modelo los añade pese a las instrucciones
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = self.parser.parse(cleaned)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                return None
            return [ExtractedExercise(**item) for item in raw]
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            logger.debug(f"Parse/validation error: {e}")
            return None

    # -------------------------------------------------------------------------
    # IDs y persistencia
    # -------------------------------------------------------------------------

    @staticmethod
    def _deterministic_id(notebook: str, statement: str) -> str:
        """
        ID estable entre ejecuciones. Idempotente: re-procesar el mismo
        cuaderno no cambia los IDs, así que los `history` de los perfiles
        no se rompen.
        """
        norm = re.sub(r"\s+", " ", statement.strip().lower())
        digest = hashlib.sha1(f"{notebook}::{norm}".encode()).hexdigest()[:8]
        return f"{notebook}-{digest}"

    def _save(self, exercises: list[dict], output_file_path: str) -> bool:
        result = {ex.pop("id"): ex for ex in exercises}
        return self._save_dict(result, output_file_path)

    @staticmethod
    def _save_dict(result: dict, output_file_path: str) -> bool:
        try:
            output_path = Path(output_file_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.success(f"Saved {len(result)} exercise(s) to {output_path}")
            return True
        except Exception as e:
            logger.exception(f"Error saving: {e}")
            return False