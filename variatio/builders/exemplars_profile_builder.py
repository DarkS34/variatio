"""Inferring a DRAFT `exemplars_profile.json` from the raw exemplars documents.

The profile is what instantiates a use case: the modalities of item this instance sets, the
fields each of them has and the rules the generation follows. Treat the output as unstable —
it has produced different field sets across runs over the same corpus.
"""

import json
import re
import unicodedata
from pathlib import Path

from json_repair import repair_json
from loguru import logger

from .. import config
from ..core import inference, progress
from ..core.inference import ensure_models
from ..core.json_io import write_json
from ..core.repair import parse_with_repair
from ..core.workspace import Workspace
from ..instance import content_context, locale
from ..instance.exemplars_profile import DIFFICULTY_FIELDS, ExemplarsProfile
from .. import prompts as prompts_pkg
from . import _context, _source_docs


BUILD_PHASES = (
    ("convert", "Transcribiendo los ejemplares", 40),
    ("scan", "Buscando modalidades de ejercicio", 40),
    ("consolidate", "Consolidando el perfil", 19),
    # Last, and one call: it needs the modalities the consolidation has just written.
    ("context", "Poniendo por escrito de qué asignatura es esto", 1),
)

MAX_EXCERPTS_PER_TYPE = 3

# How many verbatim exemplars the context synthesis sees. Three are enough to pin the
# subject, level and notation, and few enough not to drag one item's topic into the text.
CONTEXT_EXCERPTS = 3

# The scan's shape is fixed, so it is stated as a schema. The CONSOLIDATION's is not: what it
# returns is a profile, and a profile CONTAINS JSON Schemas the model writes itself, one per
# field of each modality it invents. There is no schema for «an object whose values are
# arbitrary schemas» that would constrain anything worth constraining, so that call gets
# `"json"` — the syntax guaranteed, the shape left to `_validate`, which already knows it.
SCAN_SCHEMA = {
    "type": "object",
    "properties": {
        "types": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "signals": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "excerpt": {"type": "string"},
                },
                "required": ["key", "label", "signals", "fields", "excerpt"],
            },
        }
    },
    "required": ["types"],
}


def build_models() -> list[str]:
    """Every model a profile build calls."""
    return [
        config.TRANSCRIBE_MODEL,
        config.TRANSCRIBE_SEAM_MODEL,
        config.EP_SCAN_MODEL,
        config.EP_CONSOLIDATE_MODEL,
        config.EP_CONTEXT_MODEL,
        config.REPAIR_LLM,
    ]


def _fold(value: str) -> str:
    """Fold one enum value for comparison: lowercase, unaccented, trimmed."""
    stripped = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(c for c in stripped if not unicodedata.combining(c))


