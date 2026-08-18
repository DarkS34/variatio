"""Cuánto exige cada concepto: la mitad estructural, la fusión con el juicio del modelo y
la invariante que hace defendible el número.

Puro a propósito: aquí no se importa `inference` ni `Workspace`, igual que en
`builders/knowledge_graph_builder/blocks.py`, así que todo lo que hay se puede comprobar con
un diccionario y sin GPU. Lo que sí se importa es `networkx`, porque la señal que de verdad
ordena una asignatura es un recorrido del DAG de prerrequisitos.

Trabaja sobre DATOS y no sobre un grafo cargado — la lista de conceptos y los tripletes
`[origen, clave, destino]` — porque quien lo llama primero es la curación, que todavía no ha
escrito ningún artefacto que se pueda cargar.
"""

import json
from collections import Counter
from pathlib import Path

import networkx as nx
from loguru import logger

from . import config
from .json_io import write_json

EMPTY: dict = {"concepts": {}}


# PERSISTENCIA ------------------------------------------------------------------------------


# Se lee como se leen las descripciones y el anclaje: SOLO EL FICHERO. Un workspace cuyo grafo
# llegó importado no lo tiene, y eso no es un error — se genera sin calibrar, que es como se
# generaba antes de que esto existiera. La regla que se rompería si aquí se cargara el grafo o
# el perfil está escrita en `review.UPSTREAM`: el grafo no tiene upstreams.
def load_difficulty(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return dict(EMPTY)
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(EMPTY)
    concepts = data.get("concepts")
    return {"concepts": concepts if isinstance(concepts, dict) else {}}


def save_difficulty(path: str | Path, data: dict) -> None:
    write_json(path, data)


def tier_of(concept: str, data: dict) -> int | None:
    entry = (data.get("concepts") or {}).get(concept) or {}
    tier = entry.get("tier")
    return tier if isinstance(tier, int) else None


def threshold_of(concept: str, data: dict) -> str:
    entry = (data.get("concepts") or {}).get(concept) or {}
    return str(entry.get("threshold") or "").strip()


# EL DAG DE PRERREQUISITOS ------------------------------------------------------------------


def prerequisite_pairs(relations: list[list], prerequisite_key: str | None) -> list[tuple[str, str]]:
    if not prerequisite_key:
        return []
    return [
        (source, target)
        for source, key, target in relations
        if key == prerequisite_key and source != target
    ]


# `A → B` significa «B es prerrequisito de A», que es la dirección en la que el esquema declara
# la relación y la que `ContentGenerator._prerequisites` lee como `direction="out"`.
#
# Los ciclos se rompen aquí y no se dan por imposibles: el borrador sale sin ellos porque
# `curation.break_cycles` los quita, pero el grafo curado se edita a mano y una arista puesta
# al revés no puede dejar sin dificultad a toda la asignatura.
def _dag(concepts: list[str], pairs: list[tuple[str, str]]) -> nx.DiGraph:
    universe = set(concepts)
    graph = nx.DiGraph()
    graph.add_nodes_from(concepts)
    graph.add_edges_from((s, t) for s, t in pairs if s in universe and t in universe)

    removed = 0
    while not nx.is_directed_acyclic_graph(graph):
        graph.remove_edge(*nx.find_cycle(graph)[-1][:2])
        removed += 1
    # En `debug` y no en `warning` porque el ciclo ya lo cuenta quien manda sobre él:
    # `curation.break_cycles` al construir y `KnowledgeGraph._report_cycles` al cargar. Aquí
    # se rompe para poder seguir calculando, y esto se recorre dos veces por calibración.
    if removed:
        logger.debug(f"Prerrequisitos con {removed} ciclo(s); se ignoran esas aristas al calibrar")
    return graph


def prerequisite_depth(concepts: list[str], pairs: list[tuple[str, str]]) -> dict[str, int]:
    """Cuántos prerrequisitos encadenados hay por debajo de cada concepto."""
    graph = _dag(concepts, pairs)
    depth = dict.fromkeys(graph.nodes, 0)
    # `topological_sort` da primero los que no dependen de nadie; al revés, los prerrequisitos
    # de un concepto ya están calculados cuando se llega a él.
    for node in reversed(list(nx.topological_sort(graph))):
        below = [depth[s] for s in graph.successors(node)]
        depth[node] = 1 + max(below) if below else 0
    return depth


# LA MITAD ESTRUCTURAL ----------------------------------------------------------------------


def _ratio(value: float, top: float) -> float:
    return 0.0 if top <= 0 else value / top


def _rescale(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    low, high = min(raw.values()), max(raw.values())
    # Un grafo sin un solo prerrequisito declarado no dice nada sobre la dificultad de nada,
    # y responder 0 fingiría que lo ha dicho. Neutro, y que decida el modelo.
    if high - low < 1e-9:
        logger.warning("La estructura del grafo no separa dificultades; señal estructural neutra")
        return {c: 0.5 for c in raw}
    return {c: (value - low) / (high - low) for c, value in raw.items()}


def structural_scores(concepts: list[str], relations: list[list], schema) -> dict[str, float]:
    """La dificultad que se lee del grafo, en [0,1], sin preguntarle a ningún modelo."""
    prerequisite = schema.prerequisite
    pairs = prerequisite_pairs(relations, prerequisite)
    depth = prerequisite_depth(concepts, pairs)

    needs = Counter(source for source, _ in pairs)
    enables = Counter(target for _, target in pairs)
    # Todas las claves específicas menos el prerrequisito: «es un tipo de» y «es parte de».
    # La de reserva queda fuera por construcción, que es lo que se quiere.
    hierarchy = {k for k in schema.specific_keys() if k != prerequisite}
    specificity = Counter(source for source, key, _ in relations if key in hierarchy)

    tops = (
        max(depth.values(), default=0),
        max(needs.values(), default=0),
        max(enables.values(), default=0),
        max(specificity.values(), default=0),
    )
    raw = {
        concept: (
            config.DIFFICULTY_DEPTH_WEIGHT * _ratio(depth.get(concept, 0), tops[0])
            + config.DIFFICULTY_NEEDS_WEIGHT * _ratio(needs[concept], tops[1])
            + config.DIFFICULTY_SPECIFICITY_WEIGHT * _ratio(specificity[concept], tops[3])
            - config.DIFFICULTY_ENABLES_WEIGHT * _ratio(enables[concept], tops[2])
        )
        for concept in concepts
    }
    return _rescale(raw)


# FUSIÓN, INVARIANTE Y NIVELES ---------------------------------------------------------------


def _judged_score(level: object) -> float | None:
    try:
        value = int(level)
    except (TypeError, ValueError):
        return None
    levels = config.DIFFICULTY_LEVELS
    value = min(max(value, 1), levels)
    return 0.0 if levels < 2 else (value - 1) / (levels - 1)


def blend(
    concepts: list[str],
    structural: dict[str, float],
    judgements: dict[str, object],
    llm_weight: float | None = None,
) -> dict[str, float]:
    alpha = config.DIFFICULTY_LLM_WEIGHT if llm_weight is None else llm_weight
    scores = {}
    for concept in concepts:
        base = structural.get(concept, 0.5)
        judged = _judged_score(judgements.get(concept))
        # Un concepto que el modelo no juzgó — porque no es etiquetable, o porque se lo saltó —
        # se queda con la estructura sola en lugar de con medio número inventado.
        scores[concept] = base if judged is None else alpha * judged + (1 - alpha) * base
    return scores


# LA INVARIANTE. Si A tiene a B como prerrequisito, A no puede exigir menos que B: dominar A
# supone dominar B. La mezcla puede violarlo — el modelo juzga concepto a concepto y la
# estructura penaliza a los troncales — y esto es lo que convierte una nota opinable en un
# número con una propiedad comprobable.
def enforce_monotonicity(
    scores: dict[str, float], concepts: list[str], pairs: list[tuple[str, str]]
) -> tuple[dict[str, float], int]:
    graph = _dag(concepts, pairs)
    fixed = dict(scores)
    raised = 0
    for node in reversed(list(nx.topological_sort(graph))):
        below = [fixed[s] for s in graph.successors(node) if s in fixed]
        if below and node in fixed and fixed[node] < max(below):
            fixed[node] = max(below)
            raised += 1
    return fixed, raised


def tier_for(score: float) -> int:
    return 1 + sum(1 for bound in config.DIFFICULTY_TIER_BOUNDARIES if score >= bound)


def calibrate(
    concepts: list[str],
    relations: list[list],
    schema,
    judgements: dict[str, object] | None = None,
    thresholds: dict[str, str] | None = None,
) -> dict:
    """Los dos señales, fundidas, con la invariante aplicada y repartidas en niveles."""
    judgements = judgements or {}
    thresholds = thresholds or {}

    structural = structural_scores(concepts, relations, schema)
    pairs = prerequisite_pairs(relations, schema.prerequisite)
    scores, raised = enforce_monotonicity(
        blend(concepts, structural, judgements), concepts, pairs
    )
    if raised:
        logger.info(
            f"{raised} concepto(s) subidos de nivel para no exigir menos que sus prerrequisitos"
        )

    entries = {}
    for concept in sorted(concepts):
        entry = {
            "tier": tier_for(scores[concept]),
            "score": round(scores[concept], 4),
            "structural": round(structural.get(concept, 0.5), 4),
        }
        judged = judgements.get(concept)
        if _judged_score(judged) is not None:
            entry["judged"] = int(judged)
        threshold = str(thresholds.get(concept) or "").strip()
        if threshold:
            entry["threshold"] = threshold
        entries[concept] = entry

    spread = Counter(entry["tier"] for entry in entries.values())
    logger.success(
        f"Dificultad calibrada: {len(entries)} concepto(s) — "
        + ", ".join(f"nivel {t}: {spread.get(t, 0)}" for t in range(1, config.DIFFICULTY_LEVELS + 1))
    )
    return {"concepts": entries}


# EL BANCO YA EXISTENTE ----------------------------------------------------------------------


# Un ítem exige lo que exige el más duro de los conceptos que hace practicar: bajar la media
# con los fáciles diría que un ejercicio de recursividad con bucles es medio fácil.
def item_tier(concepts: list[str], data: dict) -> int | None:
    tiers = [t for t in (tier_of(c, data) for c in concepts or []) if t is not None]
    return max(tiers) if tiers else None


# El otro medio de la pregunta: qué nivel se DERIVA para los ejercicios que ya están puestos.
# Informa, no sobreescribe — y por eso `field` es opcional y lo nombra quien llama: el nombre
# del campo de dificultad es del perfil de la instancia (`nivel_dificultad` aquí), y esta
# biblioteca no puede conocerlo sin atarse a un perfil concreto.
#
# Esto es además la medición que dice si todo lo anterior sirve: los niveles escritos a mano en
# el material docente son verdad-terreno gratis contra la que contrastar los pesos.
def bank_report(bank: dict, data: dict, field: str | None = None) -> dict:
    derived: dict[str, int] = {}
    untagged: list[str] = []
    for item_id, item in (bank or {}).items():
        tier = item_tier(item.get("concepts") or [], data)
        if tier is None:
            untagged.append(item_id)
        else:
            derived[item_id] = tier

    report = {
        "items": len(bank or {}),
        "derived": derived,
        "without_difficulty": sorted(untagged),
        "spread": dict(Counter(derived.values())),
    }
    if field is None:
        return report

    stored = {
        item_id: item.get(field)
        for item_id, item in (bank or {}).items()
        if item.get(field) is not None
    }
    report["stored"] = stored
    report["agreement"] = {
        item_id: {"stored": stored[item_id], "derived": derived[item_id]}
        for item_id in sorted(set(stored) & set(derived))
    }
    return report
