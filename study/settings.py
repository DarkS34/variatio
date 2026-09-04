"""The study's nine settings, declared beside the code that reads them.

`variatio/settings/registry/__init__.py` picks these up through an optional import — the
one place the pipeline names the study, and the single exception to the boundary.
"""

from variatio.settings.types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(
        key="evaluation.local_model",
        name="",
        kind="str",
        default=None,
        nullable=True,
        group="Evaluación",
        scope="engine",
        impact=Impact.NONE,
        doc="""QUÉ MODELO ESCRIBE LAS DOS PROPUESTAS LOCALES de una comparación (la de solo RAG y la del
sistema). Lo fija la instalación, no quien encarga la evaluación: el formulario de
«Evaluar el sistema» no ofrece ningún selector (2026-09-04, petición explícita del
usuario, que revocó la elección por encargo del mismo día).

Es UN modelo para las dos, y eso no es un detalle: lo que se compara son arquitecturas, y
un modelo distinto en cada propuesta lo convertiría en una comparación de modelos. La
propuesta comercial usa su propia cadena (`evaluation.providers`).

Vacío significa «el mismo que genera ejercicios»: el primero de `generation.models`, que es
con lo que corrieron todas las sesiones anteriores a este ajuste. Un nombre que no esté
entre los ofrecidos vale igual — es una decisión de quien administra, no del encargo — y
si el motor no lo tiene instalado la sesión falla en la primera llamada. Si el modelo tiene
el esfuerzo bloqueado en «Modelos generadores», las dos propuestas corren al nivel
declarado, exactamente como una generación.

Con ámbito de motor, como toda elección de modelo: los nombres son del motor, y cambiar de
motor cambia el perfil entero. `ArmResult.model` guarda por propuesta con qué se escribió,
así que la memoria puede decirlo sesión a sesión.""",
    ),
    Setting(
        key="evaluation.providers",
        name="",
        kind="list[str]",
        default=["gemini", "mistral", "groq"],
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_EXTERNAL_PROVIDER",
        doc="""Este bloque lo declara `study/settings.py` y lo lee `study/config.py`: vive con el código
que lo consume, fuera del paquete que mide.

Los nombres `*_MODEL_ID` terminan a propósito ni en `_MODEL` ni en `_LLM`:
`inference.required_models()` recogía ambos sufijos por introspección y `/api/health` los
exigía a Ollama, así que cualquiera de los dos nombres aparecería en la interfaz como un
modelo nunca instalado — estos los sirve un proveedor externo y nunca se descargan.

`EVAL_EXTERNAL_PROVIDER` es una CADENA en orden de preferencia, no un único nombre. Los
planes gratuitos en los que corre este brazo responden 429 a mitad de una sesión de
recogida de datos, y un proveedor que deja de responder cede el turno al siguiente en vez
de costarle a la sesión su propuesta comercial.

El ORDEN por defecto no es arbitrario: el brazo mide la línea base COMERCIAL, así que
detrás de Gemini va otro modelo propietario (Mistral) y solo al final Groq, que sirve
pesos abiertos. Una sesión que cae hasta el último eslabón sigue produciendo un ítem, pero
lo que mide ya no es lo mismo — por eso `ArmResult` guarda quién respondió y la memoria
tiene que decirlo.

Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible. `none` (o un valor
vacío) desactiva el brazo.

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
        key="evaluation.models.mistral",
        name="",
        kind="str",
        default="mistral-medium-latest",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_MISTRAL_MODEL_ID",
        doc="""El segundo eslabón comercial de la cadena, para cuando Gemini agota su cuota gratuita a
mitad de una recogida de datos. Habla el `/chat/completions` de OpenAI, igual que Groq,
pero sirve un modelo propietario y de pago, que es lo que mide este brazo.

`mistral-medium-latest` es un alias: apunta siempre a la última versión de esa gama, así
que dos sesiones separadas por meses pueden estar medidas contra pesos distintos. Fija una
versión concreta si la memoria necesita reproducibilidad.

Los nombres `*_MODEL_ID` terminan a propósito ni en `_MODEL` ni en `_LLM`:
`inference.required_models()` recogía ambos sufijos por introspección y `/api/health` los
exigía a Ollama, así que cualquiera de los dos nombres aparecería en la interfaz como un
modelo nunca instalado — estos los sirve un proveedor externo y nunca se descargan.""",
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
        key="evaluation.keys.mistral",
        name="",
        kind="str",
        default="",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_MISTRAL_API_KEY",
        secret=True,
        editable=False,
        doc="""Se saca de console.mistral.ai; el plan gratuito de La Plateforme no pide tarjeta y basta
para este brazo, que hace una llamada por sesión.

Cada proveedor trae su propia clave y su propio id de modelo, así que nunca pueden
cruzarse — lo que la única `EVAL_EXTERNAL_API_KEY` hacía imposible.

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
        name="",
        kind="float",
        default=60.0,
        group="Evaluación",
        impact=Impact.NONE,
        minimum=1.0,
        doc="""Por intento, así que una cadena de tres espera esto tres veces en el peor caso. El brazo
corre en un hilo junto a los dos locales, que tardan minutos, de modo que no es el reloj
de pared.""",
    ),
]