def guarantee_difficulty(profile: dict, prompts) -> dict:
    """Give every modality the difficulty field, on the ladder every modality shares.

    The prompt asks for it in a section of its own; this is what makes it true. Measured on
    the real builds of two workspaces before either existed: the model already converged on
    the field and on those three rungs by itself, so the ladder costs nothing — but one
    draft spelled a rung `básico` with its accent (a different stored value from the same
    builder on the same corpus), none of the four drafts set `decided_by`, and the criteria
    were three words a rung. The first two are shape and are fixed here; the third is
    judgement and only the prompt can produce it.

    Everything it writes is a floor, never a rewrite: a criterion the model wrote survives
    untouched, and the fallback is used only where there is nothing at all. A ladder that
    does NOT fold onto the canonical one is replaced and said out loud, because the
    description then enumerates rungs that no longer exist — kept rather than dropped,
    since it is the modality's only reasoning and the profile screen now puts it where
    somebody will read it.
    """
    field = prompts.DIFFICULTY_FIELD
    levels = list(prompts.DIFFICULTY_LEVELS)
    canonical = {_fold(level): level for level in levels}

    for key, spec in (profile.get("item_types") or {}).items():
        if not isinstance(spec, dict):
            continue
        fields = spec.get("fields")
        if not isinstance(fields, dict):
            continue

        found = next((name for name in (field, *DIFFICULTY_FIELDS) if name in fields), None)
        entry = fields.pop(found) if found else None
        if not isinstance(entry, dict):
            entry = {}
        if found is None:
            logger.warning(f"«{key}»: no difficulty field; adding '{field}' with no criterion")
        elif found != field:
            logger.warning(f"«{key}»: difficulty declared as '{found}'; renamed to '{field}'")

        schema = entry.get("schema")
        declared = schema.get("enum") if isinstance(schema, dict) else None
        if isinstance(declared, list) and declared:
            folded = [canonical.get(_fold(v)) for v in declared]
            if sorted(v for v in folded if v) != sorted(levels) or None in folded:
                logger.warning(
                    f"«{key}»: difficulty declared {declared}; replaced by the shared ladder "
                    f"{levels}. Its criterion still describes the old rungs — correct it by hand"
                )
        entry["schema"] = {"enum": levels}

        if not str(entry.get("description") or "").strip():
            entry["description"] = prompts.DIFFICULTY_FALLBACK_DESCRIPTION
        guidance = entry.get("guidance")
        guidance = dict(guidance) if isinstance(guidance, dict) else {}
        if not str(guidance.get("extraction") or "").strip():
            guidance["extraction"] = prompts.DIFFICULTY_FALLBACK_EXTRACTION
        entry["guidance"] = {"extraction": guidance["extraction"]}
        entry["decided_by"] = "user"

        # Last of the fields, so the artifact reads the way the screens draw it.
        fields[field] = entry

        # It carries no concept and adds the same noise to every item, so indexing it can
        # only hurt retrieval. The prompt says so twice; this is what makes it so.
        embed = spec.get("embed_fields")
        if isinstance(embed, list):
            kept = [name for name in embed if name not in (field, *DIFFICULTY_FIELDS)]
            if kept != embed:
                logger.warning(f"«{key}»: '{field}' dropped from embed_fields")
                spec["embed_fields"] = kept

    return profile


def _remember(values: list[str], value: str) -> None:
    """Append `value` once, ignoring an empty one."""
    if value and value not in values:
        values.append(value)


