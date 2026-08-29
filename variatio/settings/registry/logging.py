"""The «Registro» settings: the log level and the third-party loggers that are silenced."""

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
            default=["docling", "docling_core", "docling_ibm_models", "PIL"],
            group="Registro", impact=Impact.LOCKED, editable=False,
            doc="""`variatio/__init__.py` lo lee por nombre en tiempo de importación
(`from .config import LOG_LEVEL, NOISY_LOGGERS, NOISY_WARNING_MODULES`) para configurar
loguru una sola vez. Reescribir el atributo después no reconfigura nada, así que
ofrecerlo como editable en caliente sería una mentira que la pantalla contaría."""),
    Setting(key="logging.noisy_warning_modules", name="NOISY_WARNING_MODULES",
            kind="list[str]", default=[r"docling.*", r"PIL.*"],
            group="Registro", impact=Impact.LOCKED, editable=False,
            doc="""`variatio/__init__.py` lo lee por nombre en tiempo de importación
(`from .config import LOG_LEVEL, NOISY_LOGGERS, NOISY_WARNING_MODULES`) para configurar
loguru una sola vez. Reescribir el atributo después no reconfigura nada, así que
ofrecerlo como editable en caliente sería una mentira que la pantalla contaría."""),
]
