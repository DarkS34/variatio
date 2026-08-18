"""Soltar la GPU cuando lleva mucho rato sin que nadie la pida.

`OLLAMA_KEEP_ALIVE=24h` es deliberado: mantiene los tres modelos residentes durante una
sesión de trabajo, que es exactamente lo que se quiere mientras se trabaja. Su defecto es
que no distingue una pausa de un abandono, y una instalación que nadie ha tocado desde
ayer sigue ocupando ~29 GiB de una tarjeta que es compartida.

Este hilo es esa distinción, y nada más: mira el reloj de la cola — la cola es por dónde
pasa TODO el tráfico de modelos de este proceso — y cuando lleva `IDLE_UNLOAD_SECONDS`
sin un trabajo, manda descargar lo que haya residente. No es un sustituto del keep-alive
ni un temporizador más corto: los modelos siguen calientes toda la sesión, y se sueltan
una sola vez cuando la sesión se ha acabado de hecho.

Descargar es gratis de deshacer: la siguiente llamada los vuelve a cargar sola.
"""

import threading

from loguru import logger

from variant_generator import config, inference

from .runner import JobRunner


class IdleUnloader:
    def __init__(self, runner: JobRunner):
        self.runner = runner
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        # Una sola descarga por periodo de inactividad: sin esto, cada vuelta del bucle
        # volvería a pedir `/api/ps` y a mandar una descarga que ya no tiene nada que
        # descargar, y un servidor parado escribiría una línea de registro por minuto.
        self._released = False

    def start(self) -> None:
        if self._thread is not None or config.IDLE_UNLOAD_SECONDS <= 0:
            return
        self._thread = threading.Thread(target=self._run, name="idle-unloader", daemon=True)
        self._thread.start()
        logger.info(
            f"Vigilando la inactividad: la GPU se libera tras "
            f"{config.IDLE_UNLOAD_SECONDS // 60} minuto(s) sin trabajos"
        )

    def stop(self, timeout: float = 2.0) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stopping.wait(config.IDLE_UNLOAD_POLL_SECONDS):
            try:
                self._tick()
            except Exception as e:  # noqa: BLE001 - un vigilante no puede tumbar el proceso
                logger.warning(f"El vigilante de inactividad falló esta vuelta: {e}")

    def _tick(self) -> None:
        idle = self.runner.idle_seconds()
        if idle < config.IDLE_UNLOAD_SECONDS:
            self._released = False
            return
        if self._released:
            return

        self._released = True
        released = inference.unload_all()
        if released:
            logger.info(
                f"{len(released)} modelo(s) descargados de la GPU tras "
                f"{int(idle // 60)} minuto(s) de inactividad: {', '.join(released)}"
            )
