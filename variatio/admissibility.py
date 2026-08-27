import json
from dataclasses import dataclass

from json_repair import repair_json
from loguru import logger

from . import config
from .core import inference, progress
from .core.inference import InferenceError
from .core.lexicon import fold


@dataclass(frozen=True)
class Slot:
    key: str
    label: str
    example: str


@dataclass(frozen=True)
class Owner:
    key: str
    label: str
    where: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class Request:
    text: str
    slot: str | None
    owner: Owner | None
    term: str | None


@dataclass(frozen=True)
class Ruling:
    requests: tuple[Request, ...]
    checked: bool

    @property
    def blocked(self) -> tuple[Request, ...]:
        return tuple(r for r in self.requests if r.owner is not None)

    @property
    def ok(self) -> bool:
        return not self.blocked


CATALOG: tuple[Slot, ...] = (
    Slot("ambito", "Ámbito", "que vaya de una panadería"),
    Slot("elementos", "Elementos del enunciado", "con una tabla de datos"),
    Slot("extension", "Extensión", "un enunciado breve"),
    Slot("datos", "Datos concretos", "que la lista tenga al menos 10 elementos"),
)


def owners(knowledge_graph, item_type, profile, content_context, concepts) -> list[Owner]:
    targets = set(concepts)
    found: list[Owner] = []

    others = tuple(c for c in knowledge_graph.all_concepts if c not in targets)
    if others:
        found.append(
            Owner(
                key="concepts",
                label="los conceptos objetivo",
                where="elígelos en el paso de conceptos",
                terms=others,
            )
        )

    for name, spec in item_type.field_specs.items():
        if spec.get("decided_by") != "user":
            continue
        values = tuple(str(v) for v in (spec.get("schema") or {}).get("enum") or ())
        if not values:
            continue
        found.append(
            Owner(
                key=f"field:{name}",
                label=name,
                where="decídelo en «¿Cómo debe ser?»",
                terms=values,
            )
        )

    modalities = tuple(
        value
        for key in profile.item_types
        for value in (key, profile.item_type(key).label)
    )
    found.append(
        Owner(
            key="item_type",
            label="la modalidad del ejercicio",
            where="elígela en el paso de modalidad",
            terms=modalities,
        )
    )

    facts = tuple(
        value
        for value in (
            content_context.subject,
            content_context.educational_level,
            content_context.language_of_instruction,
        )
        if value
    )
    if facts:
        found.append(
            Owner(
                key="context",
                label="la materia, el nivel y el idioma",
                where="los fija el contexto de la asignatura, en el panel",
                terms=facts,
            )
        )

    return found


def _schema(owners: list[Owner]) -> dict:
    return {
        "type": "object",
        "properties": {
            "requests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "slot": {"enum": [*(s.key for s in CATALOG), None]},
                        "owner": {"enum": [*(o.key for o in owners), None]},
                        "term": {"type": ["string", "null"]},
                    },
                    "required": ["text", "slot", "owner", "term"],
                },
            }
        },
        "required": ["requests"],
    }


def _accept(entry: dict, owners: list[Owner], targets: set[str]) -> Request | None:
    text = str(entry.get("text") or "").strip()
    if not text:
        return None

    slot = entry.get("slot")
    if slot in {s.key for s in CATALOG}:
        return Request(text=text, slot=slot, owner=None, term=None)

    owner = next((o for o in owners if o.key == entry.get("owner")), None)
    if owner is None:
        return None

    wanted = fold(str(entry.get("term") or ""))
    if not wanted:
        return None
    term = next((t for t in owner.terms if fold(t) == wanted), None)
    if term is None or term in targets:
        return None

    return Request(text=text, slot=None, owner=owner, term=term)


def screen(
    text: str,
    owners: list[Owner],
    targets: list[str],
    prompts,
    context_block: str = "",
) -> Ruling:
    text = (text or "").strip()
    if not text:
        return Ruling(requests=(), checked=True)

    prompt = prompts.classify_instructions_prompt(
        instructions=text,
        catalog=CATALOG,
        owners=owners,
        targets=targets,
        context_block=context_block,
    )

    try:
        response = inference.generate(
            model=config.ADMISSIBILITY_LLM,
            prompt=prompt,
            think=config.THINK_ADMISSIBILITY,
            format=None if config.THINK_ADMISSIBILITY else _schema(owners),
            temperature=inference.judgement_temperature(config.THINK_ADMISSIBILITY),
        ).response
    except InferenceError as e:
        logger.warning(f"[admisibilidad] El juez no pudo responder: {e}; el encargo sigue adelante")
        return _unchecked()

    entries = _parse(response)
    if entries is None:
        logger.warning(
            f"[admisibilidad] Respuesta ilegible del juez: {response[:120]!r}; "
            "el encargo sigue adelante"
        )
        return _unchecked()

    known = set(targets)
    requests = tuple(r for r in (_accept(e, owners, known) for e in entries) if r is not None)
    if not requests:
        logger.warning(
            "[admisibilidad] Ninguna entrada del juez resultó válida; el encargo sigue adelante"
        )
        return _unchecked()

    ruling = Ruling(requests=requests, checked=True)
    _report(ruling)
    return ruling


def _parse(response: str) -> list[dict] | None:
    try:
        data = json.loads(repair_json(response))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    entries = data.get("requests")
    if not isinstance(entries, list):
        return None
    return [e for e in entries if isinstance(e, dict)]


def _unchecked() -> Ruling:
    ruling = Ruling(requests=(), checked=False)
    progress.emit("admissibility", ok=True, checked=False, slots=[], owner=None, term=None)
    return ruling


def _report(ruling: Ruling) -> None:
    blocked = ruling.blocked
    if blocked:
        first = blocked[0]
        logger.info(
            f"[admisibilidad] «{first.text}» invade {first.owner.label} por «{first.term}»"
        )
    else:
        logger.info(
            f"[admisibilidad] {len(ruling.requests)} petición(es) admitida(s): "
            + ", ".join(r.slot for r in ruling.requests)
        )
    progress.emit(
        "admissibility",
        ok=ruling.ok,
        checked=True,
        slots=[r.slot for r in ruling.requests if r.slot],
        owner=blocked[0].owner.label if blocked else None,
        term=blocked[0].term if blocked else None,
    )
