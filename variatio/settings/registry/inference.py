from ..types import Impact, Setting

_IDLE_DOC = """Cuánto puede estar el servidor sin ejecutar un solo trabajo antes de soltar la GPU
(`inference.unload_all()`, que es `ollama stop` de cada modelo residente).

`OLLAMA_KEEP_ALIVE=24h` es lo que mantiene los tres modelos calientes durante una sesión
de trabajo, y eso es lo que se quiere mientras se está trabajando: los 29 GiB residentes
no se pagan dos veces. Lo que no tiene sentido es que sigan ahí toda la noche porque
alguien dejó la pestaña abierta, en una tarjeta que es de todos.

30 minutos porque es la escala de la pausa que NO es una pausa de trabajo: entre dos
etapas de la cadena pasan minutos, no media hora, así que a este umbral no se llega
revisando un grafo — se llega habiéndose ido. Recargar los tres modelos cuesta ~30 s, que
es ruido al lado de cualquier construcción y de sobra tolerable en una generación suelta.
0 lo desactiva."""

_MODELS_MAIN_DOC = """UN SOLO modelo generativo, desde el 2026-08-17: los tres niveles no cabían juntos en la A40
(~45 GiB) y se desalojaban entre sí todo el día, y `gemma4:e4b-it-q8_0` (10.1 GiB) tampoco
cabía junto a uno de clase 30B, lo que hacía que cada reparación de JSON dentro del bucle
de extracción costase DOS cargas de ~10 s. Esa decisión sigue en pie; lo único que cambió
es CUÁL es el modelo.

Lo que queda residente son tres modelos que SÍ caben a la vez — medidos en 29.05 GiB de
~45 con las ventanas de contexto de abajo —, así que nada desaloja nada: este, el
guardarraíl y el embebedor. Ahora quedan 16 GiB de margen, donde el MoE anterior dejaba 3.5.

La medición vigente frente a un MoE de clase 30B era la etiquetabilidad: sobre el dominio
más grande del borrador de referencia (73 no etiquetables) `gemma4:31b` devolvió 75 y
`qwen3.6:35b-a3b` 66, es decir, el MoE excluye de MENOS, que es justo la dirección contra
la que legisla `review_taggable_concepts_prompt`. `qwen3.8:27b` es denso y razona, así que
se espera que aquí lo haga mejor — pero eso es una PREDICCIÓN, no una medición, y es lo
primero que hay que volver a comprobar en una construcción real.

`qwen3.8:27b-q4_K_M` desde el 2026-08-18, en sustitución de `qwen3.6:35b-a3b-q8_0` y
revirtiendo la vuelta atrás del 2026-08-16, por petición explícita del usuario. Lo que
reabrió la cuestión es que Ollama ya puede acotar cuánto delibera un modelo de
razonamiento: `think` acepta un NIVEL DE ESFUERZO y no solo un booleano, y los ajustes por
fase `reasoning.effort.*` fijan por defecto cada llamada con razonamiento en el más barato.

Los motivos de aquella vuelta atrás eran reales y solo están respondidos EN PARTE, así que
los números van aquí enteros. Todos en la A40, sobre la misma llamada —
`link_domain_relations_prompt` sobre el dominio más grande del borrador de referencia, 43
conceptos, 5 441 caracteres, temperatura 0:

  qwen3.6:35b-a3b-q8_0  think=true    128 s   37 264 car. de razonamiento   92.0 tok/s
  qwen3.8:27b-q4_K_M    think="low"   443 s   40 894                        29.1 tok/s
  qwen3.8:27b-q8_0      think="low"   649 s   38 796                        19.0 tok/s
  qwen3.8:27b-q8_0      think="high"  777 s   58 953        RESPUESTA VACÍA 19.2 tok/s

Tres cosas que leer en esa tabla antes de tocar nada de esto:

1. EL NIVEL DE ESFUERZO NO REDUCE MUCHO LA DELIBERACIÓN. `low` sigue emitiendo ~41 000
   caracteres, o sea más o menos lo que emitía el MoE antiguo con un `think=true` a secas.
   Lo que mueve el nivel es el TECHO (58 953 en `high`), no el suelo. Quien espere abaratar
   este modelo bajando más el esfuerzo se encontrará con que por debajo de `low` no hay
   nada salvo `think=False`, que apaga el razonamiento del todo.
2. EL COSTE ES LA DECODIFICACIÓN DENSA, y es el precio de esta decisión: 29.1 tok/s frente
   a los 92.0 del MoE, así que una llamada de curación pasa de 128 s a 443 s y una
   construcción se alarga ~3.5x. Aceptado a sabiendas el 2026-08-18.
3. LA CUANTIZACIÓN NO ES INTERCAMBIABLE AQUÍ. La q4_K_M es un 53 % más rápida que la q8_0
   (29.1 frente a 19.0 tok/s) y ocupa 16.5 GB contra 27.9, y obedece el nivel de esfuerzo
   exactamente igual — medido, no supuesto, en la tabla de tokens de `reasoning.effort.*`.
   A diferencia de `qwen3.6:35b-a3b-q4_K_M`, que está rota en esta máquina por encima de
   ~4 490 caracteres, esta q4 respondió al prompt de 5 441 caracteres con JSON válido. No
   la «mejores» a la q8."""

