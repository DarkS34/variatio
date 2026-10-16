"""The free chat's settings and its lane, declared beside the code that reads them.

`variatio/settings/registry/__init__.py` picks these up through an optional import. Nothing
here may import `variatio.config`: this module is read while the registry that `config` is
built from is still being assembled. The chat is no optional function of the administrator's,
so its screen is a stage of «Configuración», after the tutor's.
"""

from variatio.settings.registry.reasoning import Lane, Phase
from variatio.settings.registry.sampling import PARAMS, phase_sampling
from variatio.settings.types import Impact, Setting

STAGE = "chat"
GROUP = "Chat libre"

# One call per turn. The guardrail it runs first is the generation's call, read through
# `READS` and not declared again.
LANE = Lane(
    STAGE,
    "Chat libre",
    (
        Phase(
            "chat_reply",
            "Respuesta",
            "chat.models.reply",
            setting="chat.reasoning.reply",
            effort="chat.effort.reply",
            note="Contesta al alumno: explica, resuelve y escribe código dentro de la asignatura.",
        ),
    ),
)

# The setting that names the model of the call: it gets the context cap and the protection
# against deletion that every phase model has.
MODEL_KEYS = ("chat.models.reply",)

# The pipeline's settings a turn reads too: the guardrail and the offered models it writes
# with by default.
READS = (
    "models.guardrail",
    "context_window.guardrail",
    "generation.guardrail_criteria",
    "generation.models",
    "context_window.overrides",
    "sampling.temperature_deterministic",
    "sampling.temperature_reasoning",
    "reasoning.default_effort",
    *(f"sampling.phases.guardrail.{param}" for param in PARAMS),
)


def _setting(key: str, kind: str, default, doc: str, phase: str | None = None, **extra) -> Setting:
    """Declare one of the chat's settings."""
    return Setting(
        key=f"chat.{key}",
        name="",
        kind=kind,
        default=default,
        group=GROUP,
        stages=(STAGE,),
        phase=phase,
        impact=Impact.NONE,
        doc=doc,
        **extra,
    )


SETTINGS: list[Setting] = [
    _setting(
        "models.reply",
        "str",
        None,
        """QUÉ MODELO ESCRIBE LAS RESPUESTAS DEL CHAT LIBRE. Vacío significa «el mismo que genera
ejercicios»: el primero de `generation.models`, que ya tiene su ventana de contexto y está
protegido contra el borrado (lo pidió el usuario el 2026-10-14). Con la configuración de hoy,
el tutor y el chat usan ese mismo modelo. Un nombre propio recibe la misma ventana
(`context_window.overrides`) y la misma protección. Con ámbito de motor, como toda elección de
modelo.""",
        phase="chat_reply",
        nullable=True,
        scope="engine",
    ),
    _setting(
        "reasoning.reply",
        "bool",
        False,
        """Si el chat razona antes de contestar. Apagado por defecto porque es una conversación: cada
turno espera a la respuesta entera, y en la GPU local la deliberación añade decenas de segundos.
Sin medir.""",
        phase="chat_reply",
        scope="engine",
    ),
    _setting(
        "effort.reply",
        "str",
        "low",
        """Cuánto razona la respuesta cuando su interruptor está encendido; con él apagado no pinta
nada.""",
        phase="chat_reply",
        scope="engine",
        choices=("low", "medium", "high", "max"),
    ),
    _setting(
        "message_max_chars",
        "int",
        12000,
        """Cuántos caracteres puede tener un mensaje. La pantalla no lo muestra: es un tope de
seguridad, como el del tutor, y da para un enunciado y un programa largo pegados.""",
        minimum=200,
    ),
    _setting(
        "daily_messages",
        "int",
        None,
        """Cuántos mensajes puede enviar una cuenta al chat libre en un día, sumando todas sus
asignaturas. Vacío es sin límite. Se cuenta aparte del tutor: cada función tiene su propio
tope. Solo cuenta el mensaje que entra en la cola, también cuando se pide la respuesta otra
vez. El día es el de UTC. Sin medir.""",
        nullable=True,
        minimum=1,
    ),
    _setting(
        "history_turns",
        "int",
        8,
        """Cuántos intercambios anteriores (mensaje y respuesta) entran en el prompt de cada turno.
Lo anterior sigue guardado en la conversación. Sin medir.""",
        phase="chat_reply",
        minimum=0,
    ),
    _setting(
        "reply_max_tokens",
        "int",
        2048,
        """El techo de salida de la respuesta cuando no razona (`num_predict` en Ollama,
`max_completion_tokens` en Cerebras). Más alto que el del tutor, porque el chat escribe
soluciones y programas enteros. Con el razonamiento encendido no se aplica. Sin medir.""",
        phase="chat_reply",
        minimum=64,
    ),
    *phase_sampling(
        "chat_reply",
        (STAGE,),
        0.4,
        temperature_doc="""La temperatura de la respuesta del chat. Valor propio, como el del tutor: baja, para que
se ciña a la asignatura y a lo que se pide; no a cero, para que dos turnos seguidos no repitan
la misma fórmula. Sin medir.""",
    ),
]
