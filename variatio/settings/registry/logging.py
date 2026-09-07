"""The "Registro" settings: the log level and the third-party logger that is silenced."""

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
            doc="""`variatio/__init__.py` lo lee por nombre en tiempo de importación para configurar loguru una
sola vez. Reescribir el atributo después no reconfigura nada, así que ofrecerlo como editable
en caliente sería una mentira que la pantalla contaría.

Solo `docling`, y está medido: sobre los 22 documentos Office de la instalación, por la ruta
real y con un handler espía en la raíz, es el único que emite algo que llegue a imprimirse —
27 WARNING de `docling.backend.msword_backend` («image cannot be loaded by Pillow», los
logos de cabecera que el markdown no lleva). `docling_core` y `docling_ibm_models` no
emiten nada en ningún nivel y `PIL` solo DEBUG. Como nadie configura un handler en la raíz,
lo único que se imprime es lo que recoge `logging.lastResort`, de WARNING para arriba:
silenciar INFO o DEBUG no ahorra una línea.

Lo que sí ahorra: `build_process.py` funde stderr en stdout y el padre reemite con
`logger.info` toda línea sin marcador, así que sin esto esos avisos acaban en
`logs/<slug>/jobs.log` de cada relectura."""),
]
