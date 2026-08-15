import json
import re
from pathlib import Path

from json_repair import repair_json
from loguru import logger
from pydantic import ValidationError

from .. import config, inference, progress
from ..exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile
from ..prompts import format_content_prompt
from ..utils import ensure_models, parse_with_repair
from . import _source_docs


# Transcribing a PDF is one model call per page, so conversion is no longer the rounding
# error it was when Docling did it in three seconds.
BUILD_PHASES = (
    ("convert", "Transcribiendo los documentos", 40),
    ("extract", "Extrayendo ítems de los documentos", 60),
)


class ExemplarsBankBuilder:
    ID_RE = re.compile(r"^C(\d+)$")

    def __init__(
        self,
        exemplars_profile: ExemplarsProfile,
        verbose: bool = True,
    ):
        self.exemplars_profile = exemplars_profile
        self.context = exemplars_profile.content_context

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.chunk_size = config.EB_CHUNK_SIZE

        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._docling = _source_docs.default_converter(ocr=config.EXEMPLARS_OCR)
        self._type_keys = exemplars_profile.type_keys
        self._types_block = self._build_types_block(exemplars_profile)
        self._extraction_schema = self._build_extraction_schema(exemplars_profile)
        self._id_counter = 0

    # One branch per modality, so the decoder cannot hand back an item wearing the fields of
    # another one — the failure `_parse_and_validate` exists to catch loudly. `item_type` is
    # a `const` per branch and is only demanded when there is a choice to make: with a single
    # modality the parser already fills it in, and requiring it would add a way to fail for
    # nothing. Extraction is the one pass that legitimately answers with an empty array, and
    # the schema allows that.
    @staticmethod
    def _build_extraction_schema(exemplars_profile: ExemplarsProfile) -> dict:
        branches = []
        several = len(exemplars_profile.item_types) > 1
        for key, item_type in exemplars_profile.item_types.items():
            schema = item_type.stripped_schema()
            properties = {**schema.get("properties", {}), ITEM_TYPE_KEY: {"const": key}}
            required = list(schema.get("required", []))
            if several:
                required.append(ITEM_TYPE_KEY)
            branches.append({**schema, "properties": properties, "required": required})
        items = branches[0] if len(branches) == 1 else {"anyOf": branches}
        return {"type": "array", "items": items}

    @staticmethod
    def _build_types_block(exemplars_profile: ExemplarsProfile) -> str:
        blocks = []
        for key, item_type in exemplars_profile.item_types.items():
            lines = [f"### `{key}` — {item_type.label}"]
            if item_type.description:
                lines.append(item_type.description)
            lines.append("Schema de un ítem de esta modalidad:")
            lines.append(item_type.schema_str())
            guidance = item_type.field_guidance("extraction")
            if guidance:
                lines.append("Guía de extracción por campo — síguela literalmente:")
                lines.extend(f"- `{name}`: {text}" for name, text in guidance.items())
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    # PUBLIC API ----------------------------------------------------------------------------------

    def bootstrap(self) -> None:
        ensure_models(
            [config.EXEMPLARS_TRANSCRIBE_MODEL, config.EB_EXTRACT_MODEL, config.REPAIR_LLM],
            "exemplars bank",
        )

    # build() persiste checkpoints en disco y además devuelve el banco, para que el
    # llamador pueda usarlo sin releerlo (el loader ExemplarsBank sigue siendo la vía de carga).
    def build(self, input_dir: str, output_file_path: str) -> dict[str, dict]:
        self.bootstrap()

        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported files found in: {input_dir}")
            return {}

        bank = self._load_existing(output_file_path)
        self._id_counter = self._max_id(bank)
        logger.info(f"Found {len(files)} file(s) - Starting from C{self._id_counter + 1:03d}")

        pages_by_file = self._convert(files)

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
                    new_items = self._process_file(
                        file_path, pages_by_file.get(file_path, []), tag=tag
                    )
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

    # Pages are the unit of transcription and of the on-disk cache; batching stays a
    # matter of size, over the whole document, so an exercise that straddles a page break
    # is not cut in half before the extractor ever sees it.
    def _convert(self, files: list[Path]) -> dict[Path, list[str]]:
        progress.phase("convert", f"0/{len(files)} documento(s)")
        pages_by_file: dict[Path, list[str]] = {}
        with progress.step(
            "convert", "Transcribiendo los documentos", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=file_path.name)
                progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
                try:
                    pages_by_file[file_path] = _source_docs.document_pages(
                        file_path,
                        converter=self._docling,
                        ocr=config.EXEMPLARS_OCR,
                        tag=f"[{idx}/{len(files)}] ",
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{file_path.name}] conversion skipped: {e}")
        progress.advance(1.0, f"{sum(len(p) for p in pages_by_file.values())} página(s)")
        return pages_by_file

    def _process_file(self, file_path: Path, pages: list[str], tag: str) -> dict[str, dict]:
        content = _source_docs.join_pages(pages)
        if not content.strip():
            logger.warning(f"{tag} no usable content after transcription")
            return {}
        logger.info(f"{tag} markdown ready ({len(content):,} chars, {len(pages)} page(s))")

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
            types_block=self._types_block,
            context=self.context,
            type_keys=self._type_keys,
        )
        response = inference.generate(
            model=config.EB_EXTRACT_MODEL,
            think=False,
            prompt=prompt,
            format=self._extraction_schema,
        ).response

        items, err = parse_with_repair(
            response,
            self._parse_and_validate,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="array",
            format=self._extraction_schema,
            log_prefix=f"{tag} ",
        )

        if items is None:
            raise ValueError(f"unrecoverable JSON after {self.max_repair_attempts} repairs: {err}")
        return items

    # Each raw object is validated against the schema of the modality it declares, so a
    # mislabelled item fails loudly here instead of reaching the bank with the fields of
    # another modality. A single type in the profile makes `item_type` optional: there is
    # nothing to choose, and demanding it would only add a way for the model to fail.
    def _parse_and_validate(self, response: str) -> tuple[list[dict] | None, str | None]:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = repair_json(cleaned, return_objects=True)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list):
                return None, "top-level JSON is neither object nor array"

            items: list[dict] = []
            for entry in raw:
                if not isinstance(entry, dict):
                    return None, f"array element is not an object: {type(entry).__name__}"
                key = entry.get(ITEM_TYPE_KEY) or (
                    self.exemplars_profile.default_type
                    if len(self._type_keys) == 1
                    else None
                )
                if key is None:
                    return None, f"item is missing '{ITEM_TYPE_KEY}' (one of {self._type_keys})"
                item_type = self.exemplars_profile.item_type(str(key))
                fields = {k: v for k, v in entry.items() if k != ITEM_TYPE_KEY}
                validated = item_type.content_item(**fields).model_dump()
                items.append({ITEM_TYPE_KEY: item_type.key, **validated})
            return items, None
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