_TEMPERATURE_DOC = """HASTA DÓNDE PUEDE DIVAGAR EL MUESTREADOR. El valor por defecto de Ollama es 0.8, y unos
cuantos Modelfiles declaran 1.0 — una temperatura de REDACCIÓN, aplicada sin distinción a
llamadas que no redactan nada: leer los conceptos de un fragmento, decidir si dos nombres
son el mismo concepto, responder sí o no. Con ese valor por defecto, esas llamadas
redibujan un grafo distinto a partir del mismo corpus en cada construcción, y la diferencia
entre dos ejecuciones no es evidencia de nada. Toda llamada generativa del proyecto nombra
ahora una de estas tres.

1. DETERMINISTA — la respuesta es una lectura de la entrada y solo hay una correcta:
   extracción, los nombres de dominio y su asignación, los escaneos del banco y del perfil,
   el veredicto del guardarraíl, las descripciones de concepto que se embeben y se
   cachean. Voraz, para que reconstruir sea reconstruir y no volver a dibujar. Lo que hace
   que 0 sea seguro en todos estos sitios y no en los de abajo es que todos son
   `think=False` Y están acotados por una gramática: la respuesta empieza en `{` y el
   esquema limita cuánto puede seguir.
2. RAZONAMIENTO — los juicios con `think=True` sobre un inventario que ya está fijado:
   fusionar alias, descartar lo que no nombra un concepto, ordenar prerrequisitos,
   etiquetabilidad. Deliberadamente NO es 0, y es el único valor de aquí elegido en contra
   del determinismo. La decodificación voraz dentro de un canal de razonamiento es donde la
   deliberación degenera en un bucle de repetición, y degenera EN SILENCIO en esta pila —
   `KG_DOMAINS_MODEL` documenta una llamada que razonó durante 36 929 caracteres, alcanzó
   su token de parada y devolvió una respuesta vacía que nada aguas arriba podía distinguir
   de una de verdad. Es entropía suficiente para salir de un bucle así y queda muy por
   debajo del 0.6 que la ficha del modelo sugiere para pensar sin límites, porque ninguna
   de estas llamadas es abierta: el inventario que juzgan está cerrado.
3. GENERACIÓN — el final del pipeline, y la única llamada del proyecto que redacta de
   verdad. Aun así se queda baja, porque lo que hace que una variante merezca guardarse es
   que obedezca su encargo — los conceptos objetivo, los campos fijados, el currículo, las
   instrucciones — y la temperatura es exactamente lo que compra desviarse de los cuatro.
   La variedad entre los `n` ítems de una misma tanda se paga en el PROMPT, que le enseña
   al modelo los enunciados que ya ha escrito, y en la muestra aleatoria de ejemplos; aquí
   no es tarea del muestreador."""

