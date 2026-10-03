"""The tutor's settings and its lane, declared beside the code that reads them.

`variatio/settings/registry/__init__.py` picks these up through an optional import — the one
place the pipeline names the tutor. Nothing here may import `variatio.config`: this module is
read while the registry that `config` is built from is still being assembled.
"""

from variatio.settings.registry.reasoning import GRAMMAR, Lane, Phase
from variatio.settings.registry.sampling import PARAMS, phase_sampling
from variatio.settings.types import Impact, Setting

STAGE = "tutoring"
GROUP = "Tutor"

# The tutor's three model calls, drawn on its own configuration screen. The guardrail it
# runs first is the generation's call, read through `READS` and not declared again.
LANE = Lane(
    STAGE,
    "Tutor",
    (
        Phase(
            "tutor_classify",
            "Clasificación",
            "tutor.models.classify",
            fixed=GRAMMAR,
            note="Decide qué tipo de mensaje ha escrito el alumno y, una vez, el título de la conversación.",
        ),
        Phase(
            "tutor_reply",
            "Respuesta",
            "tutor.models.reply",
            setting="tutor.reasoning.reply",
            effort="tutor.effort.reply",
            note="Escribe la respuesta socrática a partir de la ficha del turno.",
        ),
        Phase(
            "tutor_criteria",
            "Criterios",
            "tutor.models.criteria",
            setting="tutor.reasoning.criteria",
            effort="tutor.effort.criteria",
            note="Redacta los criterios de la asignatura, una llamada por unidad del temario.",
        ),
    ),
)

# The settings that name the model of a call: they get the context cap and the protection
# against deletion that every phase model has.
MODEL_KEYS = ("tutor.models.reply", "tutor.models.classify", "tutor.models.criteria")

# The pipeline's settings a turn reads too: the guardrail, the embedder and the matching of
# names, the offered models a turn writes with by default, and the repair of a broken JSON.
READS = (
    "models.guardrail",
    "context_window.guardrail",
    "generation.guardrail_criteria",
    "generation.models",
    "context_window.overrides",
    "models.embedding",
    "context_window.embedding",
    "retrieval.query_prefix",
    "retrieval.document_prefix",
    "retrieval.batch_size",
    "retrieval.similarity_threshold",
    "retrieval.description_weight",
    "builders.kg_min_mention_length",
    "builders.kg_mention_inflection_slack",
    "builders.kg_plural_suffixes",
    "builders.kg_min_leader_runs",
    "models.phases.repair",
    "generation.max_json_repair_tries",
    "sampling.temperature_deterministic",
    "sampling.temperature_reasoning",
    "reasoning.default_effort",
    *(f"sampling.phases.{phase}.{param}" for phase in ("guardrail", "repair") for param in PARAMS),
)

_MODEL_DOC = """Vacío significa «el mismo que genera ejercicios»: el primero de `generation.models`, que
ya tiene su ventana de contexto y está protegido contra el borrado. Un nombre propio recibe la
misma ventana (`context_window.overrides`) y la misma protección. Con ámbito de motor, como
toda elección de modelo."""

_EFFORT_DOC = """Cuánto razona esta llamada cuando su interruptor está encendido; con él apagado no pinta
nada. «low» por la misma medición que los esfuerzos del resto del sistema: el nivel mueve el
techo de la deliberación y no su suelo."""


def _model(phase: str, doc: str) -> Setting:
    """Declare the model of one of the tutor's calls."""
    return Setting(
        key=f"tutor.models.{phase}",
        name="",
        kind="str",
        default=None,
        nullable=True,
        group=GROUP,
        stages=(STAGE,),
        phase=f"tutor_{phase}",
        scope="engine",
        impact=Impact.NONE,
        doc=doc + "\n\n" + _MODEL_DOC,
    )


def _switch(phase: str, default: bool, doc: str) -> Setting:
    """Declare whether one of the tutor's calls reasons."""
    return Setting(
        key=f"tutor.reasoning.{phase}",
        name="",
        kind="bool",
        default=default,
        group=GROUP,
        stages=(STAGE,),
        phase=f"tutor_{phase}",
        scope="engine",
        impact=Impact.NONE,
        doc=doc,
    )


def _effort(phase: str) -> Setting:
    """Declare how much one of the tutor's calls reasons when it does."""
    return Setting(
        key=f"tutor.effort.{phase}",
        name="",
        kind="str",
        default="low",
        group=GROUP,
        stages=(STAGE,),
        phase=f"tutor_{phase}",
        scope="engine",
        impact=Impact.NONE,
        choices=("low", "medium", "high", "max"),
        doc=_EFFORT_DOC,
    )


