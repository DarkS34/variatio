import os

import pytest

from variatio import admissibility
from variatio.core import paths
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.instance.knowledge_graph import KnowledgeGraph
from variatio.stages import _artifacts

from ..conftest import ES

ITEM_TYPE = "escritura_codigo"
TARGETS = ["Recursividad"]

ADMISSIBLE = [
    "que vaya de una lista de la compra en una tienda de barrio",
    "que el contexto sea una panadería y los datos sean sencillos",
    "que el enunciado incluya una tabla de datos de ventas",
    "que trate de un análisis de las ventas de una cafetería",
    "ambiéntalo en un gimnasio, con un ejemplo de entrada y salida",
    "que el enunciado sea breve y con números enteros pequeños",
    "que vaya de la cadena de montaje de una fábrica",
    "sitúalo en una biblioteca que presta libros a sus socios",
]

# The reference profile declares no `decided_by: "user"` field, so nothing on the screen
# owns the difficulty and asking for it invades nobody. They are apart from ADMISSIBLE
# because no slot describes them either: the claim is only that they are not blocked, and
# a ruling that types nothing is the honest answer. In an instance that does declare such
# a field, these three belong in INADMISSIBLE under `field:<name>`.
UNOWNED = [
    "genérame una variante muy difícil",
    "que el nivel de dificultad sea básico",
    "que sea de dificultad avanzada",
]

INADMISSIBLE = [
    ("que practique también las funciones", "concepts"),
    ("hazlo en inglés", "context"),
    ("que sea un ejercicio de análisis de código", "item_type"),
    ("que sea de nivel universitario avanzado", "context"),
    ("que sea de física en vez de programación", "context"),
    ("que practique variables y bucles", "concepts"),
]


# WHICH INSTANCE THE TWELVE MEASUREMENTS ARE TAKEN AGAINST, and it is named rather than
# resolved. They used to call `paths.default_workspace()`, which was deleted on 2026-08-26
# with the whole idea of a default instance — so from that day these twelve errored at
# setup with an `AttributeError` instead of running, and being deselected by default
# nobody saw it. The slug is overridable because `workspaces/` is gitignored: a checkout
# has whatever its owner built, under whatever they called it.
WORKSPACE = os.environ.get("VARIATIO_MODEL_WORKSPACE", "default")


@pytest.fixture(scope="module")
def instance():
    """The owners of the reference instance, or a skip saying what is missing.

    Every precondition is checked here rather than left to blow up inside a test: these
    are measurements of a MODEL against a real instance, so «this checkout does not have
    that instance» is not a failure of the judge and must not read as one.
    """
    ws = paths.workspace(WORKSPACE)
    graph_path = _artifacts.knowledge_graph_path(ws)
    profile_path = _artifacts.exemplars_profile_path(ws)
    if graph_path is None or profile_path is None:
        pytest.skip(
            f"«{WORKSPACE}» no tiene grafo y perfil construidos; "
            "usa VARIATIO_MODEL_WORKSPACE para medir contra otra asignatura"
        )
    profile = ExemplarsProfile(profile_path)
    if ITEM_TYPE not in profile.item_types:
        pytest.skip(f"«{WORKSPACE}» no declara la modalidad «{ITEM_TYPE}»")
    graph = KnowledgeGraph(graph_path)
    absent = [c for c in TARGETS if c not in graph.all_concepts]
    if absent:
        pytest.skip(f"«{WORKSPACE}» no tiene el concepto {absent[0]!r}")
    context = _artifacts.load_content_context(ws)
    found = admissibility.owners(graph, profile.item_type(ITEM_TYPE), profile, context, TARGETS)
    return found, context.prompt_block()


@pytest.mark.model
@pytest.mark.parametrize("text", ADMISSIBLE)
def test_a_legitimate_scenario_is_never_rejected(instance, text):
    owners, block = instance
    ruling = admissibility.screen(text, owners, TARGETS, ES, block)
    assert ruling.checked, "el juez devolvió una respuesta ilegible"
    assert ruling.ok, f"rechazada por {ruling.blocked[0].owner.key} ({ruling.blocked[0].term})"


@pytest.mark.model
@pytest.mark.parametrize("text", UNOWNED)
def test_a_request_no_control_owns_is_never_blocked(instance, text):
    owners, block = instance
    ruling = admissibility.screen(text, owners, TARGETS, ES, block)
    assert ruling.ok, f"rechazada por {ruling.blocked[0].owner.key} ({ruling.blocked[0].term})"


@pytest.mark.model
def test_every_inadmissible_request_is_caught(instance):
    owners, block = instance
    caught = []
    for text, expected in INADMISSIBLE:
        ruling = admissibility.screen(text, owners, TARGETS, ES, block)
        if not ruling.ok and ruling.blocked[0].owner.key == expected:
            caught.append(text)
    assert len(caught) == len(INADMISSIBLE), (
        f"solo {len(caught)} de {len(INADMISSIBLE)}: "
        f"faltaron {[t for t, _ in INADMISSIBLE if t not in caught]}"
    )
