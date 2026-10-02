"""The "Muestreo" settings of every model call: its temperature, its top-k and its top-p.

One triple per phase of the pipeline, declared from `PIPELINE` itself so a phase added
there gets its triple without a second edit. Empty means inherited, which is what every
call did before the triple existed: a phase reading with another phase's model takes that
phase's values first (`derived`), and what is still empty is decided per call
(`inference.sampling`) — the temperature by whether the call reasons this time, top-k and
top-p by the model, by not being sent.
"""

from ..types import Impact, Setting
from . import inference
from .reasoning import PIPELINE

GROUP = "Muestreo"
PARAMS = ("temperature", "top_k", "top_p")

_INHERITED_TEMPERATURE_DOC = """La temperatura de esta llamada. Vacía, hereda la de la pareja de juicio: la de razonamiento
(`sampling.temperature_reasoning`) cuando la llamada razona esta vez y la determinista
cuando no, que es lo que hacía cada llamada antes de tener la suya. Fijarla aquí la
desata de su interruptor de razonamiento: encenderlo o apagarlo ya no la mueve.

Sin medir por fase. En las tres llamadas de la transcripción forma parte de la huella de
la página o de la imagen, así que cambiarla vuelve a leer lo ya transcrito."""

_TOP_K_DOC = """Entre cuántos tokens candidatos, los más probables, elige el muestreador en cada paso.
Vacío no se envía y decide el modelo (su Modelfile, en Ollama). Cerebras no documenta
`top_k`: en una llamada servida allí se descarta con un aviso, y el resto del muestreo
viaja igual.

Sin medir. En las tres llamadas de la transcripción entra en la huella de la página o de
la imagen solo cuando tiene valor: dejarlo vacío no caduca nada de lo ya leído."""

_TOP_P_DOC = """Qué masa de probabilidad acumulada conserva el muestreador (núcleo): con 0.9 descarta la
cola de tokens que suma el 10 % restante. Vacío no se envía y decide el modelo o el
proveedor.

Sin medir. En las tres llamadas de la transcripción entra en la huella de la página o de
la imagen solo cuando tiene valor: dejarlo vacío no caduca nada de lo ya leído."""

_TRANSCRIBE_DOC = """Transcribir es copiar, no escribir: a la temperatura por defecto de Ollama la misma
página volvió con `a = 99` e `if a < 0 : break` sacados de su `while True:`, lo que cambia
en silencio lo que pide el ejercicio. Fijada a 0 por eso.

Sigue siendo un valor propio en vez de heredar `TEMPERATURE_DETERMINISTIC`, aunque tenga el
mismo valor y por la misma razón: esta forma parte de la huella de la caché de páginas
(`source_docs/pages.py`), así que cambiarla vuelve a transcribir todas las páginas de
todos los corpus. Heredarla haría que esa consecuencia siguiera a una edición hecha
pensando en otra cosa. Las imágenes de un Word o un PowerPoint la heredan mientras su
propia temperatura esté vacía, como heredan el modelo."""

_GENERATION_DOC = """La única llamada que redacta de verdad, y aun así baja: lo que hace que un ejercicio
merezca guardarse es que obedezca su encargo, y la temperatura es exactamente lo que compra
desviarse de él. La variedad dentro de una tanda se paga en el PROMPT, que enseña al modelo
lo que ya ha escrito. Valor propio y nunca heredado: no es un juicio, así que la pareja de
juicio no la describe. Las dos propuestas locales de la evaluación escriben con ella, y la
comercial recibe esta misma temperatura."""

_REPAIR_DOC = """Valor propio aunque coincida con la temperatura de razonamiento, porque no se movería con
ella: reparar es un bucle de REINTENTO, y un reintento a 0 no es un reintento. El prompt del
intento N+1 es la salida del intento N, así que un modelo voraz reconstruye el prompt
idéntico y escribe la respuesta idéntica — el presupuesto entero gastado en una réplica
byte a byte, que es el fallo que `parse_with_repair` documenta haber pagado una vez."""

# The phases whose temperature is a value of their own and never inherited: what they
# write is not a judgement, so the judging pair does not describe them. Each keeps the
# `config` name it had before the triple existed.
_OWN_TEMPERATURE = {
    "transcribe": (0.0, "TRANSCRIBE_TEMPERATURE", _TRANSCRIBE_DOC),
    "variant_generation": (0.3, "TEMPERATURE_GENERATION", _GENERATION_DOC),
    "repair": (0.2, "TEMPERATURE_REPAIR", _REPAIR_DOC),
}


def _declare(phase) -> list[Setting]:
    """Declare a pipeline phase's triple, staged like the model setting it steers."""
    stages = _MODELS[phase.model].stages
    if phase.key not in _OWN_TEMPERATURE:
        return phase_sampling(phase.key, stages)
    temperature, name, doc = _OWN_TEMPERATURE[phase.key]
    return phase_sampling(phase.key, stages, temperature, name, doc)


def phase_sampling(
    phase: str,
    stages: tuple[str, ...],
    temperature: float | None = None,
    name: str = "",
    temperature_doc: str = _INHERITED_TEMPERATURE_DOC,
) -> list[Setting]:
    """Declare one phase's sampling triple, empty unless the phase brings its temperature.

    Engine-scoped like the model it steers: the right sampling belongs to a model, and
    switching engine switches every model at once.
    """
    common = {"group": GROUP, "stages": stages, "phase": phase, "impact": Impact.NONE}
    return [
        Setting(
            key=f"sampling.phases.{phase}.temperature",
            name=name,
            kind="float",
            default=temperature,
            nullable=temperature is None,
            scope="engine",
            minimum=0.0,
            maximum=2.0,
            doc=temperature_doc,
            **common,
        ),
        Setting(
            key=f"sampling.phases.{phase}.top_k",
            name="",
            kind="int",
            default=None,
            nullable=True,
            scope="engine",
            minimum=1,
            doc=_TOP_K_DOC,
            **common,
        ),
        Setting(
            key=f"sampling.phases.{phase}.top_p",
            name="",
            kind="float",
            default=None,
            nullable=True,
            scope="engine",
            minimum=0.0,
            maximum=1.0,
            doc=_TOP_P_DOC,
            **common,
        ),
    ]


_MODELS = {setting.key: setting for setting in inference.SETTINGS}

SETTINGS: list[Setting] = [
    setting for lane in PIPELINE for phase in lane.phases for setting in _declare(phase)
]
