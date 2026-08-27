import json
import re
from collections.abc import Callable
from pathlib import Path

from json_repair import repair_json
from loguru import logger
from pydantic import ValidationError

from .. import config
from ..core import inference, progress
from ..core.inference import ensure_models
from ..core.json_io import write_json
from ..core.lexicon import fold
from ..core.repair import parse_with_repair
from ..core.workspace import Workspace
from ..instance import locale
from ..instance.content_context import ContentContext
from .. import prompts as prompts_pkg
from ..instance.exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile
from . import _source_docs


# Transcribing a PDF is one model call per page plus one short one per seam, so conversion
# is no longer the rounding error it was when Docling did it in three seconds.
#
# `extract` now costs more than before because it does not only extract: each document is
# tagged as soon as it comes out, inside the same phase, so an item appears with its
# concepts already instead of waiting for a second job that had to be launched by hand.
# The weights are still an estimate, as the two before them were.
BUILD_PHASES = (
    ("convert", "Transcribiendo los documentos", 30),
    ("extract", "Extrayendo y etiquetando los ítems", 70),
)


def build_models() -> list[str]:
    return [
        config.TRANSCRIBE_MODEL,
        config.TRANSCRIBE_SEAM_MODEL,
        config.EB_EXTRACT_MODEL,
        config.EMBEDDING_LLM,
        config.CONCEPT_TAGGER_LLM,
        config.REPAIR_LLM,
    ]


