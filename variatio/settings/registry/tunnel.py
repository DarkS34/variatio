"""The "Túnel SSH" settings: where the GPU box is, and whether the API opens the tunnel."""

from ..types import Impact, Setting

_TUNNEL_DOC = """El motor no corre en esta máquina: `OLLAMA_HOST` apunta a un puerto local que un túnel SSH
reenvía a la máquina de la GPU. Lo levanta la API, con el cliente `ssh` del sistema como
subproceso, y el panel lo enciende y lo apaga.

Se usa el `ssh` instalado y no una librería: es lo que ya resuelve claves, agente,
`~/.ssh/config` y `known_hosts`. Nada de contraseñas — `BatchMode=yes` hace que un `ssh`
que pediría una falle en vez de quedarse colgado esperando una consola que no existe.

`OLLAMA_SSH_HOST` es el destino tal como lo escribirías en la terminal (`usuario@host` o un
alias de `~/.ssh/config`); vacío significa que no hay túnel y el resto de ajustes no se lee.
El puerto local es el de `OLLAMA_HOST`; aquí solo se dice el remoto, 11434 por ser el puerto
por defecto de `ollama serve`. `OLLAMA_SSH_KEY_PATH` es la ruta de una clave concreta (`-i`),
para cuando el agente no la tiene; es una ruta y no un secreto.

`OLLAMA_SSH_AUTOSTART` decide si el túnel se levanta con la API; apagado, se levanta desde el
panel. Si el proceso de `ssh` muere el vigilante lo relanza con espera creciente (5 s a 60 s)
mientras el túnel siga pedido."""

# All four are `secret` to keep this deployment's own GPU address out of the versioned
# config.json, not because a port is confidential: they live in `.env`, like DATABASE_URL.
SETTINGS: list[Setting] = [
    Setting(
        key="tunnel.host",
        name="OLLAMA_SSH_HOST",
        kind="str",
        default="",
        group="Túnel SSH",
        impact=Impact.NONE,
        env="OLLAMA_SSH_HOST",
        secret=True,
        editable=False,
        doc=_TUNNEL_DOC,
    ),
    Setting(
        key="tunnel.remote_port",
        name="OLLAMA_SSH_REMOTE_PORT",
        kind="int",
        default=11434,
        group="Túnel SSH",
        impact=Impact.NONE,
        env="OLLAMA_SSH_REMOTE_PORT",
        secret=True,
        editable=False,
        minimum=1,
        maximum=65535,
        doc=_TUNNEL_DOC,
    ),
    Setting(
        key="tunnel.key_path",
        name="OLLAMA_SSH_KEY_PATH",
        kind="str",
        default="",
        group="Túnel SSH",
        impact=Impact.NONE,
        env="OLLAMA_SSH_KEY_PATH",
        secret=True,
        editable=False,
        doc=_TUNNEL_DOC,
    ),
    Setting(
        key="tunnel.autostart",
        name="OLLAMA_SSH_AUTOSTART",
        kind="bool",
        default=False,
        group="Túnel SSH",
        impact=Impact.NONE,
        env="OLLAMA_SSH_AUTOSTART",
        secret=True,
        editable=False,
        doc=_TUNNEL_DOC,
    ),
]
