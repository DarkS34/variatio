"""The «Registro» settings: the log level and the third-party logger that is silenced."""

from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(key="logging.level", name="LOG_LEVEL", kind="str", default="INFO",
            group="Registro", impact=Impact.NONE, env="VARIATIO_LOG_LEVEL",
            choices=("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"),
            doc="""El detalle por elemento (un concepto, un ítem, un fragmento) se registra en DEBUG y
queda fuera del registro: la barra de progreso ya lo dibuja, y un banco de 150 ítems
o un grafo de 350 conceptos lo desbordarían. VARIATIO_LOG_LEVEL=DEBUG lo devuelve.

Cambiarlo en caliente afecta a los sumideros que lo releen; el nivel con el que arrancó
el proceso no se puede deshacer sin reiniciar."""),
    Setting(key="logging.noisy_loggers", name="NOISY_LOGGERS", kind="list[str]",
            default=["docling"],
            group="Registro", impact=Impact.LOCKED, editable=False,
            doc="""`variatio/__init__.py` lo lee por nombre en tiempo de importación
(`from .config import LOG_LEVEL, NOISY_LOGGERS`) para configurar
loguru una sola vez. Reescribir el atributo después no reconfigura nada, así que
ofrecerlo como editable en caliente sería una mentira que la pantalla contaría.

Era `docling, docling_core, docling_ibm_models, PIL` hasta el 2026-09-05, cuando se midió
qué emitía cada uno: los 22 documentos Office de la instalación, por la ruta real (con el
rasterizado de metaficheros delante), con los filtros deshechos y un handler espía en la
raíz. Solo `docling` dice algo que llegue a imprimirse — 27 WARNING de
`docling.backend.msword_backend` en 19 de los 22, todos «image cannot be loaded by
Pillow», que son los logos de cabecera que el markdown no lleva. `docling_core` y
`docling_ibm_models` no emitieron nada en ningún nivel (el segundo es del pipeline de PDF,
y ningún PDF pasa por Docling desde el 2026-08-27) y `PIL` solo DEBUG. Y nadie configura un
handler en la raíz — la config de uvicorn declara `uvicorn`, `uvicorn.error` y
`uvicorn.access`, sin `root` — así que lo único que se imprime es lo que recoge
`logging.lastResort`, de WARNING para arriba: silenciar INFO o DEBUG no ahorraba una línea.

Lo que sí ahorra: en el worker de construcción `build_process.py` funde stderr en stdout y
el padre reemite con `logger.info` toda línea sin marcador, así que sin esto los 27 avisos
acaban en `logs/<slug>/jobs.log` de cada relectura."""),
]
