import pytest

from variatio import admissibility
from variatio.core import paths
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.instance.knowledge_graph import KnowledgeGraph
from variatio.stages import _artifacts

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


@pytest.fixture(scope="module")
def instance():
    ws = paths.default_workspace()
    graph = KnowledgeGraph(_artifacts.knowledge_graph_path(ws))
    profile = ExemplarsProfile(_artifacts.exemplars_profile_path(ws))
    context = _artifacts.load_content_context(ws)
    found = admissibility.owners(graph, profile.item_type(ITEM_TYPE), profile, context, TARGETS)
    return found, context.prompt_block()


@pytest.mark.model
@pytest.mark.parametrize("text", ADMISSIBLE)
def test_a_legitimate_scenario_is_never_rejected(instance, text):
    owners, block = instance
    ruling = admissibility.screen(text, owners, TARGETS, block)
    assert ruling.checked, "el juez devolvió una respuesta ilegible"
    assert ruling.ok, f"rechazada por {ruling.blocked[0].owner.key} ({ruling.blocked[0].term})"


@pytest.mark.model
@pytest.mark.parametrize("text", UNOWNED)
def test_a_request_no_control_owns_is_never_blocked(instance, text):
    owners, block = instance
    ruling = admissibility.screen(text, owners, TARGETS, block)
    assert ruling.ok, f"rechazada por {ruling.blocked[0].owner.key} ({ruling.blocked[0].term})"


@pytest.mark.model
def test_every_inadmissible_request_is_caught(instance):
    owners, block = instance
    caught = []
    for text, expected in INADMISSIBLE:
        ruling = admissibility.screen(text, owners, TARGETS, block)
        if not ruling.ok and ruling.blocked[0].owner.key == expected:
            caught.append(text)
    assert len(caught) == len(INADMISSIBLE), (
        f"solo {len(caught)} de {len(INADMISSIBLE)}: "
        f"faltaron {[t for t, _ in INADMISSIBLE if t not in caught]}"
    )