class ExemplarsProfileBuilder:
    """Scans the exemplars corpus for modalities and consolidates them into a draft profile."""

    def __init__(
        self,
        workspace: Workspace,
        scan_model: str | None = None,
        consolidate_model: str | None = None,
        context_model: str | None = None,
        verbose: bool = True,
    ):
        """Resolve the workspace's prompt set and the three models of the build."""
        self.workspace = workspace
        self.prompts = prompts_pkg.of(locale.prompt_language(workspace))
        self._context_cache: str | None = None
        self.scan_model = scan_model or config.EP_SCAN_MODEL
        self.consolidate_model = consolidate_model or config.EP_CONSOLIDATE_MODEL
        self.context_model = context_model or config.EP_CONTEXT_MODEL
        self.chunk_size = config.EP_CHUNK_SIZE
        self.excerpt_chars = config.EP_SCAN_EXCERPT_CHARS
        self.max_item_types = config.EP_MAX_ITEM_TYPES
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES

        logger.enable(__name__) if verbose else logger.disable(__name__)

        # Only `.docx` and `.pptx` ever reach it: a PDF goes through the page-transcription
        # route and plain text needs no conversion, so on a PDF corpus Docling is never built.
        self._docling = _source_docs.LazyConverter(ocr=config.EXEMPLARS_OCR)

    # PUBLIC API ----------------------------------------------------------------------------------

    def bootstrap(self) -> None:
        """Check this build's own models are installed, the overridden ones included."""
        ensure_models(
            [
                config.TRANSCRIBE_MODEL,
                config.TRANSCRIBE_SEAM_MODEL,
                self.scan_model,
                self.consolidate_model,
                self.context_model,
                config.REPAIR_LLM,
            ],
            "exemplars profile",
        )

    def build(self, input_dir: str, output_file_path: str) -> dict:
        """Scan the corpus, consolidate the draft profile, write it and return it.

        A draft that does not load is saved anyway and reported: it is a starting point for
        somebody to correct by hand, and losing it would cost the whole scan again.
        """
        self.bootstrap()

        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"No supported document in {input_dir}")
            return {}

        logger.info(f"{len(files)} document(s); looking for exercise modalities")
        chunks = self._convert(files)
        if not chunks:
            logger.error("No document contributed any content")
            return {}

        findings = self._scan(chunks)
        if not findings:
            logger.error("No exercise modality found in the corpus")
            return {}

        profile = self._consolidate(findings)
        if not profile:
            logger.error("Could not write the profile draft")
            return {}

        write_json(output_file_path, profile)
        try:
            loaded = ExemplarsProfile(output_file_path)
            logger.success(
                f"Profile draft in {Path(output_file_path).name}: loads cleanly, "
                f"{len(loaded.item_types)} item type(s) ({', '.join(loaded.type_keys)})"
            )
        except Exception as e:
            logger.warning(
                f"Profile draft in {Path(output_file_path).name}: "
                f"needs corrections by hand before it will load ({e})"
            )

        self.synthesize_context(profile, findings)
        return profile

    def synthesize_context(self, profile: dict, found: dict[str, dict]) -> None:
        """Write the subject-context draft from what the profile knows that the graph does not.

        The FORMS in which this subject sets its tasks, plus verbatim excerpts — and those
        are the half that matters: the modality labels say the shape of a task, only a real
        statement says the material is a first-year Python workbook rather than programming
        in the abstract.
        """
        progress.phase("context")
        item_types = profile.get("item_types") or {}
        if not item_types:
            return
        lines = [f"La asignatura plantea sus tareas en {len(item_types)} modalidad(es):"]
        for key, spec in item_types.items():
            label = spec.get("label") or key
            lines.append(f"- {label}: {spec.get('description') or 'sin descripción'}")

        excerpts = [
            excerpt
            for record in found.values()
            for _, excerpt in record.get("excerpts", [])
        ][:CONTEXT_EXCERPTS]
        if excerpts:
            lines.append("Ejemplares literales del material:")
            lines.extend(f"---\n{excerpt}" for excerpt in excerpts)

        _context.synthesize(
            self.workspace,
            "\n".join(lines),
            "EL PERFIL DE EJEMPLARES",
            self.context_model,
            think=config.THINK_EP_CONTEXT,
        )
        progress.advance(1.0)

    # CONVERSION ----------------------------------------------------------------------------------

    def _convert(self, files: list[Path]) -> list[tuple[str, str]]:
        """Transcribe and chunk the WHOLE corpus, never a sample.

        A workbook that opens with forty coding exercises and closes with a page of
        multiple-choice questions would otherwise declare one modality: whatever the head of
        the document happened to show.
        """
        progress.phase("convert", f"0/{len(files)} documento(s)")
        chunks: list[tuple[str, str]] = []
        with progress.step(
            "convert", "Transcribiendo los ejemplares", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.start(idx, detail=file_path.name)
                progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
                try:
                    content = _source_docs.document_markdown(
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
                    logger.exception(f"[{file_path.name}] skipped: {e}")
                    continue
                if not content.strip():
                    logger.warning(f"[{file_path.name}] no content after the transcription")
                    continue
                for heading, body in _source_docs.chunk_markdown(content, self.chunk_size):
                    location = f"{file_path.stem} > {heading}" if heading else file_path.stem
                    chunks.append((location, body))

        progress.advance(1.0, f"{len(chunks)} fragmento(s)")
        logger.info(f"Corpus split into {len(chunks)} chunk(s) of up to {self.chunk_size:,} characters")
        return chunks

    # SCANNING ------------------------------------------------------------------------------------

    def _scan(self, chunks: list[tuple[str, str]]) -> dict[str, dict]:
        """Look for exercise modalities in every chunk, gathered by the key the scanner gave."""
        progress.phase("scan", f"0/{len(chunks)} fragmento(s)")
        found: dict[str, dict] = {}

        with progress.step(
            "scan", "Buscando modalidades de ejercicio", len(chunks)
        ) as reporter:
            for idx, (location, body) in enumerate(chunks, 1):
                progress.checkpoint()
                reporter.start(idx, detail=location)
                progress.advance(
                    (idx - 1) / len(chunks),
                    f"{location} ({idx}/{len(chunks)}) · {len(found)} modalidad(es)",
                )
                for entry in self._scan_chunk(body, location, f"[{idx}/{len(chunks)}] "):
                    self._merge_finding(found, entry, location)

        progress.advance(1.0, f"{len(found)} modalidad(es)")
        logger.success(
            f"Scan finished: {len(found)} candidate modality(ies) ({', '.join(sorted(found))})"
        )
        return found

    def _context_block(self) -> str:
        """The subject's context, or an empty block on the build that has none yet.

        Read once per build and cached, because both phases ask for it and the file does
        not change while a build runs. Empty is the ordinary state of a FIRST build: the
        context is synthesised in this same builder's last phase, so there is nothing to
        pass until there has been one build. From the second onwards the two phases know
        the subject, the level and — the reason this exists — the language it is taught in.
        """
        if self._context_cache is None:
            self._context_cache = content_context.load_for(self.workspace).prompt_block()
        return self._context_cache

    def _scan_chunk(self, body: str, location: str, tag: str) -> list[dict]:
        """Ask one chunk for its modalities, `[]` when the answer cannot be repaired."""
        prompt = self.prompts.scan_item_types_prompt(
            body, location, self.excerpt_chars, context_block=self._context_block()
        )
        response = inference.generate(
            model=self.scan_model,
            think=config.THINK_EP_SCAN,
            prompt=prompt,
            format=None if config.THINK_EP_SCAN else SCAN_SCHEMA,
            temperature=inference.judgement_temperature(config.THINK_EP_SCAN),
        ).response

        entries, err = parse_with_repair(
            response,
            self._parse_scan,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            format=SCAN_SCHEMA,
            log_prefix=tag,
            prompts=self.prompts,
        )
        if entries is None:
            logger.warning(f"{tag}{location}: unusable scan ({err}); skipped")
            return []
        return entries

    @staticmethod
    def _parse_scan(response: str) -> tuple[list[dict] | None, str | None]:
        """Read the scan answer as the list of typed entries that at least carry a key."""
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            raw = repair_json(cleaned, return_objects=True)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"
        if not isinstance(raw, dict):
            return None, "top-level JSON is not an object"
        types = raw.get("types")
        if types is None:
            return None, "missing 'types' key"
        if not isinstance(types, list):
            return None, "'types' is not an array"
        return [entry for entry in types if isinstance(entry, dict) and entry.get("key")], None

    def _merge_finding(self, found: dict[str, dict], entry: dict, location: str) -> None:
        """Fold one scanned entry into the record of its key.

        Findings are merged only when the scanner gave them the SAME key: that much is
        mechanical. Deciding that `pregunta_test` and `test_opcion_multiple` are one modality
        is a judgement, and it belongs to the consolidation call that sees both anatomies
        side by side.
        """
        key = str(entry.get("key") or "").strip()
        if not key:
            return
        record = found.setdefault(
            key,
            {"key": key, "labels": [], "signals": [], "fields": [], "excerpts": [], "seen": 0},
        )
        record["seen"] += 1

        _remember(record["labels"], str(entry.get("label") or "").strip())
        _remember(record["signals"], str(entry.get("signals") or "").strip())
        for name in entry.get("fields") or []:
            _remember(record["fields"], str(name).strip())

        excerpt = str(entry.get("excerpt") or "").strip()
        if excerpt and len(record["excerpts"]) < MAX_EXCERPTS_PER_TYPE:
            record["excerpts"].append((location, excerpt[: self.excerpt_chars]))

    def _findings_block(self, found: dict[str, dict]) -> str:
        """The scan's findings as the prompt sees them, the most frequent modality first."""
        blocks = []
        for record in sorted(found.values(), key=lambda r: -r["seen"]):
            lines = [
                f"## `{record['key']}` — {' / '.join(record['labels']) or record['key']}",
                f"Visto en {record['seen']} fragmento(s).",
            ]
            if record["signals"]:
                lines.append("Señales: " + " | ".join(record["signals"][:3]))
            if record["fields"]:
                lines.append("Campos observados: " + ", ".join(record["fields"]))
            for location, excerpt in record["excerpts"]:
                lines.append(f"Ejemplar ({location}):\n{excerpt}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    # CONSOLIDATION -------------------------------------------------------------------------------

    def _consolidate(self, found: dict[str, dict]) -> dict:
        """Turn the candidate modalities into one profile, under its own progress step."""
        progress.phase("consolidate", f"{len(found)} modalidad(es) candidata(s)")
        with progress.step("consolidate", "Consolidando el perfil de ejemplares"):
            profile = guarantee_difficulty(self._infer(self._findings_block(found)), self.prompts)
        progress.advance(1.0)
        return profile

    def _infer(self, findings: str) -> dict:
        """Ask for the profile and repair it until it validates, or give up and keep it.

        Two repair routes: unreadable JSON goes to the repair model, while a profile that
        parses but does not validate goes back to the model that wrote it, with the error.
        """
        prompt = self.prompts.consolidate_exemplars_profile_prompt(
            findings, self.max_item_types, context_block=self._context_block()
        )
        think = (
            config.THINK_EP_CONSOLIDATE
            if inference.supports_thinking(self.consolidate_model)
            else False
        )
        logger.info(
            f"Consolidating with '{self.consolidate_model}' "
            f"(reasoning {'on' if think else 'off'})"
        )
        response = inference.generate(
            model=self.consolidate_model,
            think=think,
            prompt=prompt,
            temperature=inference.judgement_temperature(think),
        ).response
        profile = self._parse(response)
        err = self._validate(profile)

        for attempt in range(1, self.max_repair_attempts + 1):
            if err is None:
                break
            logger.warning(f"Repair {attempt}/{self.max_repair_attempts}: {err}")
            if profile is None:
                repair_model = config.REPAIR_LLM
                repair_prompt = self.prompts.json_repair_prompt(
                    broken_output=response, error_msg=err, shape="objeto"
                )
            else:
                repair_model = self.consolidate_model
                repair_prompt = self.prompts.repair_exemplars_profile_prompt(
                    profile=json.dumps(profile, ensure_ascii=False, indent=2), error_msg=err
                )
            response = inference.generate(
                model=repair_model,
                prompt=repair_prompt,
                think=False,
                format="json",
                temperature=config.TEMPERATURE_REPAIR,
            ).response
            candidate = self._parse(response)
            if candidate is not None:
                profile = candidate
            err = self._validate(profile)

        if profile is None:
            return {}
        if err is not None:
            logger.warning(f"The profile still does not validate after the repairs; saving it anyway: {err}")
        return profile

    @classmethod
    def _parse(cls, response: str) -> dict | None:
        """Repair the answer into a non-empty object, or `None`."""
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
        raw = repair_json(cleaned, return_objects=True)
        return raw if isinstance(raw, dict) and raw else None

    @classmethod
    def _validate(cls, profile: dict | None) -> str | None:
        """`None` when the profile is loadable, otherwise the reason it is not."""
        if profile is None:
            return "top-level JSON is not an object"
        try:
            ExemplarsProfile.validate_raw(profile)
            return None
        except (ValueError, KeyError, TypeError) as e:
            return f"{type(e).__name__}: {str(e)[:200]}"