class ExemplarsBankBuilder:
    ID_RE = re.compile(r"^C(\d+)$")

    def __init__(
        self,
        exemplars_profile: ExemplarsProfile,
        workspace: Workspace,
        content_context: ContentContext | None = None,
        verbose: bool = True,
    ):
        self.workspace = workspace
        # The workspace's own prompt set, resolved once here. Every model call this
        # builder makes goes through it, so a Spanish instance and an English one build
        # from the same code and never share a prompt.
        self.prompts = prompts_pkg.of(locale.prompt_language(workspace))
        self.exemplars_profile = exemplars_profile
        self.content_context = content_context or ContentContext()

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.chunk_size = config.EB_CHUNK_SIZE

        logger.enable(__name__) if verbose else logger.disable(__name__)

        # Only `.docx` ever reaches it: a PDF goes through the page-transcription route and
        # plain text needs no conversion, so on the usual corpus Docling is never built.
        self._docling = _source_docs.LazyConverter(ocr=config.EXEMPLARS_OCR)
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

    # The tagger and the embedder come in here because the build uses them: each document is
    # tagged right after extracting it, inside this same job.
    def bootstrap(self) -> None:
        ensure_models(build_models(), "del banco de ejemplares")

    # build() persists checkpoints to disk and also returns the bank, so the caller can use it
    # without re-reading it.
    #
    # `on_items(bank, new_ids)` is the hook tagging comes in through: it is called with the
    # whole bank right after writing a document's items and returns that same bank annotated.
    # The builder does not know what it does — it knows neither the graph nor the tagger —;
    # `stages/build.py` wires it, being the layer whose job is to orchestrate.
    def build(
        self,
        input_dir: str,
        output_file_path: str,
        on_items: Callable[[dict, list[str]], dict] | None = None,
    ) -> dict[str, dict]:
        self.bootstrap()

        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"Ningún documento admitido en {input_dir}")
            return {}

        bank = self._load_existing(output_file_path)
        self._id_counter = self._max_id(bank)
        logger.info(f"{len(files)} documento(s); se empieza en C{self._id_counter + 1:03d}")

        text_by_file = self._convert(files)

        progress.phase("extract", f"0/{len(files)} documento(s)")
        with progress.step(
            "extract", "Extrayendo y etiquetando los ítems", len(files)
        ) as reporter:
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
                        file_path, text_by_file.get(file_path, ""), tag=tag
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"{tag} omitido: {e}")
                    continue

                if not new_items:
                    logger.warning(f"{tag} no produjo ningún ítem")
                    continue

                bank.update(new_items)
                write_json(output_file_path, bank)
                logger.success(f"{tag} +{len(new_items)} ítem(s); {len(bank)} en total")
                progress.emit("artifact.progress", name="exemplars_bank", count=len(bank))

                if on_items is not None:
                    # Half a phase per document: extracting is the first half and tagging the second, so the
                    # bar moves within a document and not only when moving on to the next one.
                    progress.advance(
                        (idx - 0.5) / len(files),
                        f"{file_path.name} ({idx}/{len(files)}) · etiquetando "
                        f"{len(new_items)} ítem(s)",
                    )
                    try:
                        bank = on_items(bank, list(new_items))
                    except progress.Cancelled:
                        raise
                    except Exception as e:
                        logger.exception(f"{tag} no se pudo etiquetar: {e}")
                    else:
                        write_json(output_file_path, bank)
                        progress.emit(
                            "artifact.progress", name="exemplars_bank", count=len(bank)
                        )

        progress.advance(1.0, f"{len(bank)} ítem(s)")
        logger.success(f"Banco terminado: {len(bank)} ítem(s) en {Path(output_file_path).name}")
        return bank

    # PIPELINE ------------------------------------------------------------------------------------

    # Pages are the unit of transcription and of the on-disk cache; batching stays a
    # matter of size, over the whole document, so an exercise that straddles a page break
    # is not cut in half before the extractor ever sees it.
    def _convert(self, files: list[Path]) -> dict[Path, str]:
        progress.phase("convert", f"0/{len(files)} documento(s)")
        text_by_file: dict[Path, str] = {}
        with progress.step(
            "convert", "Transcribiendo los documentos", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=file_path.name)
                progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
                try:
                    text_by_file[file_path] = _source_docs.document_markdown(
                        file_path,
                        self.prompts,
                        converter=self._docling,
                        ocr=config.EXEMPLARS_OCR,
                        tag=f"[{idx}/{len(files)}] ",
                        cache_dir=self.workspace.markdown_cache_dir,
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{file_path.name}] conversión omitida: {e}")
        progress.advance(1.0, f"{len(text_by_file)} documento(s) transcrito(s)")
        return text_by_file

    def _process_file(self, file_path: Path, content: str, tag: str) -> dict[str, dict]:
        if not content.strip():
            logger.warning(f"{tag} sin contenido aprovechable tras la transcripción")
            return {}

        batches = self._build_batches(content)
        if not batches:
            return {}

        items: dict[str, dict] = {}
        seen: set[str] = set()
        repeated = 0
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
                    logger.error(f"{b_tag} falló: {e}")
                    continue
                for raw in extracted:
                    key = self._identity(raw)
                    # The id is claimed AFTER the duplicate check: a repeat that consumed
                    # one would leave a gap in the numbering for an item nobody kept.
                    if key and key in seen:
                        repeated += 1
                        continue
                    if key:
                        seen.add(key)
                    items[self._next_id()] = {**raw, "source": file_path.stem}
                logger.debug(f"{b_tag} extrajo {len(extracted)} ítem(s)")
        if repeated:
            logger.debug(f"{tag} {repeated} ítem(s) repetidos por el solape, descartados")
        return items

    # What makes two extractions the same item: the primary field, which is the one the
    # profile declares as carrying the statement. Compared folded, because the same
    # exercise read from two overlapping batches comes back with the same words and not
    # necessarily the same spacing.
    def _identity(self, raw: dict) -> str:
        key = raw.get(ITEM_TYPE_KEY) or self.exemplars_profile.default_type
        try:
            item_type = self.exemplars_profile.item_type(str(key))
            text = item_type.primary_text(raw)
        except (KeyError, ValueError):
            return ""
        return f"{item_type.key}::{fold(text).strip()}" if text.strip() else ""

    def _extract_batch(self, batch: str, tag: str) -> list[dict]:
        prompt = self.prompts.format_content_prompt(
            content=batch,
            types_block=self._types_block,
            context_block=self.content_context.prompt_block(),
            type_keys=self._type_keys,
        )
        response = inference.generate(
            model=config.EB_EXTRACT_MODEL,
            think=config.THINK_EB_EXTRACT,
            prompt=prompt,
            format=None if config.THINK_EB_EXTRACT else self._extraction_schema,
            temperature=inference.judgement_temperature(config.THINK_EB_EXTRACT),
        ).response

        items, err = parse_with_repair(
            response,
            self._parse_and_validate,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="array",
            format=self._extraction_schema,
            log_prefix=f"{tag} ",
            prompts=self.prompts,
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

    # Batches OVERLAP: the last `EB_BATCH_OVERLAP_BLOCKS` blocks of one open the next, so an
    # exercise that straddles the size cut is seen whole by at least one call instead of
    # half by each. The price is items extracted twice, and `_identity` is what pays it.
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
                current = self._carry_over(current)
                size = sum(len(b) + 10 for b in current)
                current.append(block)
                size += b_size + 10
            else:
                current.append(block)
                size += b_size + 10
        if current:
            batches.append("\n\n---\n\n".join(current))
        return batches

    # Only what leaves room: carrying a block that fills half the budget would push the very
    # next cut back into the same block and could stop the batches advancing at all.
    def _carry_over(self, blocks: list[str]) -> list[str]:
        count = min(config.EB_BATCH_OVERLAP_BLOCKS, len(blocks))
        carried: list[str] = []
        for block in reversed(blocks[len(blocks) - count :]):
            if sum(len(b) for b in carried) + len(block) > self.chunk_size // 2:
                break
            carried.insert(0, block)
        return carried

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
            logger.warning(f"No se pudo leer el banco existente {path} ({e}); se empieza de cero")
            return {}

