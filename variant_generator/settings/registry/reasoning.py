from dataclasses import dataclass

from ..types import Impact, Setting

GROUP = "Razonamiento"

_SHARED_DOC = """Si esta fase razona antes de contestar. `think` sigue siendo un booleano en el punto de
llamada y `THINK_EFFORT` decide cuánto razona; esto solo decide SI razona.

Una llamada con gramática (`format=`) no puede razonar en esta pila: la gramática se aplica
desde el primer token, el modelo nunca cierra el canal y la respuesta vuelve vacía. Por eso
encender el razonamiento en una fase que hoy va con gramática QUITA la gramática de esa
llamada y deja la forma de la respuesta en manos del analizador y de la reparación, que sí
conserva la suya. Apagarlo en una fase que hoy razona la deja sin gramática y a temperatura
determinista: se lee igual, lo que cambia es el juicio."""

_TRANSCRIBE_DOC = """Copiar una página que se tiene delante como imagen no es un juicio, y lo que sostiene la
fidelidad es la cláusula carácter a carácter del prompt, no la deliberación. Apagado por
defecto: cada página es una llamada, y razonar multiplica el coste de la fase más larga
del banco sin nada que medir a cambio."""

_EP_SCAN_DOC = """El rastreo lee fragmentos y señala modalidades candidatas con una gramática. Es una lectura,
no un juicio, y corre sobre cada fragmento del corpus; apagado por defecto."""

_EP_CONSOLIDATE_DOC = """La consolidación del perfil lee los hallazgos de todo el corpus y escribe la definición de las
modalidades: un juicio sobre un inventario cerrado, que es exactamente donde el razonamiento
ayuda. Antes de existir este ajuste la fase razonaba siempre que el modelo pudiera."""

_CONTEXT_DOC = """La síntesis del contexto de la materia va con gramática y sin razonar por la misma razón
que las descripciones: con el canal cerrado un modelo razonador delibera DENTRO de la
respuesta, y aquí eso se interpolaría en cada prompt del sistema como si fuera la materia.
Apagado por defecto."""

_EB_EXTRACT_DOC = """La extracción del banco transcribe ítems de un lote con la gramática del perfil, que es lo
que garantiza los campos. Es lectura y corre sobre cada lote; apagado por defecto."""

_KG_EXTRACT_DOC = """Leer los conceptos de un fragmento es lo que la gramática `EXTRACT_SCHEMA` acota y lo que
`clean` corrige después. Razonar aquí paga una deliberación por cada fragmento del corpus
para una lectura; apagado por defecto. `extract` sigue sin medirse con los prompts en
español."""

_KG_CLEAN_MERGE_DOC = """Decidir si dos nombres son el mismo concepto parece léxico y no lo es: «Lista» y «Listas
en Python» se fusionan, «Lista» y «Lista enlazada» no. Apagarlo abarata la limpieza, pero la
fusión equivocada se propaga a todas las relaciones del superviviente."""

_KG_CLEAN_DROP_DOC = """Medido, no supuesto: sin razonar el descarte es 6,8x más rápido, pero sobre 180 nodos ya
limpios pasó de 1 descarte a 20, llevándose «Cohesión», «El método de la Burbuja», «Else» y
«Error de compilación». La deliberación es lo que mantiene tímida esta pasada, y un concepto
descartado aquí desaparece del grafo para siempre. Apagarlo es aceptar esa pérdida a cambio
del tiempo."""

_KG_DOMAINS_DOC = """LA FASE QUE TUVO QUE RENUNCIAR AL RAZONAMIENTO, y está medido: pedida la partición del
inventario entero, el modelo enumeró dentro del canal de razonamiento durante 36 929
caracteres, llegó a su token de parada en el concepto 60 y devolvió una respuesta VACÍA
con `done_reason: "stop"`, indistinguible aguas arriba de una real — cada concepto habría
ido a «Sin clasificar» en silencio. Con gramática y sin razonar: 56 s en vez de 400 y 202
de 203 colocados. El prompt ya solo pide los nombres, pero la enumeración está a una
edición de distancia. Encenderlo es reabrir esa medición, no un ajuste fino."""

_KG_DOMAINS_LEFTOVERS_DOC = """Colocar conceptos sueltos en dominios ya fijados, por lotes pequeños; el fallo que repara es
«se olvidó de contestar», no «no supo decidir», y la gramática es lo que obliga a contestar
por cada uno. Apagado por defecto por la misma medición que `kg_domains`."""

_KG_LINK_DOC = """Ordenar prerrequisitos es la llamada más cara del constructor (443 s sobre el dominio mayor
del borrador de referencia, ~41 000 caracteres de deliberación a `low`) y también la que más
se nota: una relación de prerrequisito invertida intercambia «se da por sabido» con «aún no
se ha enseñado» en cada enunciado que el generador escriba después, y nada falla."""

_KG_TAGGABLE_DOC = """El fallo documentado de la revisión de etiquetabilidad es excluir DE MENOS, y los modelos
que no deliberan van en esa dirección (los MoE sin razonamiento excluyeron 23 de 73). Sobre
el borrador de referencia con razonamiento: 44 de 135 contra los 43 del borrador, 38 de ellos
los mismos conceptos, en 27,8 min. Apagarlo es rápido y deja etiquetas vagas en el corpus."""

_DESCRIPTION_DOC = """Las descripciones son la superficie de recuperación: lo que se escribe aquí se embebe. Con
el canal cerrado un modelo razonador delibera dentro de la respuesta, y el espacio de
trabajo de referencia guarda ~9 000 caracteres de borrador en inglés como descripción,
embebidos como prosa. Por eso va con gramática y apagado; encenderlo quita la gramática y
vuelve a abrir exactamente esa puerta."""