_TEMPERATURE_REPAIR_DOC = """Constante propia aunque coincida con la de razonamiento, porque no está ahí por el mismo
motivo y no se movería con ella: reparar es un bucle de REINTENTO, y un reintento a 0 no es
un reintento. El prompt del intento N+1 es la salida del intento N, así que un modelo que
devuelve lo que se le dio reconstruye el prompt idéntico y, siendo voraz, escribe la
respuesta idéntica — el presupuesto entero gastado en una sola réplica byte a byte igual,
que es el fallo que `parse_with_repair` ya documenta haber pagado una vez."""

_CONTEXT_WINDOW_DOC = """Son lo que hace que los tres modelos convivan, así que no son libres de crecer: medido en
la A40 a través de `/api/ps`, `LLM_MAIN` a 65536 + guardarraíl + embebedor suman 29.05 GiB
de ~45 (19.49 + 5.49 + 4.07). La del guardarraíl era 8192, que costaba 1 GiB de caché KV y
subía el total antiguo a 45.17 — pasado por poco, y el síntoma era que filtrar un encargo
desalojaba al embebedor. Como mucho lee `GENERATION_INSTRUCTIONS_MAX_CHARS` (600
caracteres, ~200 tokens), así que 4096 sigue siendo un margen de diez veces.

La de `LLM_MAIN` se dobló desde 32768 el 2026-08-18, con el paso a un modelo de
razonamiento. La regla cambió por debajo: con `think` encendido, la ventana ya no la
dimensiona el PROMPT sino prompt + deliberación, y la deliberación es la mitad grande — el
prompt más largo del pipeline son ~8 000 tokens, mientras que una sola llamada de curación
en `low` gasta ~13 000 solo en razonar. El margen que liberó la q4, más ligera, es lo que
lo paga, así que mantenerla no cuesta nada.

Lo que NO arregla, medido, es la respuesta vacía que daba `curate_graph_domains_prompt`
mientras seguía pidiendo la partición entera: sobre 203 conceptos, esa llamada devolvió
`response == ""` a 32768 Y a 65536, byte a byte lo mismo (36 929 caracteres de
razonamiento, 11 611 tokens — unos 13 200 en total, una quinta parte de la ventana más
pequeña). Allí la ventana nunca fue la restricción; véase `KG_DOMAINS_MODEL`.

Bajarla trunca en silencio, como siempre — y ahora trunca primero el razonamiento, así que
el síntoma es una respuesta vacía o a medio escribir, y no una cola de prompt que falta."""

_CONTEXT_WINDOW_OVERRIDES_DOC = """La ventana de todo modelo de fase que NO sea el principal, el guardarraíl o el embebedor.
Antes de que esto existiera, un modelo así no tenía entrada en `LLM_CONTEXT` y Ollama
dimensionaba su caché KV a partir del Modelfile, lo que para `qwen3.6:35b-a3b-q8_0` (34.88
GiB solo de pesos) es la diferencia entre caber junto al embebedor y no caber. Un único
valor y no uno por fase: a 2026-08-23 la única sobrescritura es ese MoE, puesto en las
fases de construcción que leen documentos (`transcribe`, `ep_scan`, `eb_extract`,
`kg_extract`, las dos `kg_clean_*` y las dos `kg_link_*`), mientras `LLM_MAIN` sigue siendo
`qwen3.8:27b-q4_K_M` para juzgar y generar. Los dos nunca necesitan estar residentes a la
vez — una construcción carga el MoE una vez y el 27b vuelve en la siguiente generación —,
así que la aritmética de convivencia sigue siendo de tres modelos.

65536 porque aplica la misma regla que `context_window.main` (prompt más deliberación allí
donde una fase razona), y porque bajarla trunca en silencio."""

