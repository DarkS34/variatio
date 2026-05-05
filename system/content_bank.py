import hashlib
import json
import re
from pathlib import Path

from docling.document_converter import DocumentConverter, InputFormat
import ollama
from loguru import logger
from pydantic import BaseModel, ValidationError

from system import config
from system.prompts import (
    clean_content as _clean_content_prompt,
    format_content as _format_content_prompt,
    json_repair as _json_repair_prompt,
)



class ContentBank:
    CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
    SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")

    def __init__(
        self,
        item_model,
        content_cleaning_model: str,
        content_formatting_model: str,
        context_name: str = "",
        verbose: bool = True,
        max_repair_attempts: int = 3,
    ):
        self.content_cleaning_model = content_cleaning_model
        self.content_formatting_model = content_formatting_model
        self.context_name = context_name
        self.item_model = item_model
        self.max_repair_attempts = max_repair_attempts
        self.chunk_size = config.MAX_CHUNK_SIZE
        self.content_kwarg = "content"
        self.schema_kwarg = "schema"

        self._docling = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX])
        self._schema_str = json.dumps(item_model.model_json_schema(), indent=2, ensure_ascii=False)

        logger.enable(__name__) if verbose else logger.disable(__name__)

    # MAIN METHODS --------------------------------------------------------------------------------

    def format_file(self, input_file_path: str, output_file_path: str) -> dict[str, dict]:
        try:
            input_path = Path(input_file_path)
            logger.info(f"Processing file: {input_path.name}")
            source = input_path.stem
            content = self._to_markdown(input_path)
            items = self._extract_from_content(content, source=source)

            self._save_dict(items, output_file_path)
            return items

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
            all_items: dict[str, dict] = {}
            for file_idx, file_path in enumerate(files, 1):
                logger.info(f"[{file_idx}/{len(files)}] Processing file: {file_path.name}")

                try:
                    content = self._to_markdown(file_path)
                    logger.info(f"Converted {file_path.name}: {len(content):,} chars")
                    items = self._extract_from_content(content, source=file_path.stem)
                    before = len(all_items)
                    for item_id, item in items.items():
                        all_items.setdefault(item_id, item)
                    added = len(all_items) - before
                    logger.info(
                        f"[{file_idx}/{len(files)}] {file_path.name}: "
                        f"added {added} new, skipped {len(items) - added} duplicate(s)"
                    )
                except Exception as e:
                    logger.exception(f"Skipping {file_path.name}: {e}")

            logger.success(f"Directory scan complete: {len(all_items)} unique item(s) collected")
            self._save_dict(all_items, output_file_path)
            return all_items
        except Exception as e:
            logger.exception(f"Error processing directory: {e}")
            return {}

    # TO MARKDOWN ---------------------------------------------------------------------------------

    def _to_markdown(self, input_path: Path) -> str:
        suffix = input_path.suffix.lower()
        try:
            if suffix in (".md", ".txt"):
                return input_path.read_text(encoding="utf-8")
            result = self._docling.convert(str(input_path))
            return result.document.export_to_markdown()
        except Exception:
            raise ValueError(f"Unsupported file extension: {suffix}")

    # EXTRACTION AND FORMATTING FLOW --------------------------------------------------------------

    def _extract_from_content(self, content: str, source: str) -> dict[str, dict]:
        content = self._clean_content(content)
        batches = self._build_batches(content)
        logger.info(f"Document split into {len(batches)} batch(es)")

        if not batches:
            logger.warning(f"No item batches produced for '{source}'")
            return {}

        all_items: dict[str, dict] = {}
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"Batch {batch_idx}/{len(batches)} ({len(batch):,} chars) — invoking LLM")
            try:
                extracted = self._extract_batch(batch, source)
            except Exception as e:
                logger.error(f"Batch {batch_idx} failed after retries: {e}")
                continue

            new_count = 0
            for item in extracted:
                item_id = item.pop("id")
                if item_id not in all_items:
                    new_count += 1
                all_items.setdefault(item_id, item)
            logger.info(
                f"Batch {batch_idx}/{len(batches)}: extracted {len(extracted)} "
                f"({new_count} new, {len(extracted) - new_count} duplicate)"
            )

        logger.success(f"Extracted {len(all_items)} item(s) from {source}")
        return all_items

    def _build_batches(self, content: str) -> list[str]:
        items = self._split_items_protecting_code(content)
        if not items:
            return []

        oversized = sum(1 for it in items if len(it) > self.chunk_size)
        if oversized:
            logger.warning(
                f"{oversized} item(s) exceed chunk_size={self.chunk_size}; sent as solo batches"
            )

        batches, current, size = [], [], 0
        for it in items:
            it_size = len(it)
            if it_size > self.chunk_size:
                if current:
                    batches.append("\n\n---\n\n".join(current))
                    current, size = [], 0
                batches.append(it)
                continue
            if size + it_size > self.chunk_size and current:
                batches.append("\n\n---\n\n".join(current))
                current, size = [it], it_size
            else:
                current.append(it)
                size += it_size + 10
        if current:
            batches.append("\n\n---\n\n".join(current))
        return batches

    def _split_items_protecting_code(self, text: str) -> list[str]:
        fences = []

        def _stash(m):
            fences.append(m.group(0))
            return f"§§FENCE{len(fences) - 1}§§"

        masked = self.CODE_FENCE_RE.sub(_stash, text)

        starts = [m.start() for m in self.item_start_re.finditer(masked)]
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
            prompt = _clean_content_prompt(content=content, context=self.context_name)
            response = ollama.generate(
                model=self.content_cleaning_model, prompt=prompt
            ).response.strip()
            return re.sub(r"\n{3,}", "\n\n", response)
        except Exception as e:
            logger.warning(f"Cleaning failed, returning raw content: {e}")
            return content

    def _extract_batch(self, batch: str, source: str) -> list[dict]:
        prompt = _format_content_prompt(
             content=batch, schema=self._schema_str, context=self.context_name
        )
        response = ollama.generate(model=self.content_formatting_model, prompt=prompt).response
        items, err = self._parse_and_validate(response)

        for attempt in range(self.max_repair_attempts):
            if items is not None:
                break
            logger.warning(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")
            repair_prompt = _json_repair_prompt(
                broken_output=response, error_msg=err or "invalid JSON"
            )
            response = ollama.generate(
                model=self.content_formatting_model, prompt=repair_prompt
            ).response
            items, err = self._parse_and_validate(response)
            if items is not None:
                logger.info(f"Repair attempt {attempt + 1} succeeded")

        if items is None:
            raise ValueError(f"Failed to extract valid JSON after repairs: {err}")

        return [
            {
                **item.model_dump(),
                "source": source,
                "id": self._make_id(item),
            }
            for item in items
        ]

    def _parse_and_validate(self, response: str) -> tuple[list[BaseModel] | None, str | None]:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = json.loads(cleaned)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                return None, "top-level JSON is neither object nor array"
            return [self.item_model(**item) for item in raw], None
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
            logger.error(f"Parse/validation error: {err}")
            return None, err

    # OTHER STUFF ---------------------------------------------------------------------------------

    def _make_id(self, item: BaseModel) -> str:
        if callable(self.id_from):
            seed = self.id_from(item)
        else:
            seed = getattr(item, self.id_from, None)
            if seed is None:
                raise ValueError(
                    f"Cannot generate id: field '{self.id_from}' is missing or None on item"
                )
            seed = str(seed)
        return self._deterministic_id(seed)

    @staticmethod
    def _deterministic_id(seed: str) -> str:
        norm = re.sub(r"\s+", " ", seed.strip().lower())
        return hashlib.sha1(norm.encode()).hexdigest()[:8]

    @staticmethod
    def _restore_fences(text: str, fences: list[str]) -> str:
        return re.sub(r"§§FENCE(\d+)§§", lambda m: fences[int(m.group(1))], text)

    @staticmethod
    def _save_dict(result: dict, output_file_path: str) -> bool:
        try:
            output_path = Path(output_file_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.success(f"Saved {len(result)} item(s) to {output_path}")
            return True
        except Exception as e:
            logger.exception(f"Error saving: {e}")
            return False

    @staticmethod
    def load_content_bank(path: str):
        with open(path, encoding="utf-8") as f:
            content_bank = json.load(f)
        logger.info("Content bank loaded correctly")
        return content_bank
