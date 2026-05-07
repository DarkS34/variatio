import json

import re
from pathlib import Path

from json_repair import repair_json
from docling.document_converter import DocumentConverter, InputFormat
import ollama
from loguru import logger
from pydantic import BaseModel, ValidationError

from system import config
from system.prompts import clean_content_prompt, format_content_prompt, json_repair_prompt


class ContentBank:
    SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")
    CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
    SEPARATOR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
    ID_RE = re.compile(r"^C(\d+)$")

    def __init__(
        self,
        item_model,
        context: str = "",
        verbose: bool = True,
    ):
        self.item_model = item_model
        self.context = context

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.chunk_size = config.MAX_CHUNK_SIZE

        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._docling = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX])
        self._schema_str = json.dumps(item_model.model_json_schema(), indent=2, ensure_ascii=False)
        self._id_counter = 0

        self.bank = (
            self.load_content_bank(config.CONTENT_BANK_PATH)
            if config.CONTENT_BANK_PATH.is_file()
            else None
        )

    # PUBLIC API ----------------------------------------------------------------------------------

    def format_file(self, input_file_path: str, output_file_path: str) -> dict[str, dict]:
        input_path = Path(input_file_path)
        try:
            bank = self._load_existing(output_file_path)
            self._id_counter = self._max_id(bank)

            new_items = self._process_file(input_path, tag=f"[{input_path.name}]")
            bank.update(new_items)
            self._save(bank, output_file_path)
            logger.success(f"[{input_path.name}] +{len(new_items)} item(s) → {output_file_path}")
            return bank
        except Exception as e:
            logger.exception(f"[{input_path.name}] failed: {e}")
            return {}

    def format_dir(self, input_dir: str, output_file_path: str) -> dict[str, dict]:
        input_path = Path(input_dir)
        files = sorted(
            p
            for p in input_path.iterdir()
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTS
        )
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        bank = self._load_existing(output_file_path)
        self._id_counter = self._max_id(bank)
        logger.info(f"Found {len(files)} file(s) - Starting from C{self._id_counter + 1:03d}")

        for idx, file_path in enumerate(files, 1):
            tag = f"[{idx}/{len(files)} {file_path.name}]"
            try:
                new_items = self._process_file(file_path, tag=tag)
            except Exception as e:
                logger.exception(f"{tag} skipped: {e}")
                continue

            if not new_items:
                logger.warning(f"{tag} produced 0 items")
                continue

            bank.update(new_items)
            self._save(bank, output_file_path)
            logger.success(f"{tag} +{len(new_items)} → checkpoint saved ({len(bank)} total)")

        logger.success(f"Directory done — {len(bank)} item(s) in {output_file_path}")
        
        self.bank = bank

    @staticmethod
    def load_content_bank(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            bank = json.load(f)
        logger.info(f"Content bank loaded ({len(bank)} item(s))")
        return bank

    # PIPELINE ------------------------------------------------------------------------------------

    def _process_file(self, file_path: Path, tag: str) -> dict[str, dict]:
        content = self._to_markdown(file_path)
        logger.info(f"{tag} markdown ready ({len(content):,} chars)")

        # content = self._clean_content(content, tag)
        batches = self._build_batches(content)
        if not batches:
            return {}
        logger.info(f"{tag} split into {len(batches)} batch(es)")

        items: dict[str, dict] = {}
        for b_idx, batch in enumerate(batches, 1):
            b_tag = f"{tag} batch {b_idx}/{len(batches)}"
            try:
                extracted = self._extract_batch(batch, b_tag)
            except Exception as e:
                logger.error(f"{b_tag} failed: {e}")
                continue
            for raw in extracted:
                items[self._next_id()] = {**raw, "source": file_path.stem}
            logger.info(f"{b_tag} extracted {len(extracted)} item(s)")
        return items

    def _clean_content(self, content: str, tag: str) -> str:
        if len(content.strip()) < 300:
            return content
        try:
            logger.info(f"{tag} cleaning content via LLM")
            prompt = clean_content_prompt(content=content, context=self.context)
            response = ollama.generate(
                model=config.CONTENT_CLEANING_LLM, prompt=prompt
            ).response.strip()

            return re.sub(r"\n{3,}", "\n\n", response)
        except Exception as e:
            logger.warning(f"{tag} cleaning failed, using raw content: {e}")
            return content

    def _extract_batch(self, batch: str, tag: str) -> list[dict]:
        prompt = format_content_prompt(content=batch, schema=self._schema_str, context=self.context)
        response = ollama.generate(
            model=config.CONTENT_FORMATTING_LLM, think=False, prompt=prompt
        ).response
        items, err = self._parse_and_validate(response)

        for attempt in range(1, self.max_repair_attempts + 1):
            if items is not None:
                break
            err_inline = " | ".join(err.splitlines()) if err else err
            logger.warning(f"{tag} repair {attempt}/{self.max_repair_attempts}: {err_inline}")

            repair_prompt = json_repair_prompt(
                broken_output=response, error_msg=err or "invalid JSON"
            )
            response = ollama.generate(model=config.REPAIR_LLM, prompt=repair_prompt).response
            items, err = self._parse_and_validate(response)

        if items is None:
            raise ValueError(f"unrecoverable JSON after {self.max_repair_attempts} repairs: {err}")
        return [item.model_dump() for item in items]

    def _parse_and_validate(self, response: str) -> tuple[list[BaseModel] | None, str | None]:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = repair_json(cleaned, return_objects=True)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                return None, "top-level JSON is neither object nor array"
            return [self.item_model(**item) for item in raw], None
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    # BATCHING ------------------------------------------------------------------------------------

    def _build_batches(self, content: str) -> list[str]:
        blocks = self._split_blocks(content)
        if not blocks:
            return []

        batches, current, size = [], [], 0
        for block in blocks:
            b_size = len(block)
            if b_size > self.chunk_size:
                if current:
                    batches.append("\n\n---\n\n".join(current))
                    current, size = [], 0
                batches.append(block)
                continue
            if size + b_size > self.chunk_size and current:
                batches.append("\n\n---\n\n".join(current))
                current, size = [block], b_size
            else:
                current.append(block)
                size += b_size + 10
        if current:
            batches.append("\n\n---\n\n".join(current))
        return batches

    def _split_blocks(self, text: str) -> list[str]:
        fences: list[str] = []

        def _stash(m):
            fences.append(m.group(0))
            return f"§§FENCE{len(fences) - 1}§§"

        masked = self.CODE_FENCE_RE.sub(_stash, text)
        pieces = (
            self.SEPARATOR_RE.split(masked)
            if self.SEPARATOR_RE.search(masked)
            else re.split(r"\n\s*\n", masked)
        )

        def _restore(p: str) -> str:
            return re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], p).strip()

        return [r for r in (_restore(p) for p in pieces) if r]

    # HELPERS -------------------------------------------------------------------------------------

    def _to_markdown(self, input_path: Path) -> str:
        suffix = input_path.suffix.lower()
        if suffix in (".md", ".txt"):
            return input_path.read_text(encoding="utf-8")
        if suffix in (".pdf", ".docx"):
            return self._docling.convert(str(input_path)).document.export_to_markdown()
        raise ValueError(f"Unsupported file extension: {suffix}")

    def _next_id(self) -> str:
        self._id_counter += 1
        return f"C{self._id_counter:03d}"

    @classmethod
    def _max_id(cls, bank: dict) -> int:
        return max(
            (int(m.group(1)) for k in bank if (m := cls.ID_RE.match(k))),
            default=0,
        )

    @staticmethod
    def _load_existing(path: str) -> dict:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Could not read existing {path} ({e}) — starting fresh")
            return {}

    @staticmethod
    def _save(bank: dict, output_file_path: str) -> None:
        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(bank, f, ensure_ascii=False, indent=2)