_TRANSCRIBE_DOC = """Transcripción de una página a partir de su imagen renderizada — compartida por LOS TRES
constructores y por LOS DOS orígenes en bruto, así que hay una sola constante y no tres que
pudieran divergir y producir dos markdowns distintos del mismo fichero. Desde el
2026-08-27, por petición explícita del usuario, `raw/raw_corpus/` pasa también por esta
ruta: la calidad pesa más que la velocidad, y a Docling le queda el `.docx`, que no tiene
página que renderizar.

Lo que sostiene la fidelidad aquí es el PROMPT, no el modelo. Medido sobre Prog1_PEC1 p.1:
sin la cláusula de copia carácter a carácter de `transcribe_page_prompt`, gemma4:31b
reescribió `a -= 1` como `a = a - 1`, se inventó `8 - (n-i)` donde había `(n-i)` y
convirtió `x = x - 1` en `x = x + 1` — lo que invierte la respuesta de la mismísima
pregunta que estaba transcribiendo. Con la cláusula, los dos modelos de clase 30B vuelven
fieles. Debilitar esa instrucción reintroduce en silencio código corrupto en el banco.

La comparación de fidelidad que hay detrás (acentos y el salto de línea de un docstring
conservados donde gemma4:31b perdió ambos, 20s frente a 31s por página) se midió sobre
`qwen3.6:35b-a3b-q8_0`, que ya no ocupa este puesto — siguió a `LLM_MAIN` hasta
`qwen3.8:27b-q4_K_M` el 2026-08-18. El modelo nuevo tiene la capacidad `vision`,
comprobado, así que la llamada funciona; si transcribe con la misma fidelidad NO está
medido todavía. Es lo más barato de volver a comprobar de todo el pipeline (una página) y
lo más dañino si se falla, porque una transcripción corrupta aterriza en el banco como un
ejercicio cuya respuesta ha cambiado y, desde que el corpus se sumó a esta ruta, en el
grafo como un concepto que el temario nunca enseñó."""

_TRANSCRIBE_SEAM_DOC = """La costura entre dos páginas transcritas por separado: el modelo CLASIFICA cómo se pegan
—`none`/`space`/`newline`/`paragraph`— y cuántas líneas iniciales de la segunda son
repetición mecánica de la maquetación. NUNCA reescribe el contenido: todo el prompt de
transcripción está construido sobre «copia carácter a carácter», y un segundo modelo con
permiso para redactar lo tiraría por la borda. La respuesta se verifica contra el catálogo
de separadores antes de creerla, y lo que no se pueda leer cae al detector determinista.

SIN MEDIR. Esta fase existe desde el 2026-08-27 por petición explícita del usuario y no
tiene todavía ni una medición de calidad ni una de coste: lo único comprobado es que el
detector determinista solo, que es lo que había antes, mete un salto de párrafo en mitad de
una frase o de un bloque de código cada vez que un ejercicio ocupa dos páginas. Una llamada
por costura y solo cuando el detector no tiene certeza (una valla de código abierta sí lo
es), así que un documento de N páginas paga como mucho N-1 llamadas cortas."""


_PHASE_SHARED_DOC = """Una constante por llamada al modelo sigue siendo la unidad de reajuste, y esa es toda la
razón de que sobrevivan a una consolidación: apuntarlas todas a `LLM_MAIN` es una decisión,
no un colapso, y cualquier fase suelta puede moverse fuera sin tocar las otras doce."""

_KG_DOMAINS_DOC = """La única fase cuya llamada tuvo que renunciar del todo al razonamiento cuando `LLM_MAIN`
pasó a ser un modelo que razona: pedirle que particionase el inventario entero hacía que
respondiera dentro del canal de razonamiento y no devolviera nada. Ahora solo nombra los
dominios — `assign_round` coloca los conceptos, tanda a tanda — y las dos llamadas siguen
acotadas por una gramática y por tanto sin pensar. La medición está en el sitio de la
llamada, en `knowledge_graph_builder/curation.py:curate_domains`. Aquí el que estaba mal no
era el modelo, así que esto sigue apuntando a `LLM_MAIN`; era el pensar."""

