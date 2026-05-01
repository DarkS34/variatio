import hashlib
import json
import logging
import re
import warnings
from pathlib import Path
from typing import ClassVar

from docling.document_converter import DocumentConverter, InputFormat
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import OllamaLLM
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, field_validator

from ggleg.utils import load_prompt

for _name in ("docling", "docling_core", "docling_ibm_models", "PIL"):
    logging.getLogger(_name).setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module=r"docling.*")
warnings.filterwarnings("ignore", module=r"PIL.*")


class ExtractedExercise(BaseModel):
    statement: str = Field(min_length=10)
    solution: str | None = None

    LEADING_ENUM_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*(?:\d+\s*[.)\-:]\s*|(?:Ejercicio|Exercise|Problem|Problema)\s*\d+\s*[.)\-:]?\s*)",
        re.IGNORECASE,
    )

    @field_validator("statement")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return cls.LEADING_ENUM_RE.sub("", v.strip()).strip()


class ExerciseFormatter:
    EXERCISE_START_RE = re.compile(
        r"^(?:\d+[.)]\s+|(?:Ejercicio|Exercise|Problem|Problema)\s*\d+[:.)\s])",
        re.MULTILINE | re.IGNORECASE,
    )
    CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
    SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")

    def __init__(self, llm: OllamaLLM, chunk_size: int = 2_000, max_repair_attempts: int = 1, verbose: bool = True):
        self.llm = llm
        self.parser = JsonOutputParser()
        self.chunk_size = chunk_size
        self.max_repair_attempts = max_repair_attempts
        self._docling = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX])

        logger.enable(__name__) if verbose else logger.disable(__name__)

    def _to_markdown(self, input_path: Path) -> str:
        suffix = input_path.suffix.lower()

        try:
            if suffix in (".md", ".txt"):
                return input_path.read_text(encoding="utf-8")
            
            result = self._docling.convert(str(input_path))
            return result.document.export_to_markdown()
        except Exception as _:
            raise ValueError(f"Unsupported file extension: {suffix}")

    def format_file(self, input_file_path: str, output_file_path: str) -> dict[str, dict]:
        try:
            input_path = Path(input_file_path)
            logger.info(f"Processing file: {input_path.name}")
            notebook = input_path.stem
            content = self._to_markdown(input_path)
            exercises = self._extract_from_content(content, notebook=notebook)

            self._save_dict(exercises, output_file_path)
            return exercises

        except Exception as e:
            logger.exception(f"Error processing file {input_file_path}: {e}")
            return {}

    def format_dir(self, input_dir: str, output_file_path: str) -> dict[str, dict]:
        try:
            input_path = Path(input_dir)
            files = sorted(
                p
                for p in input_path.iterdir()
                if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
            )

            if not files:
                logger.error(f"No supported files found in: {input_dir}")
                return {}

            logger.info(f"Found {len(files)} file(s) to process")
            all_exercises: dict[str, dict] = {}
            for file_idx, file_path in enumerate(files, 1):
                logger.info(
                    f"[{file_idx}/{len(files)}] Processing file: {file_path.name}"
                )
                
                try:
                    content = self._to_markdown(file_path)
                    logger.info(f"Converted {file_path.name}: {len(content):,} chars")
                    exercises = self._extract_from_content(content, notebook=file_path.stem)
                    before = len(all_exercises)
                    for ex_id, ex in exercises.items():
                        all_exercises.setdefault(ex_id, ex)
                    added = len(all_exercises) - before
                    logger.info(
                        f"[{file_idx}/{len(files)}] {file_path.name}: "
                        f"added {added} new, skipped {len(exercises) - added} duplicate(s)"
                    )
                except Exception as e:
                    logger.exception(f"Skipping {file_path.name}: {e}")

            logger.success(
                f"Directory scan complete: {len(all_exercises)} unique exercise(s) collected"
            )
            self._save_dict(all_exercises, output_file_path)
            return all_exercises
        except Exception as e:
            logger.exception(f"Error processing directory: {e}")
            return {}

    def _extract_from_content(self, content: str, notebook: str) -> dict[str, dict]:
        # cleaned = self._clean_content(content)
        # logger.info(f"Cleaned content: {len(cleaned):,} chars (was {len(content):,})")
        batches = self._build_batches(content)
        logger.info(f"Document split into {len(batches)} batch(es)")

        if not batches:
            logger.warning(f"No exercise batches produced for '{notebook}'")
            return {}

        all_exercises: dict[str, dict] = {}
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(
                f"Batch {batch_idx}/{len(batches)} ({len(batch):,} chars) — invoking LLM"
            )
            try:
                extracted = self._extract_batch(batch, notebook)
            except Exception as e:
                logger.error(f"Batch {batch_idx} failed after retries: {e}")
                continue

            new_count = 0
            for ex in extracted:
                ex_id = ex.pop("id")
                if ex_id not in all_exercises:
                    new_count += 1
                all_exercises.setdefault(ex_id, ex)
            logger.info(
                f"Batch {batch_idx}/{len(batches)}: extracted {len(extracted)} "
                f"({new_count} new, {len(extracted) - new_count} duplicate)"
            )

        logger.success(f"Extracted {len(all_exercises)} exercise(s) from {notebook}")
        return all_exercises

    def _build_batches(self, content: str) -> list[str]:
        exercises = self._split_exercises_protecting_code(content)
        if not exercises:
            return []

        oversized = sum(1 for ex in exercises if len(ex) > self.chunk_size)
        if oversized:
            logger.warning(
                f"{oversized} exercise(s) exceed chunk_size={self.chunk_size}; sent as solo batches"
            )

        batches, current, size = [], [], 0
        for ex in exercises:
            ex_size = len(ex)
            if ex_size > self.chunk_size:
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
        fences = []

        def _stash(m):
            fences.append(m.group(0))
            return f"§§FENCE{len(fences) - 1}§§"

        masked = self.CODE_FENCE_RE.sub(_stash, text)

        starts = [m.start() for m in self.EXERCISE_START_RE.finditer(masked)]
        if len(starts) <= 1:
            restored = self._restore_fences(masked, fences).strip()
            return [restored] if restored else []

        pieces_masked = []
        for i, s in enumerate(starts):
            e = starts[i + 1] if i + 1 < len(starts) else len(masked)
            pieces_masked.append(masked[s:e])

        pieces = [self._restore_fences(p, fences).strip() for p in pieces_masked]
        return [p for p in pieces if p]

    def _clean_content(self, content: str) -> str:
        if len(content.strip()) < 300:
            return content
        try:
            logger.info(f"Cleaning content via LLM ({len(content):,} chars)")
            prompt = load_prompt("data_prep/content_cleaner", raw_content=content)
            response = self.llm.invoke(prompt).strip()
            return re.sub(r"\n{3,}", "\n\n", response)
        except Exception as e:
            logger.warning(f"Cleaning failed, returning raw content: {e}")
            return content

    def _extract_batch(self, batch: str, notebook: str) -> list[dict]:
        prompt = load_prompt(
            "data_prep/exercise_formatter",
            exercises_content=batch,
        )
        response = self.llm.invoke(prompt)
        exercises = self._parse_and_validate(response)

        for attempt in range(self.max_repair_attempts):
            if exercises is not None:
                break
            logger.warning(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")
            repair_prompt = load_prompt(
                "data_prep/json_repair",
                broken_output=response,
                error_msg="invalid JSON or schema",
            )
            response = self.llm.invoke(repair_prompt)
            exercises = self._parse_and_validate(response)
            if exercises is not None:
                logger.info(f"Repair attempt {attempt + 1} succeeded")

        if exercises is None:
            raise ValueError("Failed to extract valid JSON after repairs")

        return [
            {
                **ex.model_dump(),
                "notebook": notebook,
                "id": self._deterministic_id(ex.statement),
            }
            for ex in exercises
        ]

    def _parse_and_validate(self, response: str) -> list[ExtractedExercise] | None:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = self.parser.parse(cleaned)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                return None
            return [ExtractedExercise(**item) for item in raw]
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            logger.error(f"Parse/validation error: {e[:20]}")
            return None

    @staticmethod
    def _restore_fences(text: str, fences: list[str]) -> str:
        return re.sub(r"§§FENCE(\d+)§§",lambda m: fences[int(m.group(1))],text)

    @staticmethod
    def _deterministic_id(statement: str) -> str:
        norm = re.sub(r"\s+", " ", statement.strip().lower())
        return hashlib.sha1(norm.encode()).hexdigest()[:8]

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
