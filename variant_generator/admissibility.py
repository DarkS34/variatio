from dataclasses import dataclass


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