_REPAIR_DOC = """Reparar es la única llamada que se dispara DESDE DENTRO de un bucle por elemento, así que
es también la única que nunca debe tener modelo propio: un modelo pequeño aparte no cabe
junto a `LLM_MAIN` en esta máquina, y cada reparación lo desalojaría y pagaría dos cargas
de ~10 s en mitad de un corpus. Se mueva lo que se mueva fuera de `LLM_MAIN`, esta lo
sigue."""

_VACIO_SENTINEL = "Vacío significa que sigue al modelo principal."


def _phase_doc(sentence: str) -> str:
    return _PHASE_SHARED_DOC + "\n\n" + sentence + "\n\n" + _VACIO_SENTINEL


SETTINGS: list[Setting] = [
    Setting(
        key="engine.name",
        name="INFERENCE_ENGINE",
        kind="str",
        default="ollama",
        group="Motor",
        impact=Impact.ENGINE,
        choices=("ollama", "cerebras+ollama"),
        doc="""Qué implementación de motor de inferencia respalda generate()/embed()/embed_batch().
`config.INFERENCE_ENGINE` la selecciona y la lógica de negocio nunca llama a un SDK
directamente — todo pasa por `variatio.core.inference`.

'ollama' es el motor local de siempre. 'cerebras+ollama' es un motor compuesto: los modelos
listados en CEREBRAS_MODELS van a la API de Cerebras (api.cerebras.ai, OpenAI-compatible) y
todo lo demás —el guardián y el embedder incluidos— sigue en Ollama. La residencia, la
descarga de la GPU y el pull/borrado de modelos son siempre de la mitad Ollama: en Cerebras
no hay nada que cargar ni descargar.

CADA MOTOR TIENE SU PERFIL DE CONFIGURACIÓN. Los ajustes de ámbito «engine» (los modelos,
las fases, las ventanas de contexto y los interruptores de razonamiento con sus esfuerzos) se
guardan en `config.json` bajo `profiles.<motor>`, así que cambiar de motor cambia de perfil
completo y volver atrás recupera el anterior tal cual se dejó.

Elegir 'cerebras+ollama' saca los prompts y el corpus de la máquina hacia un servicio
externo: es una decisión explícita del 2026-08-24 que revoca, solo para quien lo active, el
«open-source only / stack local» del registro de decisiones. El motor por defecto sigue
siendo 'ollama'.""",
    ),
    Setting(
        key="engine.cerebras_base_url",
        name="CEREBRAS_BASE_URL",
        kind="str",
        default="https://api.cerebras.ai/v1",
        group="Motor",
        impact=Impact.ENGINE,
        env="CEREBRAS_BASE_URL",
        doc="""La raíz OpenAI-compatible de la API de Cerebras. Solo la usa el motor 'cerebras+ollama';
existe como ajuste porque es lo que permite apuntar a un proxy o a un mock en pruebas sin
tocar código.""",
    ),
    Setting(
        key="engine.cerebras_api_key",
        name="CEREBRAS_API_KEY",
        kind="str",
        default="",
        group="Motor",
        impact=Impact.ENGINE,
        env="CEREBRAS_API_KEY",
        secret=True,
        editable=False,
        doc="""La clave de la API de Cerebras. Como las claves de la evaluación: viene del entorno (o
del `.env` ignorado por git), nunca se serializa en `config.json` y nunca sale de la API —
`snapshot()` solo dice «configurada» o «ausente». Sin clave, el motor 'cerebras+ollama'
falla en la primera llamada remota con un error legible; las llamadas a la mitad Ollama no
la necesitan.""",
    ),
    Setting(
        key="engine.cerebras_models",
        name="CEREBRAS_MODELS",
        kind="list[str]",
        default=["gemma-4-31b"],
        group="Motor",
        impact=Impact.ENGINE,
        doc="""Qué modelos enruta a Cerebras el motor 'cerebras+ollama'; todo lo que no esté aquí va a
Ollama. La pertenencia a esta lista ES la decisión de enrutado — explícita a propósito, en
vez de adivinar por la forma del nombre («gemma-4-31b» contra «qwen3.8:27b-q4_K_M»).

`gemma-4-31b` por defecto: es el id exacto del catálogo de Cerebras (~1.850 tok/s medidos
por Artificial Analysis, ventana de 131.072, salida máxima 40.000, structured outputs con
`strict` y razonamiento vía `reasoning_effort`).

LAS CUOTAS SON POR MODELO, y las de la cuenta no son las que anuncia la página del modelo.
Medido contra la API el 2026-08-26: `gemma-4-31b` declara 500 peticiones/min y 250.000
tokens uncached/min, pero los `remaining-*` de esta cuenta van contra 5 peticiones/min,
30.000 tokens/min, 2.400 peticiones/día y 1.000.000 de tokens/día. Un build entero no cabe
ahí. Quien lo administra son los CEREBRAS_MAX_* de más abajo, no esta lista.""",
    ),
    # Los cuatro techos que de verdad atan, con los números del nivel gratuito medidos el
    # 2026-08-26. No se leen de los headers `limit-*` porque esos reportan la cuota del
    # MODELO (gemma: 500/min y 250.000 tok/min) y no la de la cuenta, que solo asoma en los
    # `remaining-*`. El limitador sí los sube solo si alguna vez ve un `remaining` por
    # encima de ellos: eso solo puede significar que la cuenta es mayor de lo que dicen.
    Setting(
        key="engine.cerebras_max_requests_minute",
        name="CEREBRAS_MAX_REQUESTS_MINUTE",
        kind="int",
        default=5,
        minimum=1,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuántas peticiones por minuto admite la cuenta para CADA modelo enrutado a Cerebras.

5 en el nivel gratuito (medido 2026-08-26: la primera llamada dejó
`x-ratelimit-remaining-requests-minute` en 4, mientras el header `limit-` anunciaba 1000).
Es el techo que más ata: 5/min es un suelo de 12 segundos entre llamadas, así que un build
con cientos de llamadas pasa a durar horas. El limitador espera a que ruede la ventana en
vez de comerse un 429, y lo dice en «Motor».

No hace falta reiniciar nada al cambiarlo: se lee en cada llamada.""",
    ),
    Setting(
        key="engine.cerebras_max_tokens_minute",
        name="CEREBRAS_MAX_TOKENS_MINUTE",
        kind="int",
        default=30_000,
        minimum=1,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuántos tokens por minuto admite la cuenta para cada modelo enrutado a Cerebras. 30.000 en
el nivel gratuito (medido 2026-08-26).

Se cuentan con el `usage` exacto que trae cada respuesta, no con los headers: medido, el
contador de tokens del servidor va con retraso — una llamada de 74 tokens y otra de 20
movieron `remaining-tokens-day` exactamente 6 las dos veces. El header solo se usa para
BAJAR lo que creemos que queda, nunca para subirlo.""",
    ),
    Setting(
        key="engine.cerebras_max_requests_day",
        name="CEREBRAS_MAX_REQUESTS_DAY",
        kind="int",
        default=2_400,
        minimum=1,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuántas peticiones al día admite la cuenta para cada modelo enrutado a Cerebras. 2.400 en el
nivel gratuito (medido 2026-08-26: `remaining-requests-day` en 2399 tras una llamada,
mientras el header `limit-` anunciaba 720.000).

La ventana es deslizante de 24 h, no un día natural: la API no manda ningún header de
`reset`, así que la única ventana reconstruible es la que sale de nuestras propias marcas
de tiempo. Ser deslizante es lo conservador — nunca gasta de más.""",
    ),
    Setting(
        key="engine.cerebras_max_tokens_day",
        name="CEREBRAS_MAX_TOKENS_DAY",
        kind="int",
        default=1_000_000,
        minimum=1,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuántos tokens al día admite la cuenta para cada modelo enrutado a Cerebras. 1.000.000 en el
nivel gratuito (medido 2026-08-26).

Es el techo que decide si un build cabe: con prompts de ~8.000 tokens salen unas 125
llamadas al día. El desglose por fase de «Motor» existe para responder a la pregunta que
sigue — QUÉ fase se lo está comiendo — y se descarga en CSV.""",
    ),
    Setting(
        key="engine.cerebras_max_wait_seconds",
        name="CEREBRAS_MAX_WAIT_SECONDS",
        kind="int",
        default=90,
        minimum=0,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuánto puede quedarse una llamada esperando a que se libere presupuesto antes de rendirse
con un error legible.

Una regla, dos efectos: la ventana de minuto se libera en 60 s como mucho, así que se
espera; la de día tarda horas, así que se rechaza diciendo cuándo se libera. Esperar veinte
horas no es esperar — es un build colgado sin explicación. La espera es cancelable
(`progress.checkpoint()` entre rebanadas de un segundo), así que el botón de Cancelar sigue
respondiendo mientras se aguanta.""",
    ),
    Setting(
        key="engine.ollama_host",
        name="OLLAMA_HOST",
        kind="str",
        default="localhost:13434",
        group="Motor",
        impact=Impact.ENGINE,
        env="OLLAMA_HOST",
        doc="""El host de Ollama como `host:puerto` (o una URL `http(s)://` completa). `config.py` lo
lee de la variable de entorno `OLLAMA_HOST` y normaliza un `host:puerto` desnudo
anteponiéndole `http://`; el registro guarda el valor desnudo y ese prefijo se añade en
otro sitio, no aquí.""",
    ),
    Setting(
        key="engine.idle_unload_seconds",
        name="IDLE_UNLOAD_SECONDS",
        kind="int",
        default=1800,
        group="Motor",
        impact=Impact.NONE,
        env="VARIATIO_IDLE_UNLOAD_SECONDS",
        minimum=0,
        doc=_IDLE_DOC,
    ),
    Setting(
        key="engine.idle_unload_poll_seconds",
        name="IDLE_UNLOAD_POLL_SECONDS",
        kind="int",
        default=60,
        group="Motor",
        impact=Impact.NONE,
        minimum=1,
        doc=_IDLE_DOC,
    ),
    Setting(
        key="models.main",
        name="LLM_MAIN",
        kind="str",
        default="qwen3.8:27b-q4_K_M",
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=(("cerebras+ollama", "gemma-4-31b"),),
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="models.guardrail",
        name="GUARDRAIL_LLM",
        kind="str",
        default="granite4.1-guardian:8b-q4_K_M",
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="models.embedding",
        name="EMBEDDING_LLM",
        kind="str",
        default="qwen3-embedding:4b",
        group="Modelos",
        impact=Impact.REINDEX,
        scope="engine",
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="sampling.temperature_deterministic",
        name="TEMPERATURE_DETERMINISTIC",
        kind="float",
        default=0.0,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_reasoning",
        name="TEMPERATURE_REASONING",
        kind="float",
        default=0.2,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_generation",
        name="TEMPERATURE_GENERATION",
        kind="float",
        default=0.3,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_repair",
        name="TEMPERATURE_REPAIR",
        kind="float",
        default=0.2,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_REPAIR_DOC,
    ),
    Setting(
        key="context_window.main",
        name="",
        kind="int",
        default=65536,
        group="Ventana de contexto",
        scope="engine",
        impact=Impact.CONTEXTS,
        minimum=2048,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="context_window.guardrail",
        name="",
        kind="int",
        default=4096,
        group="Ventana de contexto",
        scope="engine",
        impact=Impact.CONTEXTS,
        minimum=2048,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="context_window.embedding",
        name="",
        kind="int",
        default=4096,
        group="Ventana de contexto",
        scope="engine",
        impact=Impact.REINDEX,
        minimum=512,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="context_window.overrides",
        name="",
        kind="int",
        default=65536,
        group="Ventana de contexto",
        scope="engine",
        impact=Impact.CONTEXTS,
        minimum=2048,
        doc=_CONTEXT_WINDOW_OVERRIDES_DOC,
    ),
    Setting(
        key="models.phases.transcribe",
        name="TRANSCRIBE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_TRANSCRIBE_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
    Setting(
        key="models.phases.transcribe_seam",
        name="TRANSCRIBE_SEAM_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_TRANSCRIBE_SEAM_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
    Setting(
        key="models.phases.ep_scan",
        name="EP_SCAN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de escaneo del generador de perfil de ejemplares (exemplars_profile_builder)."
        ),
    ),
    Setting(
        key="models.phases.ep_consolidate",
        name="EP_CONSOLIDATE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de consolidación del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.ep_context",
        name="EP_CONTEXT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de contexto del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.eb_extract",
        name="EB_EXTRACT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de extracción del generador del banco de ejemplares."),
    ),
    Setting(
        key="models.phases.kg_extract",
        name="KG_EXTRACT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de extracción del constructor del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_merge",
        name="KG_CLEAN_MERGE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de fusión de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_drop",
        name="KG_CLEAN_DROP_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc("Fase de descarte de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_units",
        name="KG_UNITS_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de segmentación del temario del grafo de conocimiento: lee el índice de "
            "encabezados del corpus y dice cuáles abren unidad didáctica."
        ),
    ),
    Setting(
        key="models.phases.kg_domains",
        name="KG_DOMAINS_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_KG_DOMAINS_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
    Setting(
        key="models.phases.kg_domains_leftovers",
        name="KG_DOMAINS_LEFTOVERS_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de colocación de los conceptos sobrantes de la asignación de dominios "
            "del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_domain",
        name="KG_LINK_DOMAIN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de enlace de relaciones dentro de un mismo dominio del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_cross_domain",
        name="KG_LINK_CROSS_DOMAIN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de enlace de relaciones entre dominios distintos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_taggable",
        name="KG_TAGGABLE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de revisión de etiquetabilidad de los conceptos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_context",
        name="KG_CONTEXT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de síntesis del contexto de la materia a partir del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.description_generation",
        name="DESCRIPTION_GENERATION_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de generación de descripciones de conceptos, en el pipeline en tiempo de "
            "ejecución (no en un build)."
        ),
    ),
    Setting(
        key="models.phases.concept_tagger",
        name="CONCEPT_TAGGER_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de etiquetado de conceptos sobre el banco de ejemplares, en el pipeline en "
            "tiempo de ejecución."
        ),
    ),
    Setting(
        key="models.phases.variant_generation",
        name="VARIANT_GENERATION_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de generación de variantes de contenido, en el pipeline en tiempo de "
            "ejecución."
        ),
    ),
    Setting(
        key="models.phases.admissibility",
        name="ADMISSIBILITY_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_phase_doc(
            "Fase de admisibilidad: juzga si el texto libre del encargo pide algo que ya "
            "decide otro control de la pantalla. Va sobre el modelo principal por dos "
            "razones: ya está residente cuando se le llama, así que no cuesta un cambio de "
            "modelo, y el guardián —que corre antes— tiene 4096 de contexto y no puede leer "
            "la lista entera de conceptos del grafo."
        ),
    ),
    Setting(
        key="models.phases.repair",
        name="REPAIR_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        nullable=True,
        doc=_REPAIR_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
]
