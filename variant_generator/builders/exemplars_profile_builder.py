import json
import re
from pathlib import Path

from json_repair import repair_json
from loguru import logger

from .. import config, inference, progress
from ..exemplars_profile import ExemplarsProfile
from ..prompts import (
    consolidate_exemplars_profile_prompt,
    json_repair_prompt,
    repair_exemplars_profile_prompt,
    scan_item_types_prompt,
)
from ..utils import ensure_models, parse_with_repair
from . import _source_docs


BUILD_PHASES = (
    ("convert", "Transcribiendo los ejemplares", 40),
    ("scan", "Buscando modalidades de ejercicio", 40),
    ("consolidate", "Consolidando el perfil", 20),
)

MAX_EXCERPTS_PER_TYPE = 3

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


class ExemplarsProfileBuilder:
    def __init__(
        self,
        scan_model: str = config.EP_SCAN_MODEL,
        consolidate_model: str = config.EP_CONSOLIDATE_MODEL,
        verbose: bool = True,
        workspace=None,
    ):
        self.workspace = workspace or config.default_workspace()
        self.scan_model = scan_model
        self.consolidate_model = consolidate_model
        self.chunk_size = config.EP_CHUNK_SIZE
        self.excerpt_chars = config.EP_SCAN_EXCERPT_CHARS
        self.max_item_types = config.EP_MAX_ITEM_TYPES
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES

        logger.enable(__name__) if verbose else logger.disable(__name__)

        self._docling = _source_docs.default_converter(ocr=config.EXEMPLARS_OCR)

    # PUBLIC API ----------------------------------------------------------------------------------

    def bootstrap(self) -> None:
        ensure_models(
            [
                config.EXEMPLARS_TRANSCRIBE_MODEL,
                self.scan_model,
                self.consolidate_model,
                config.REPAIR_LLM,
            ],
            "del perfil de ejemplares",
        )

    def build(self, input_dir: str, output_file_path: str) -> dict:
        self.bootstrap()

        files = _source_docs.list_source_files(input_dir)
        if not files:
            logger.error(f"Ningún documento admitido en {input_dir}")
            return {}

        logger.info(f"{len(files)} documento(s); buscando modalidades de ejercicio")
        chunks = self._convert(files)
        if not chunks:
            logger.error("Ningún documento aportó contenido")
            return {}

        findings = self._scan(chunks)
        if not findings:
            logger.error("Ninguna modalidad de ejercicio encontrada en el corpus")
            return {}

        profile = self._consolidate(findings)
        if not profile:
            logger.error("No se pudo redactar el borrador del perfil")
            return {}

        _source_docs.save_json(profile, output_file_path)
        try:
            loaded = ExemplarsProfile(output_file_path)
            logger.success(
                f"Borrador del perfil en {Path(output_file_path).name}: carga bien, "
                f"{len(loaded.item_types)} tipo(s) de ítem ({', '.join(loaded.type_keys)})"
            )
        except Exception as e:
            logger.warning(
                f"Borrador del perfil en {Path(output_file_path).name}: "
                f"necesita correcciones a mano antes de cargar ({e})"
            )
        return profile

    # CONVERSION ----------------------------------------------------------------------------------

    # The whole corpus is chunked and scanned, never sampled. A workbook that opens with
    # forty coding exercises and closes with a page of multiple-choice questions would
    # otherwise declare one modality: whatever the head of the document happened to show.
    def _convert(self, files: list[Path]) -> list[tuple[str, str]]:
        progress.phase("convert", f"0/{len(files)} documento(s)")
        chunks: list[tuple[str, str]] = []
        with progress.step(
            "convert", "Transcribiendo los ejemplares", len(files)
        ) as reporter:
            for idx, file_path in enumerate(files, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=file_path.name)
                progress.advance((idx - 1) / len(files), f"{file_path.name} ({idx}/{len(files)})")
                try:
                    content = _source_docs.join_pages(
                        _source_docs.document_pages(
                            file_path,
                            converter=self._docling,
                            ocr=config.EXEMPLARS_OCR,
                            tag=f"[{idx}/{len(files)}] ",
                            cache_dir=self.workspace.markdown_cache_dir,
                        )
                    )
                except progress.Cancelled:
                    raise
                except Exception as e:
                    logger.exception(f"[{file_path.name}] omitido: {e}")
                    continue
                if not content.strip():
                    logger.warning(f"[{file_path.name}] sin contenido tras la transcripción")
                    continue
                for heading, body in _source_docs.chunk_markdown(content, self.chunk_size):
                    location = f"{file_path.stem} > {heading}" if heading else file_path.stem
                    chunks.append((location, body))

        progress.advance(1.0, f"{len(chunks)} fragmento(s)")
        logger.info(f"Corpus partido en {len(chunks)} fragmento(s) de hasta {self.chunk_size:,} caracteres")
        return chunks

    # SCANNING ------------------------------------------------------------------------------------

    def _scan(self, chunks: list[tuple[str, str]]) -> dict[str, dict]:
        progress.phase("scan", f"0/{len(chunks)} fragmento(s)")
        found: dict[str, dict] = {}

        with progress.step(
            "scan", "Buscando modalidades de ejercicio", len(chunks)
        ) as reporter:
            for idx, (location, body) in enumerate(chunks, 1):
                progress.checkpoint()
                reporter.tick(idx, detail=location)
                progress.advance(
                    (idx - 1) / len(chunks),
                    f"{location} ({idx}/{len(chunks)}) · {len(found)} modalidad(es)",
                )
                for entry in self._scan_chunk(body, location, f"[{idx}/{len(chunks)}] "):
                    self._merge_finding(found, entry, location)

        progress.advance(1.0, f"{len(found)} modalidad(es)")
        logger.success(
            f"Rastreo terminado: {len(found)} modalidad(es) candidatas ({', '.join(sorted(found))})"
        )
        return found

    def _scan_chunk(self, body: str, location: str, tag: str) -> list[dict]:
        prompt = scan_item_types_prompt(body, location, self.excerpt_chars)
        response = inference.generate(
            model=self.scan_model, think=False, prompt=prompt, format=SCAN_SCHEMA
        ).response

        entries, err = parse_with_repair(
            response,
            self._parse_scan,
            repair_model=config.REPAIR_LLM,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            format=SCAN_SCHEMA,
            log_prefix=tag,
        )
        if entries is None:
            logger.warning(f"{tag}{location}: rastreo inservible ({err}); omitido")
            return []
        return entries

    @staticmethod
    def _parse_scan(response: str) -> tuple[list[dict] | None, str | None]:
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

    # Findings are merged only when the scanner gave them the SAME key: that much is
    # mechanical. Deciding that `pregunta_test` and `test_opcion_multiple` are one
    # modality is a judgement, and it belongs to the consolidation call that can see
    # both anatomies side by side.
    def _merge_finding(self, found: dict[str, dict], entry: dict, location: str) -> None:
        key = str(entry.get("key") or "").strip()
        if not key:
            return
        record = found.setdefault(
            key,
            {"key": key, "labels": [], "signals": [], "fields": [], "excerpts": [], "seen": 0},
        )
        record["seen"] += 1

        label = str(entry.get("label") or "").strip()
        if label and label not in record["labels"]:
            record["labels"].append(label)

        signals = str(entry.get("signals") or "").strip()
        if signals and signals not in record["signals"]:
            record["signals"].append(signals)

        for name in entry.get("fields") or []:
            name = str(name).strip()
            if name and name not in record["fields"]:
                record["fields"].append(name)

        excerpt = str(entry.get("excerpt") or "").strip()
        if excerpt and len(record["excerpts"]) < MAX_EXCERPTS_PER_TYPE:
            record["excerpts"].append((location, excerpt[: self.excerpt_chars]))

    def _findings_block(self, found: dict[str, dict]) -> str:
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
        progress.phase("consolidate", f"{len(found)} modalidad(es) candidata(s)")
        with progress.step("consolidate", "Consolidando el perfil de ejemplares"):
            profile = self._infer(self._findings_block(found))
        progress.advance(1.0)
        return profile

    def _infer(self, findings: str) -> dict:
        prompt = consolidate_exemplars_profile_prompt(findings, self.max_item_types)
        think = inference.supports_thinking(self.consolidate_model)
        logger.info(
            f"Consolidando con '{self.consolidate_model}' "
            f"(razonamiento {'activado' if think else 'desactivado'})"
        )
        response = inference.generate(
            model=self.consolidate_model, think=think, prompt=prompt
        ).response
        profile = self._parse(response)
        err = self._validate(profile)

        for attempt in range(1, self.max_repair_attempts + 1):
            if err is None:
                break
            logger.warning(f"Reparación {attempt}/{self.max_repair_attempts}: {err}")
            if profile is None:
                repair_model = config.REPAIR_LLM
                repair_prompt = json_repair_prompt(
                    broken_output=response, error_msg=err, shape="objeto"
                )
            else:
                repair_model = self.consolidate_model
                repair_prompt = repair_exemplars_profile_prompt(
                    profile=json.dumps(profile, ensure_ascii=False, indent=2), error_msg=err
                )
            response = inference.generate(
                model=repair_model, prompt=repair_prompt, think=False, format="json"
            ).response
            candidate = self._parse(response)
            if candidate is not None:
                profile = candidate
            err = self._validate(profile)

        if profile is None:
            return {}
        if err is not None:
            logger.warning(f"El perfil sigue sin validar tras las reparaciones; se guarda igual: {err}")
        return profile

    @classmethod
    def _parse(cls, response: str) -> dict | None:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
        raw = repair_json(cleaned, return_objects=True)
        return raw if isinstance(raw, dict) and raw else None

    @classmethod
    def _validate(cls, profile: dict | None) -> str | None:
        if profile is None:
            return "top-level JSON is not an object"
        try:
            ExemplarsProfile.validate_raw(profile)
            return None
        except (ValueError, KeyError, TypeError) as e:
            return f"{type(e).__name__}: {str(e)[:200]}"