_CONCEPT_TAGGER_DOC = """El etiquetador hace una primera pasada con gramática y sin razonar; esto decide si, cuando
esa pasada no concluye (JSON inválido o rechaza a todos los candidatos), se reintenta una vez
razonando y sin gramática. Apagarlo quita la escalada: un ítem no concluyente pasa directo al
segundo `_resolve` sobre `TAGGER_FALLBACK_TOP_K`, que sigue siendo sin razonar."""

_ADMISSIBILITY_DOC = """El juez de admisibilidad contesta con una gramática derivada de los dueños de cada ranura,
y su respuesta se verifica contra esa misma lista antes de creerla. Corre en cada encargo,
entre el guardián y la generación; razonar aquí alarga cada generación por un juicio que
falla abierto de todos modos. Apagado por defecto."""

_DEFAULTS = {
    "exemplars_transcribe": (False, _TRANSCRIBE_DOC),
    "ep_scan": (False, _EP_SCAN_DOC),
    "ep_consolidate": (True, _EP_CONSOLIDATE_DOC),
    "ep_context": (False, _CONTEXT_DOC),
    "eb_extract": (False, _EB_EXTRACT_DOC),
    "kg_extract": (False, _KG_EXTRACT_DOC),
    "kg_clean_merge": (True, _KG_CLEAN_MERGE_DOC),
    "kg_clean_drop": (True, _KG_CLEAN_DROP_DOC),
    "kg_domains": (False, _KG_DOMAINS_DOC),
    "kg_domains_leftovers": (False, _KG_DOMAINS_LEFTOVERS_DOC),
    "kg_link_domain": (True, _KG_LINK_DOC),
    "kg_link_cross_domain": (True, _KG_LINK_DOC),
    "kg_taggable": (True, _KG_TAGGABLE_DOC),
    "kg_context": (False, _CONTEXT_DOC),
    "description_generation": (False, _DESCRIPTION_DOC),
    "concept_tagger": (True, _CONCEPT_TAGGER_DOC),
    "admissibility": (False, _ADMISSIBILITY_DOC),
}


def _toggle(phase: str) -> Setting:
    default, doc = _DEFAULTS[phase]
    return Setting(
        key=f"reasoning.phases.{phase}",
        name=f"THINK_{phase.upper()}",
        kind="bool",
        default=default,
        group=GROUP,
        impact=Impact.NONE,
        doc=doc + "\n\n" + _SHARED_DOC,
    )


SETTINGS: list[Setting] = [_toggle(phase) for phase in _DEFAULTS]


GRAMMAR = "grammar"
COMMISSION = "commission"
MODEL = "model"


@dataclass(frozen=True)
class Phase:
    key: str
    label: str
    model: str
    setting: str | None = None
    fixed: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Lane:
    key: str
    label: str
    phases: tuple[Phase, ...]


def _switch(key: str, label: str, note: str = "") -> Phase:
    return Phase(
        key=key,
        label=label,
        model=f"models.phases.{key}",
        setting=f"reasoning.phases.{key}",
        note=note,
    )


PIPELINE: tuple[Lane, ...] = (
    Lane(
        "profile",
        "Perfil de ejemplares",
        (
            _switch(
                "exemplars_transcribe",
                "Transcripción",
                "Lee páginas como imagen; compartida con el banco.",
            ),
            _switch("ep_scan", "Escaneo"),
            _switch("ep_consolidate", "Consolidación"),
            _switch("ep_context", "Contexto"),
        ),
    ),
    Lane(
        "graph",
        "Grafo de conocimiento",
        (
            _switch("kg_extract", "Extracción"),
            _switch("kg_clean_merge", "Fusión"),
            _switch("kg_clean_drop", "Descarte"),
            _switch(
                "kg_domains",
                "Dominios",
                "Razonando devolvió una respuesta vacía sobre 203 conceptos.",
            ),
            _switch("kg_domains_leftovers", "Sobrantes"),
            _switch("kg_link_domain", "Enlace interno"),
            _switch("kg_link_cross_domain", "Enlace global"),
            _switch("kg_context", "Contexto"),
            _switch("kg_taggable", "Etiquetabilidad", "Trabajo aparte; necesita el perfil aprobado."),
        ),
    ),
    Lane(
        "bank",
        "Banco de ejemplares",
        (
            _switch("eb_extract", "Extracción"),
            _switch(
                "concept_tagger",
                "Etiquetado",
                "Primera pasada con gramática; el interruptor decide la escalada.",
            ),
        ),
    ),
    Lane(
        "run",
        "Generación",
        (
            _switch(
                "description_generation",
                "Descripciones",
                "Lo que deliberara quedaría embebido como prosa.",
            ),
            Phase(
                "guardrail",
                "Guardián",
                "models.guardrail",
                fixed=MODEL,
                note="Un clasificador con 4096 de contexto; no razona.",
            ),
            _switch("admissibility", "Admisibilidad"),
            Phase(
                "variant_generation",
                "Variante",
                "models.phases.variant_generation",
                fixed=COMMISSION,
                note="Lo decide cada encargo; el estudio lo mide en ambas posiciones.",
            ),
            Phase(
                "repair",
                "Reparación",
                "models.phases.repair",
                fixed=GRAMMAR,
                note="La gramática ES la reparación: sin ella no puede corregir un esquema.",
            ),
        ),
    ),
)
