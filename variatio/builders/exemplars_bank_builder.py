"""Building `exemplars_bank.json`: real items read out of the raw exemplars documents.

The bank is defined in terms of the exemplars profile — every item is validated against the
modality it declares — and each document is tagged as soon as it comes out, inside the same
job, so an item reaches the bank with its concepts already on it.
"""

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


# Shares of a whole build, and an estimate: transcribing a PDF is one model call per page
# plus a short one per seam, and `extract` also tags each document as it comes out.
BUILD_PHASES = (
    ("convert", "Transcribiendo los documentos", 30),
    ("extract", "Extrayendo y etiquetando los ítems", 70),
)


def build_models() -> list[str]:
    """Every model a bank build calls, the tagger's and the embedder's included."""
    return [
        config.TRANSCRIBE_MODEL,
        config.TRANSCRIBE_SEAM_MODEL,
        config.EB_EXTRACT_MODEL,
        config.EMBEDDING_LLM,
        config.CONCEPT_TAGGER_LLM,
        config.REPAIR_LLM,
    ]


class ExemplarsBankBuilder:
    """Reads the raw exemplars documents into the bank, one document at a time."""

    def __init__(
        self,
        exemplars_profile: ExemplarsProfile,
        workspace: Workspace,
        content_context: ContentContext | None = None,
        verbose: bool = True,
    ):
        """Resolve the workspace's prompt set and precompute the schema and prompt blocks."""
        self.workspace = workspace
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

    @staticmethod
    def _build_extraction_schema(exemplars_profile: ExemplarsProfile) -> dict:
        """One branch per modality, so the decoder cannot mix the fields of two of them.

        `item_type` is a `const` per branch and is only demanded when there is a choice to
        make: with a single modality the parser fills it in, and requiring it would add a way
        to fail for nothing. Extraction legitimately answers with an empty array, and the
        schema allows that.
        """
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
        """The prompt's catalogue of modalities: schema and per-field extraction guidance."""
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
        """Check every model of the build is installed, the tagger's and embedder's included."""
        ensure_models(build_models(), "exemplars bank")

    def build(
        self,
        input_dir: str,
        output_file_path: str,
        working_file_path: str | Path,
        on_items: Callable[[dict, list[str]], dict] | None = None,
    ) -> dict[str, dict]:
        """Read every document into a NEW bank and, once it is whole, put it in place.

        Every checkpoint goes to `working_file_path` and the artifact is written once, at the
        end. A build reads every document again, so anything already in the bank could only
        come back out of them a second time — checkpointing into the artifact itself is what
        piled one extraction on top of the previous one — and until this build finishes, what
        the workspace has is still the bank it had. Cancelling loses the run, tagging
        included, and keeps that bank.

        `on_items(bank, new_ids)` is the hook tagging comes in through: it is called with the
        whole bank right after a document's items are written and returns that same bank
        annotated. The builder knows neither the graph nor the tagger — `stages/build.py`
        wires it, being the layer whose job is to orchestrate.
        """
        self.bootstrap()

        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported document in {input_dir}")
            return {}

        working = Path(working_file_path)
        # Whatever a build that died left behind. The worker is killed five seconds after a
        # cancel, so its own cleanup is the exception and not the rule, and resuming from
        # half a bank would only extract every document over it again.
        working.unlink(missing_ok=True)

        bank: dict[str, dict] = {}
        self._id_counter = 0
        logger.info(f"{len(files)} document(s) to read")

        try:
            text_by_file = self._convert(files)

            progress.phase("extract", f"0/{len(files)} documento(s)")
            with progress.step(
                "extract", "Extrayendo y etiquetando los ítems", len(files)
            ) as reporter:
                for idx, file_path in enumerate(files, 1):
                    progress.checkpoint()
                    tag = f"[{idx}/{len(files)} {file_path.name}]"
                    reporter.start(idx, detail=file_path.name)
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
                        logger.exception(f"{tag} skipped: {e}")
                        continue

                    if not new_items:
                        logger.warning(f"{tag} produced no item")
                        continue

                    bank.update(new_items)
                    write_json(working, bank)
                    logger.success(f"{tag} +{len(new_items)} item(s); {len(bank)} in total")
                    progress.emit("artifact.progress", name="exemplars_bank", count=len(bank))

                    if on_items is not None:
                        # Half a phase per document — extracting the first half, tagging the
                        # second — so the bar moves within a document and not only between two.
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
                            logger.exception(f"{tag} could not be tagged: {e}")
                        else:
                            write_json(working, bank)
                            progress.emit(
                                "artifact.progress", name="exemplars_bank", count=len(bank)
                            )

            # An extraction that produced nothing may not replace what is there: `stages`
            # turns it into an error, and the bank the workspace already had is what its
            # screen goes back to.
            if bank:
                write_json(output_file_path, bank)
        finally:
            working.unlink(missing_ok=True)

        progress.advance(1.0, f"{len(bank)} ítem(s)")
        logger.success(f"Bank finished: {len(bank)} item(s) in {Path(output_file_path).name}")
        return bank

    # PIPELINE ------------------------------------------------------------------------------------

    def _convert(self, files: list[Path]) -> dict[Path, str]:
        """Transcribe every document to one markdown string.

        Pages are the unit of transcription and of the on-disk cache; batching stays a matter
        of size over the whole document, so an exercise straddling a page break is not cut in
        half before the extractor ever sees it.
        """
        progress.phase("convert", f"0/{len(files)} documento(s)")
        text_by_file: dict[Path, str] = {}
        with progress.step(
            "convert", "Transcribiendo los documentos", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.start(idx, detail=file_path.name)
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
                    logger.exception(f"[{file_path.name}] conversion skipped: {e}")
        progress.advance(1.0, f"{len(text_by_file)} documento(s) transcrito(s)")
        return text_by_file

    def _process_file(self, file_path: Path, content: str, tag: str) -> dict[str, dict]:
        """Extract one document's items batch by batch, dropping what the overlap repeats."""
        if not content.strip():
            logger.warning(f"{tag} no usable content after the transcription")
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
                reporter.start(b_idx)
                try:
                    extracted = self._extract_batch(batch, b_tag)
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.error(f"{b_tag} failed: {e}")
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
                logger.debug(f"{b_tag} extracted {len(extracted)} item(s)")
        if repeated:
            logger.debug(f"{tag} {repeated} item(s) repeated by the overlap, discarded")
        return items

    def _identity(self, raw: dict) -> str:
        """What makes two extractions the same item: its modality and its primary field.

        Compared FOLDED, because the same exercise read from two overlapping batches comes
        back with the same words and not necessarily the same spacing.
        """
        key = raw.get(ITEM_TYPE_KEY) or self.exemplars_profile.default_type
        try:
            item_type = self.exemplars_profile.item_type(str(key))
            text = item_type.primary_text(raw)
        except (KeyError, ValueError):
            return ""
        return f"{item_type.key}::{fold(text).strip()}" if text.strip() else ""

    @staticmethod
    def _grammar_costs_the_text(model: str) -> bool:
        r"""Whether a grammar on `model` would mangle the prose it makes it copy.

        Measured against Cerebras' constrained decoding: `gemma-4-31b` stops emitting raw
        UTF-8 inside a JSON string and takes the grammar's `\uXXXX` branch for every
        non-ASCII character, then writes the hex wrong. One real batch came back with 107
        escapes, all of them `\u00` plus two arbitrary digits, so `á`, `é`, `ó`, `ñ` and
        `→` all reached the bank as a single control character. It worsens with the length
        of what is generated (107 escapes under the real schema, 17 under a one-field one,
        0 on a short answer) and `json_object` mode is no cure (31), which is why the whole
        `response_format` has to go rather than only its schema.
        """
        return model in inference.remote_models()

    def _grammar(self) -> dict | None:
        """The extraction schema, or nothing when a grammar would cost the text itself.

        Reasoning silences a grammar as it does everywhere else. A remotely served model
        drops it for the heavier reason above: this is the one phase that copies whole
        paragraphs of the corpus verbatim, and losing the text is worse than losing the
        decoder's guarantee, which `parse_with_repair` takes over exactly as it does for
        the phases that reason.
        """
        if config.THINK_EB_EXTRACT:
            return None
        if self._grammar_costs_the_text(config.EB_EXTRACT_MODEL):
            return None
        return self._extraction_schema

    def _extract_batch(self, batch: str, tag: str) -> list[dict]:
        """Ask for one batch's items, raising when no repair produces usable JSON."""
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
            format=self._grammar(),
            temperature=inference.judgement_temperature(config.THINK_EB_EXTRACT),
        ).response

        # A repair re-emits the same paragraphs, so a grammar kept here would undo the drop
        # above on the one path that runs when the reply was already malformed.
        repair_grammar = (
            None if self._grammar_costs_the_text(config.REPAIR_LLM) else self._extraction_schema
        )
        items, err = parse_with_repair(
            response,
            self._parse_and_validate,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="array",
            format=repair_grammar,
            log_prefix=f"{tag} ",
            prompts=self.prompts,
        )

        if items is None:
            raise ValueError(f"unrecoverable JSON after {self.max_repair_attempts} repairs: {err}")
        return items

    def _parse_and_validate(self, response: str) -> tuple[list[dict] | None, str | None]:
        """Validate each raw object against the schema of the modality it declares.

        A mislabelled item fails loudly here instead of reaching the bank wearing another
        modality's fields. A single type in the profile makes `item_type` optional: there is
        nothing to choose, and demanding it would only add a way for the model to fail.
        """
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
        """Pack the document's blocks into batches of at most `chunk_size`, OVERLAPPING them.

        The last `EB_BATCH_OVERLAP_BLOCKS` blocks of a batch open the next one, so an
        exercise straddling the size cut is seen whole by at least one call instead of half
        by each; the price is items extracted twice, and `_identity` is what pays it. The
        ~10-character separator budget is charged to the first block of a batch too.
        """
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

    def _carry_over(self, blocks: list[str]) -> list[str]:
        """The trailing blocks that open the next batch — only what leaves room.

        Carrying a block that fills half the budget would push the very next cut back into
        the same block and could stop the batches advancing at all.
        """
        count = min(config.EB_BATCH_OVERLAP_BLOCKS, len(blocks))
        carried: list[str] = []
        for block in reversed(blocks[len(blocks) - count :]):
            if sum(len(b) for b in carried) + len(block) > self.chunk_size // 2:
                break
            carried.insert(0, block)
        return carried

    # HELPERS -------------------------------------------------------------------------------------

    def _next_id(self) -> str:
        """Claim the next `C###` identifier."""
        self._id_counter += 1
        return f"C{self._id_counter:03d}"
