import json
import re
from pathlib import Path

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ValidationError

from .. import config, inference, progress
from ..content_profile import ContentProfile
from ..prompts import format_content_prompt
from ..utils import parse_with_repair
from . import _source_docs


BUILD_PHASES = (("extract", "Extrayendo ítems de los documentos", 100),)


class ExemplarsBankBuilder:
    ID_RE = re.compile(r"^C(\d+)$")

    def __init__(
        self,
        content_profile: ContentProfile,
        verbose: bool = True,
    ):
        self.content_profile = content_profile
        self.item_model = content_profile.content_item
        self.context = content_profile.content_context

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.chunk_size = config.EXEMPLARS_BANK_CHUNK_SIZE

        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._docling = _source_docs.default_converter()
        self._schema_str = json.dumps(content_profile.stripped_schema(), indent=2, ensure_ascii=False)
        self._extraction_guidance_block = "\n".join(
            f"- `{name}`: {text}" for name, text in content_profile.field_guidance("extraction").items()
        )
        self._id_counter = 0

    # PUBLIC API ----------------------------------------------------------------------------------

    # build() persiste checkpoints en disco y además devuelve el banco, para que el
    # llamador pueda usarlo sin releerlo (el loader ExemplarsBank sigue siendo la vía de carga).
    def build(self, input_dir: str, output_file_path: str) -> dict[str, dict]:
        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        bank = self._load_existing(output_file_path)
        self._id_counter = self._max_id(bank)
        logger.info(f"Found {len(files)} file(s) - Starting from C{self._id_counter + 1:03d}")

        progress.phase("extract", f"0/{len(files)} documento(s)")
        with progress.step("extract", "Extrayendo ítems de los documentos", len(files)) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                tag = f"[{idx}/{len(files)} {file_path.name}]"
                reporter.tick(idx, detail=file_path.name)
                progress.advance(
                    (idx - 1) / len(files),
                    f"{file_path.name} ({idx}/{len(files)}) · {len(bank)} ítem(s)",
                )
                try:
                    new_items = self._process_file(file_path, tag=tag)
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"{tag} skipped: {e}")
                    continue

                if not new_items:
                    logger.warning(f"{tag} produced 0 items")
                    continue

                bank.update(new_items)
                _source_docs.save_json(bank, output_file_path)
                logger.success(f"{tag} +{len(new_items)} → checkpoint saved ({len(bank)} total)")
                progress.emit("artifact.progress", name="exemplars_bank", count=len(bank))

        progress.advance(1.0, f"{len(bank)} ítem(s)")
        logger.success(f"Directory done — {len(bank)} item(s) in {output_file_path}")
        return bank

    # PIPELINE ------------------------------------------------------------------------------------

    def _process_file(self, file_path: Path, tag: str) -> dict[str, dict]:
        with progress.step("convert", f"Convirtiendo {file_path.name} a markdown"):
            content = _source_docs.to_markdown(self._docling, file_path)
        logger.info(f"{tag} markdown ready ({len(content):,} chars)")

        batches = self._build_batches(content)
        if not batches:
            return {}
        logger.info(f"{tag} split into {len(batches)} batch(es)")

        items: dict[str, dict] = {}
        with progress.step(
            "extract_batches", f"{file_path.name}: extrayendo lotes", len(batches)
        ) as reporter:
            for b_idx, batch in enumerate(batches, 1):
                progress.checkpoint()
                b_tag = f"{tag} batch {b_idx}/{len(batches)}"
                reporter.tick(b_idx)
                try:
                    extracted = self._extract_batch(batch, b_tag)
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.error(f"{b_tag} failed: {e}")
                    continue
                for raw in extracted:
                    items[self._next_id()] = {**raw, "source": file_path.stem}
                logger.info(f"{b_tag} extracted {len(extracted)} item(s)")
        return items

    def _extract_batch(self, batch: str, tag: str) -> list[dict]:
        prompt = format_content_prompt(
            content=batch,
            schema=self._schema_str,
            context=self.context,
            field_guidance_block=self._extraction_guidance_block,
        )
        response = inference.generate(
            model=config.CONTENT_FORMATTING_LLM, think=False, prompt=prompt
        ).response

        items, err = parse_with_repair(
            response,
            self._parse_and_validate,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="array",
            log_prefix=f"{tag} ",
        )

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
        blocks = _source_docs.split_blocks(content)
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

    # HELPERS -------------------------------------------------------------------------------------

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