def _number(key: str, kind: str, default, doc: str, phase: str | None = None, **bounds) -> Setting:
    """Declare one of the tutor's numeric knobs."""
    return Setting(
        key=f"tutor.{key}",
        name="",
        kind=kind,
        default=default,
        group=GROUP,
        stages=(STAGE,),
        phase=phase,
        impact=Impact.NONE,
        doc=doc,
        **bounds,
    )


SETTINGS: list[Setting] = [
    _model(
        "reply",
        """QUÉ MODELO ESCRIBE LAS RESPUESTAS DEL TUTOR. Lo fija la instalación: el alumno no elige
modelo en ningún sitio.""",
    ),
    _switch(
        "reply",
        False,
        """Si el tutor razona antes de contestar. Apagado por defecto porque es una conversación:
cada turno espera a la respuesta entera, y en la GPU local la deliberación añade decenas de
segundos por turno. Las comprobaciones del sistema (pregunta, código, copia de los apuntes,
conceptos posteriores) se aplican igual con él encendido o apagado. Sin medir.""",
    ),
    _effort("reply"),
    _model(
        "classify",
        """QUÉ MODELO DECIDE EL TIPO DE MENSAJE: duda de teoría, ayuda con un enunciado, intento propio,
petición de la solución, saludo, consulta administrativa o pregunta ajena a la asignatura.
Contesta con gramática y sin razonar. Vacío usa el modelo de la respuesta, que es el que la
GPU ya tiene cargado para ese mismo turno.""",
    ),
    _model(
        "criteria",
        """QUÉ MODELO REDACTA LOS CRITERIOS DE LA ASIGNATURA a partir de los apuntes, el temario y las
soluciones del banco. Vacío usa el modelo de la respuesta.""",
    ),
    _switch(
        "criteria",
        False,
        """Si la redacción de los criterios razona. Apagado por defecto, como el resto de las lecturas
acotadas del sistema: con gramática el modelo solo puede citar pasajes y conceptos que existen.
Encenderlo quita la gramática y deja la forma en manos del analizador y de la reparación.""",
    ),
    _effort("criteria"),
    _number(
        "message_max_chars",
        "int",
        12000,
        """Cuántos caracteres puede tener un mensaje del alumno. La pantalla no lo muestra: es un tope
de seguridad, no un límite de escritura, y da para un enunciado y un programa largo pegados.
Más largo se rechaza antes de llegar a la cola, porque ocho intercambios así ya llenarían
buena parte de la ventana de contexto.""",
        minimum=200,
    ),
    _number(
        "history_turns",
        "int",
        8,
        """Cuántos intercambios anteriores (mensaje del alumno y respuesta del tutor) entran en el prompt
de cada turno. Lo anterior sigue guardado en la conversación; el foco y lo ya comprobado viajan
aparte, en la ficha, así que no se pierden al salir de la ventana. Sin medir.""",
        phase="tutor_reply",
        minimum=0,
    ),
    _number(
        "reply_max_tokens",
        "int",
        1024,
        """El techo de salida de la respuesta cuando no razona (`num_predict` en Ollama,
`max_completion_tokens` en Cerebras). Una respuesta socrática son unas líneas y una o dos
preguntas; el techo es lo que impide que un modelo que no se para escriba la solución entera.
Con el razonamiento encendido no se aplica, porque la deliberación cuenta contra el mismo
techo.""",
        phase="tutor_reply",
        minimum=64,
    ),
    _number(
        "max_questions",
        "int",
        3,
        """Cuántas preguntas puede hacer una respuesta como mucho. Las instrucciones del tutor piden
dos o tres bien elegidas y no un interrogatorio. Una respuesta sin ninguna pregunta tampoco
pasa la comprobación.""",
        phase="tutor_reply",
        minimum=1,
    ),
    _number(
        "max_code_lines",
        "int",
        3,
        """Cuántas líneas de código puede llevar una respuesta, contadas dentro de los bloques de
código. Bastan para citar una línea del alumno y preguntar por ella; un programa que funcione
no cabe. Cero prohíbe cualquier bloque de código.""",
        phase="tutor_reply",
        minimum=0,
    ),
    _number(
        "copy_max_words",
        "int",
        20,
        """Cuántas palabras seguidas puede compartir una respuesta con un pasaje de los apuntes que
llevaba su ficha. Más es copiar el material en vez de remitir a él, y la respuesta se repite.
Sin medir.""",
        phase="tutor_reply",
        minimum=5,
    ),
    _number(
        "passages_top_k",
        "int",
        3,
        """Cuántos pasajes de los apuntes, buscados por parecido con la pregunta, entran en la ficha
de una duda de teoría, además de los pasajes anclados de los conceptos del foco. Cero apaga la
búsqueda.""",
        minimum=0,
    ),
    _number(
        "passage_threshold",
        "float",
        0.5,
        """Desde qué parecido coseno entra un pasaje de los apuntes en la ficha. Por debajo, el pasaje
no habla de lo que se pregunta y llenaría la ficha de ruido. Medido sobre seis mensajes de la
asignatura de prueba: una pregunta de teoría encuentra sus pasajes entre 0,72 y 0,77 y un
ejercicio entre 0,53 y 0,60, mientras que un saludo no pasa de 0,45 y una pregunta ajena a la
asignatura de 0,33.""",
        minimum=0.0,
        maximum=1.0,
    ),
    _number(
        "passage_chars",
        "int",
        1200,
        """De cuántos caracteres son los pasajes en que se cortan los apuntes para buscar en ellos.
Cambiarlo vuelve a cortar y a embeber los apuntes en el turno siguiente.""",
        minimum=200,
    ),
    _number(
        "anchors_per_concept",
        "int",
        2,
        """Cuántos pasajes anclados de cada concepto del foco entran en la ficha. El grafo guarda
hasta tres por concepto.""",
        minimum=0,
    ),
    _number(
        "bank_match_threshold",
        "float",
        0.85,
        """Desde qué parecido un mensaje ES un ejercicio del banco: entonces los conceptos del foco
salen de las etiquetas de ese ejercicio y no de la búsqueda. Se compara por el lado del
documento, el mismo en que se embebió el banco. Medido en la asignatura de prueba: el
enunciado pegado tal cual da 1,0 y con una frase delante 0,97; parafraseado, 0,82; una
petición sin relación, 0,70.""",
        minimum=0.0,
        maximum=1.0,
    ),
    _number(
        "focus_threshold",
        "float",
        0.55,
        """Desde qué parecido con un concepto fija un mensaje el foco de la conversación. Más alto que
el del temario (`retrieval.similarity_threshold`, 0,40), porque aquí un mensaje es una frase y
no un ejercicio entero: medido en la asignatura de prueba, las preguntas de contenido dan
entre 0,61 y 0,66 con su mejor concepto, y un saludo llega a 0,49 con uno cualquiera.""",
        minimum=0.0,
        maximum=1.0,
    ),
    _number(
        "focus_margin",
        "float",
        0.05,
        """Cuánto tiene que superar un concepto nuevo al foco actual en un mensaje para que el foco
cambie. Sin margen, cualquier frase corta («no lo entiendo») movería la conversación a otro
concepto. Sin medir.""",
        minimum=0.0,
        maximum=1.0,
    ),
    _number(
        "criteria_max_chars",
        "int",
        3000,
        """Cuántos caracteres de criterios docentes entran en la ficha de un turno: los generales
primero, después los de la unidad del foco y antes los de sus conceptos.""",
        phase="tutor_reply",
        minimum=200,
    ),
    _number(
        "criteria_evidence_chars",
        "int",
        14000,
        """Cuántos caracteres de los apuntes de una unidad lee cada llamada que redacta sus criterios.
Entran primero los párrafos que mandan, prohíben o avisan de un error. Sin medir.""",
        phase="tutor_criteria",
        minimum=1000,
    ),
    _number(
        "criteria_per_unit",
        "int",
        5,
        """Cuántos criterios puede proponer como mucho la llamada de cada unidad. La gramática lo
impone (`maxItems`) y el prompt pide los más importantes: sin techo, un modelo con gramática
puede seguir añadiendo criterios hasta llenar la ventana. Con diez, la redacción de `demo`
dio entre seis y nueve por unidad, largos y difíciles de revisar; cinco es lo que un docente
lee de una vez.""",
        phase="tutor_criteria",
        minimum=1,
    ),
    _number(
        "criteria_max_tokens",
        "int",
        4096,
        """El techo de salida de cada llamada que redacta criterios (`num_predict` en Ollama). Diez
criterios con sus citas caben de sobra; el techo corta una respuesta que no termina. Con el
razonamiento encendido no se aplica, porque la deliberación cuenta contra el mismo techo.""",
        phase="tutor_criteria",
        minimum=256,
    ),
    _number(
        "criteria_solutions",
        "int",
        6,
        """Cuántas soluciones del banco de cada unidad lee esa misma llamada, para reconocer las
convenciones que el docente sigue en todas.""",
        phase="tutor_criteria",
        minimum=0,
    ),
    *phase_sampling(
        "tutor_reply",
        (STAGE,),
        0.4,
        temperature_doc="""La temperatura de la respuesta del tutor. Valor propio y nunca heredado: escribir una
pregunta no es un juicio. Baja, para que obedezca su método; no a cero, para que dos turnos
seguidos no repitan la misma fórmula. Sin medir.""",
    ),
    *phase_sampling("tutor_classify", (STAGE,)),
    *phase_sampling("tutor_criteria", (STAGE,)),
]
