from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(
        key="evaluation.providers",
        name="EVAL_EXTERNAL_PROVIDERS",
        kind="list[str]",
        default=["gemini", "groq"],
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_EXTERNAL_PROVIDER",
        doc="""Solo el modo de evaluación lee este bloque; el pipeline nunca importa `evaluation/`.

Los nombres `*_MODEL_ID` terminan a propósito ni en `_MODEL` ni en `_LLM`:
`inference.required_models()` recogía ambos sufijos por introspección y `/api/health` los
exigía a Ollama, así que cualquiera de los dos nombres aparecería en la interfaz como un
modelo nunca instalado — estos los sirve un proveedor externo y nunca se descargan.

`EVAL_EXTERNAL_PROVIDER` es una CADENA en orden de preferencia, no un único nombre. Los
planes gratuitos en los que corre este brazo responden 429 a mitad de una sesión de
recogida de datos, y un proveedor que deja de responder cede el turno al siguiente en vez
de costarle a la sesión su propuesta comercial. Cada proveedor trae su propia clave y su
propio id de modelo, así que nunca pueden cruzarse — lo que la única
`EVAL_EXTERNAL_API_KEY` hacía imposible. `none` (o un valor vacío) desactiva el brazo.

Las claves vienen del entorno (o del `.env` ignorado por git) y por defecto están vacías:
sin ninguna clave el brazo naive se registra como `unavailable` y la sesión corre con dos.""",
    ),
    Setting(
        key="evaluation.models.gemini",
        name="",
        kind="str",
        default="gemini-3.6-flash",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GEMINI_MODEL_ID",
        doc="""Los nombres `*_MODEL_ID` terminan a propósito ni en `_MODEL` ni en `_LLM`:
`inference.required_models()` recogía ambos sufijos por introspección y `/api/health` los
exigía a Ollama, así que cualquiera de los dos nombres aparecería en la interfaz como un
modelo nunca instalado — estos los sirve un proveedor externo y nunca se descargan.

Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible.""",
    ),
    Setting(
        key="evaluation.models.groq",
        name="",
        kind="str",
        default="llama-3.3-70b-versatile",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GROQ_MODEL_ID",
        doc="""Los nombres `*_MODEL_ID` terminan a propósito ni en `_MODEL` ni en `_LLM`:
`inference.required_models()` recogía ambos sufijos por introspección y `/api/health` los
exigía a Ollama, así que cualquiera de los dos nombres aparecería en la interfaz como un
modelo nunca instalado — estos los sirve un proveedor externo y nunca se descargan.

Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible.""",
    ),
    Setting(
        key="evaluation.keys.gemini",
        name="",
        kind="str",
        default="",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GEMINI_API_KEY",
        secret=True,
        editable=False,
        doc="""Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible. `none` (o un valor
vacío) desactiva el brazo.

Las claves vienen del entorno (o del `.env` ignorado por git) y por defecto están vacías:
sin ninguna clave el brazo naive se registra como `unavailable` y la sesión corre con dos.

Nunca se serializan en `config.json` ni salen de la API: viven solo en el `.env` ignorado
por git.""",
    ),
    Setting(
        key="evaluation.keys.groq",
        name="",
        kind="str",
        default="",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GROQ_API_KEY",
        secret=True,
        editable=False,
        doc="""Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible. `none` (o un valor
vacío) desactiva el brazo.

Las claves vienen del entorno (o del `.env` ignorado por git) y por defecto están vacías:
sin ninguna clave el brazo naive se registra como `unavailable` y la sesión corre con dos.

Nunca se serializan en `config.json` ni salen de la API: viven solo en el `.env` ignorado
por git.""",
    ),
    Setting(
        key="evaluation.timeout",
        name="EVAL_EXTERNAL_TIMEOUT",
        kind="float",
        default=60.0,
        group="Evaluación",
        impact=Impact.NONE,
        minimum=1.0,
        doc="""Por intento, así que una cadena de dos espera esto dos veces en el peor caso. El brazo
corre en un hilo junto a los dos locales, que tardan minutos, de modo que no es el reloj
de pared.""",
    ),
]
