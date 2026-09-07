"""The engine settings: the two engines, the phase models, sampling and context windows."""

from ..types import Impact, Setting

_TEMPERATURE_DOC = """HASTA DÓNDE PUEDE DIVAGAR EL MUESTREADOR. El valor por defecto de Ollama es 0.8 —una
temperatura de REDACCIÓN— aplicada sin distinción a llamadas que no redactan nada, y con
él un mismo corpus produce un grafo distinto en cada construcción. Toda llamada generativa
del proyecto nombra una de estas tres:

1. DETERMINISTA — la respuesta es una lectura de la entrada y solo hay una correcta:
   extracción, dominios, escaneos, guardarraíl, descripciones. Lo que hace 0 seguro aquí es
   que todas son `think=False` Y están acotadas por una gramática.
2. RAZONAMIENTO — los juicios con `think=True` sobre un inventario ya fijado. NO es 0, y es
   el único valor elegido en contra del determinismo: la decodificación voraz dentro de un
   canal de razonamiento degenera EN SILENCIO en un bucle de repetición (véase
   `KG_DOMAINS_MODEL`: 36 929 caracteres de deliberación y respuesta vacía). Queda por
   debajo del 0.6 que sugiere la ficha del modelo, porque el inventario que juzgan es
   cerrado.
3. GENERACIÓN — la única llamada que redacta de verdad, y aun así baja: lo que hace que un
   ejercicio merezca guardarse es que obedezca su encargo, y la temperatura es exactamente
   lo que compra desviarse de él. La variedad dentro de una tanda se paga en el PROMPT, que
   enseña al modelo lo que ya ha escrito."""

_RESIDENT_MODELS_DOC = """UN SOLO modelo generativo por trabajo: los tres niveles antiguos no cabían juntos en la A40
(~45 GiB) y se desalojaban entre sí. Lo que queda residente son tres modelos que SÍ caben a
la vez — medidos en 29.05 GiB de ~45 con las ventanas de abajo: este, el guardarraíl y el
embebedor. Esa aritmética ya no describe los perfiles que se envían, donde las fases que
leen documentos nombran un MoE de 34.88 GiB: vuelve a medir `/api/ps` antes de citarla.

Medición vigente frente a un MoE de clase 30B, sobre la misma llamada de curación
(43 conceptos, 5 441 caracteres, temperatura 0, A40):

  qwen3.6:35b-a3b-q8_0  think=true    128 s   37 264 car. de razonamiento   92.0 tok/s
  qwen3.8:27b-q4_K_M    think="low"   443 s   40 894                        29.1 tok/s
  qwen3.8:27b-q8_0      think="low"   649 s   38 796                        19.0 tok/s
  qwen3.8:27b-q8_0      think="high"  777 s   58 953        RESPUESTA VACÍA 19.2 tok/s

Tres cosas que leer ahí antes de tocar nada:

1. EL NIVEL DE ESFUERZO NO REDUCE MUCHO LA DELIBERACIÓN: `low` sigue emitiendo ~41 000
   caracteres. Lo que mueve el nivel es el TECHO, no el suelo, y por debajo de `low` no hay
   nada salvo `think=False`.
2. EL COSTE ES LA DECODIFICACIÓN DENSA: 29.1 tok/s frente a 92.0, así que la construcción
   se alarga ~3.5x. Aceptado a sabiendas.
3. LA CUANTIZACIÓN SE PAGA A PROPÓSITO: la q4_K_M es un 53 % más rápida y ocupa 16.5 GB
   contra 27.9, y obedece el esfuerzo igual — pero NO está instalada en esta máquina, así
   que nombrarla dejaba diecisiete fases apuntando a un modelo inexistente. En calidad de
   etiquetabilidad, un MoE excluye de MENOS (66 frente a 75 sobre 73 no etiquetables), que
   es la dirección contra la que legisla `review_taggable_concepts_prompt`.

La `qwen3.6:35b-a3b-q4_K_M` sigue rota en esta máquina por encima de ~4 490 caracteres, y
por eso el MoE de transcripción es la q8_0 y no la q4."""

_TEMPERATURE_REPAIR_DOC = """Constante propia aunque coincida con la de razonamiento, porque no se movería con ella:
reparar es un bucle de REINTENTO, y un reintento a 0 no es un reintento. El prompt del
intento N+1 es la salida del intento N, así que un modelo voraz reconstruye el prompt
idéntico y escribe la respuesta idéntica — el presupuesto entero gastado en una réplica
byte a byte, que es el fallo que `parse_with_repair` documenta haber pagado una vez."""

_CONTEXT_WINDOW_DOC = """Son lo que hace que los tres modelos convivan, así que no son libres de crecer: medido en la
A40 a través de `/api/ps`, el modelo de juicio a 65536 + guardarraíl + embebedor suman
29.05 GiB de ~45 (19.49 + 5.49 + 4.07). La del guardarraíl a 8192 costaba 1 GiB de caché KV
y subía el total a 45.17, con el síntoma de que filtrar un encargo desalojaba al embebedor;
como mucho lee `GENERATION_INSTRUCTIONS_MAX_CHARS` (600 caracteres, ~200 tokens), así que
4096 es un margen de diez veces.

Con `think` encendido la ventana ya no la dimensiona el PROMPT sino prompt + deliberación,
y la deliberación es la mitad grande: el prompt más largo del pipeline son ~8 000 tokens y
una sola llamada de curación en `low` gasta ~13 000 solo en razonar.

Bajarla trunca EN SILENCIO, y trunca primero el razonamiento, así que el síntoma es una
respuesta vacía o a medio escribir y no una cola de prompt que falta."""

_CONTEXT_WINDOW_OVERRIDES_DOC = """La ventana de todo modelo de fase que no sea el guardarraíl o el embebedor. Sin ella, Ollama
dimensiona la caché KV a partir del Modelfile, lo que para `qwen3.6:35b-a3b-q8_0` (34.88 GiB
solo de pesos) es la diferencia entre caber junto al embebedor y no caber.

Un único valor y no uno por fase: el MoE está en las fases que leen documentos y el modelo
de juicio en las demás, y los dos nunca necesitan estar residentes a la vez — una
construcción carga el MoE una vez y el 27b vuelve en la siguiente generación.

65536 por la misma regla de arriba (prompt más deliberación allí donde una fase razona), y
porque bajarla trunca en silencio."""

_TRANSCRIBE_DOC = """Transcripción de una página a partir de su imagen renderizada — compartida por LOS TRES
constructores y por LOS DOS orígenes en bruto, así que hay una sola constante y no tres que
pudieran divergir y producir dos markdowns distintos del mismo fichero. A Docling le quedan
el `.docx` y el `.pptx`, que no tienen página que renderizar; sus IMÁGENES pasan también
por este modelo, una llamada por imagen y bajo el mismo bloque de reglas que la página
(`IMAGE_RULES`), con caché por hash de contenido.

Lo que sostiene la fidelidad aquí es el PROMPT, no el modelo. Medido: sin la cláusula de
copia carácter a carácter de `transcribe_page_prompt`, gemma4:31b reescribió `a -= 1` como
`a = a - 1`, se inventó `8 - (n-i)` donde había `(n-i)` y convirtió `x = x - 1` en
`x = x + 1` — lo que invierte la respuesta de la pregunta que estaba transcribiendo.
Debilitar esa instrucción reintroduce en silencio código corrupto en el banco.

Que el modelo de este puesto transcriba con la misma fidelidad que el medido NO está
comprobado. Es lo más barato de volver a comprobar de todo el pipeline (una página) y lo
más dañino si se falla: una transcripción corrupta aterriza en el banco como un ejercicio
cuya respuesta ha cambiado, y en el grafo como un concepto que el temario nunca enseñó."""

_TRANSCRIBE_SEAM_DOC = """La costura entre dos páginas transcritas por separado: el modelo CLASIFICA cómo se pegan
—`none`/`space`/`newline`/`paragraph`— y cuántas líneas iniciales de la segunda son
repetición mecánica de la maquetación. NUNCA reescribe el contenido: todo el prompt de
transcripción está construido sobre «copia carácter a carácter», y un segundo modelo con
permiso para redactar lo tiraría por la borda. La respuesta se verifica contra el catálogo
de separadores antes de creerla, y lo que no se pueda leer cae al detector determinista.

SIN MEDIR en calidad y en coste. Lo único comprobado es que el detector determinista solo
mete un salto de párrafo en mitad de una frase o de un bloque de código cada vez que un
ejercicio ocupa dos páginas. Una llamada por costura y solo cuando el detector no tiene
certeza, así que un documento de N páginas paga como mucho N-1 llamadas cortas."""


# Seed value only: it is read once, when a phase has no stored model. Nothing resolves
# through it at run time — every phase names its own and refuses an empty value.
_MAIN = "qwen3.8:27b-q8_0"
_MAIN_BY_ENGINE = (("cerebras+ollama", "gemma-4-31b"),)

OFFERED_GROUP = "Modelos generadores"

_FIXED_EFFORT_DOC = """QUÉ MODELOS NO DEJAN AJUSTAR EL ESFUERZO DE RAZONAMIENTO al pedir un ejercicio. Un nombre de
esta lista sigue ofreciéndose para generar y sigue razonando si el encargo lo enciende; lo
que pierde es el deslizador.

Es una propiedad medida del modelo, pero quien la mide es quien administra la instalación y
quien la sufre es quien pide el ejercicio, así que declararla es administrar y no programar.

LO QUE HAY QUE MEDIR PARA PONER UN NOMBRE AQUÍ: la misma llamada, temperatura 0 y semilla
fija, en cada nivel. Si dos niveles devuelven byte a byte lo mismo, el deslizador ofrece una
decisión que no cambia nada. Así se midió `gemma-4-31b` —de ahí que sea el único valor por
defecto, y sólo en el perfil de `cerebras+ollama`— y así se midió que `qwen3.8:27b-q8_0` SÍ
los distingue en tres.

LOS NOMBRES SON LOS DEL MOTOR y se comparan enteros, no por prefijo; de ámbito `engine` por
lo mismo que la lista de ofrecidos, porque `gemma-4-31b` no existe en Ollama.

NOMBRAR AQUÍ UN MODELO QUE NO SE OFREZCA no es un error y no se rechaza: se retira un modelo
mucho más a menudo de lo que se vuelve a medir su razonamiento.

CON QUÉ NIVEL SE LE LLAMA lo dice `generation.fixed_effort_levels`, que es el otro lado de
esta misma decisión."""


_FIXED_LEVEL_DOC = """CON QUÉ NIVEL SE LLAMA A UN MODELO DE ESFUERZO FIJO. Un mapa de nombre de modelo a nivel
(`low`, `medium`, `high`, `max`), vacío por defecto. Solo se lee para los nombres que están
en `generation.fixed_effort`: bloquear el deslizador y decidir con qué nivel se llama son la
misma decisión vista por sus dos caras, y quien la toma es quien administra la instalación.

UN MODELO BLOQUEADO SIN NIVEL DECLARADO se llama con el que resuelva el motor
(`inference.DEFAULT_THINK_EFFORT`, «low» en los dos). Sin este ajuste el navegador esconde
el deslizador pero sigue mandando el último nivel que tuviera puesto, así que el bloqueo
diría «lo fija la instalación» y lo fijaría el navegador.

ES UN AJUSTE APARTE de la lista de bloqueados, por la misma razón que la lista es aparte de
la de ofrecidos: quitar el candado un rato no debe tirar la medición.

UN NOMBRE QUE NO ESTÉ BLOQUEADO no es un error — se guarda y no se lee. De ámbito `engine`,
como las otras dos listas, porque los nombres son los del motor."""


_OFFERED_DOC = """QUÉ MODELOS PUEDE ELEGIR QUIEN PIDE UN ÍTEM, y en qué orden se le ofrecen. La redacción de
un ejercicio es la única fase cuyo modelo decide el encargo y no la instalación, porque es
la única en la que la diferencia se nota sin medir nada: un modelo servido en remoto
contesta en segundos y uno denso en la GPU local tarda minutos, y a cambio delibera. Lo que
sigue siendo de la instalación es ACOTAR la lista.

EL PRIMERO ES EL DE POR DEFECTO. `VARIANT_GENERATION_LLM` no es un ajuste: lo deriva
`settings.derived` del primer elemento, así que sigue existiendo para todo lo que no elige —
la CLI, un encargo que no nombra ninguno y los tres brazos del estudio, que comparan
arquitecturas y no modelos. La memoria tiene que decir cuál era el primero cuando se
grabaron las sesiones, igual que dice qué motor las produjo.

LOS NOMBRES SON LOS DEL MOTOR, así que el ajuste es de ámbito `engine` como los modelos de
fase: `gemma-4-31b` es el nombre de Cerebras y no existe en Ollama. Cambiar de motor cambia
la lista entera, y volver recupera la anterior intacta.

OFRECER UN MODELO NO LO DESCARGA: nada llama aquí a `ensure_models`, así que uno que no esté
en el disco aparece como «sin instalar» y falla en la primera llamada. Lo que sí hace es
PROTEGERLO — `required_models()` cuenta esta lista, de modo que el panel se niega a borrar
del disco un modelo que la generación ofrece.

Acotada por abajo a uno: vaciarla dejaría a la generación sin modelo. Por arriba no hay
límite, pero dos o tres es lo que cabe leerse antes de pedir un ítem."""

_PHASE_SHARED_DOC = """Una constante por llamada al modelo es la unidad de reajuste: apuntar varias al mismo modelo
es una decisión, no un colapso, y cualquier fase suelta puede moverse sin tocar las otras
veinte. NO HAY MODELO PRINCIPAL — cada fase nombra el suyo y ninguna admite un valor vacío,
así que lo que un constructor va a cargar se lee en el propio ajuste y no resolviendo un
defecto. Lo que sigue es la medición del modelo que la mayoría de las fases comparten.

""" + _RESIDENT_MODELS_DOC

_GUARDRAIL_DOC = """NO SE CAMBIA DESDE EL PANEL: es uno de los dos modelos que no sirven a ninguna fase del
pipeline, y los dos son decisiones cerradas con una medición detrás. El guardarraíl es un clasificador que lee como mucho
`GENERATION_INSTRUCTIONS_MAX_CHARS` (600 caracteres, ~200 tokens), así que su
`context_window.guardrail` está en 4096 —un margen de diez veces— y es parte de lo que hace
que los tres modelos residentes quepan a la vez. Cambiarlo desde un navegador es cambiar esa
aritmética sin volver a medirla.

Hay una segunda razón, y es del reparto de carriles: el guardarraíl está EXCLUIDO del cálculo
de `server/jobs/lanes.py` porque es pequeño, es local y convive con los demás. Ponerle un
nombre que `CEREBRAS_MODELS` enrute mandaría cada llamada del guardarraíl a la API remota sin
reservar el carril remoto — hoy es contrafáctico, porque la familia granite no está en el
catálogo de Cerebras, y deja de serlo en cuanto alguien escribe aquí otro nombre.

Sigue siendo un ajuste normal en todo lo demás: se lee de `config.json` como cualquier otro,
y editarlo a mano en el fichero (y reiniciar) sigue funcionando. Lo que se ha quitado es la
casilla.

""" + _RESIDENT_MODELS_DOC

_EMBEDDING_DOC = """NO SE CAMBIA DESDE EL PANEL, por la misma razón que el guardarraíl: el modelo de embebido
es una decisión cerrada y medida.
`qwen3-embedding:4b` sustituyó a `embeddinggemma` después de una sonda de 18 consultas sobre
14 conceptos en la que pasó de 15/18 a 18/18 en top-1 y más que dobló el margen entre el
acierto y el mejor fallo (0,069 → 0,152); el 8b se midió y se DESCARTÓ —mismo top-1, margen
algo peor, el doble de disco y de latencia—.

Lo que cuelga del nombre no es solo el índice. `EMBEDDER_SIMILARITY_THRESHOLD` está calibrado
sobre la escala de coseno de ESTE modelo (la mediana de todos los pares concepto-ítem es
0,382, y por eso el umbral subió de 0,3 a 0,40), y `EMBEDDING_QUERY_PREFIX` es una afirmación
por modelo: el mismo mecanismo se midió como INÚTIL en embeddinggemma. Cambiar el modelo sin
tocar ninguno de los dos deja un umbral y un prefijo que ya no describen nada, y el síntoma
—ítems que dejan de etiquetarse— aparece lejos de la causa. Además reembebe los dos índices
enteros, que es lo que dice su `Impact.REINDEX`.

Sigue leyéndose de `config.json` como cualquier otro ajuste; lo que se ha quitado es la
casilla.

""" + _RESIDENT_MODELS_DOC

_KG_DOMAINS_DOC = """La única fase cuya llamada tuvo que renunciar del todo al razonamiento cuando el modelo que
comparte con las demás pasó a ser uno que razona: pedirle que particionase el inventario entero hacía que
respondiera dentro del canal de razonamiento y no devolviera nada. Ahora solo nombra los
dominios — `assign_round` coloca los conceptos, tanda a tanda — y las dos llamadas siguen
acotadas por una gramática y por tanto sin pensar. La medición está en el sitio de la
llamada, en `knowledge_graph_builder/curation.py:curate_domains`. Aquí el que estaba mal no
era el modelo, así que esto sigue apuntando al mismo que las demás; era el pensar."""

_REPAIR_DOC = """Reparar es la única llamada que se dispara DESDE DENTRO de un bucle por elemento, así que
es también la única que nunca debe tener modelo propio: un modelo pequeño aparte no cabe
junto al de extracción en esta máquina, y cada reparación lo desalojaría y pagaría dos
cargas de ~10 s en mitad de un corpus. Se mueva lo que se mueva, esta debe quedarse en el
mismo modelo que la fase desde cuyo bucle se dispara."""

def _phase_doc(sentence: str) -> str:
    """Return one phase model's documentation: the shared preamble, then its own sentence."""
    return _PHASE_SHARED_DOC + "\n\n" + sentence


SETTINGS: list[Setting] = [
    Setting(
        key="engine.name",
        name="INFERENCE_ENGINE",
        kind="str",
        default="ollama",
        group="Motor",
        impact=Impact.ENGINE,
        choices=("ollama", "cerebras+ollama"),
        doc="""Qué implementación respalda generate()/embed()/embed_batch(). La lógica de negocio nunca
llama a un SDK: todo pasa por `variatio.core.inference`.

'cerebras+ollama' es un motor compuesto — el catálogo de Cerebras y lo que nombre
CEREBRAS_MODELS van a su API, y todo lo demás, guardarraíl y embebedor incluidos, sigue en
Ollama. La residencia, la descarga de la GPU y el pull/borrado son siempre de la mitad
Ollama: en Cerebras no hay nada que cargar.

CADA MOTOR TIENE SU PERFIL: los ajustes de ámbito «engine» se guardan bajo
`profiles.<motor>`, así que cambiar de motor cambia el perfil entero y volver recupera el
anterior tal cual.

Elegir 'cerebras+ollama' saca los prompts y el corpus de la máquina hacia un servicio
externo, y revoca —solo para quien lo active— el «open-source only / stack local» del
registro de decisiones. La memoria tiene que decir con qué motor se produjo lo que
reporte.""",
    ),
    Setting(
        key="engine.cerebras_base_url",
        name="CEREBRAS_BASE_URL",
        kind="str",
        default="https://api.cerebras.ai/v1",
        group="Motor",
        impact=Impact.ENGINE,
        env="CEREBRAS_BASE_URL",
        editable=False,
        doc="""La raíz OpenAI-compatible de la API de Cerebras. Solo la usa el motor 'cerebras+ollama'.

SOLO DEL ENTORNO: no se puede cambiar en caliente. El cliente se construye con esta raíz y
con `Authorization: Bearer CEREBRAS_API_KEY` en la cabecera de cada llamada, así que quien
pudiera reescribirla desde el panel recibiría en su propio host la clave que
`engine.cerebras_api_key` marca `secret` y `editable=False` precisamente para que nunca
salga de la API. Cambiar la dirección es cambiar a quién se le entrega la credencial, y eso
no es una preferencia de configuración.

No es un secreto —la raíz pública de Cerebras no lo es—, así que se sigue guardando en
`config.json`; lo que no puede es ser reescribible en caliente. Apuntar a un proxy o a un
mock en pruebas sigue funcionando: se hace por la variable de entorno `CEREBRAS_BASE_URL`
(o el `.env` ignorado por git).""",
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
        doc="""Qué modelos enruta a Cerebras el motor 'cerebras+ollama' ADEMÁS de su catálogo: todo modelo
que la API lista en `/models` se sirve allí sin declararlo aquí. Esta lista es lo que manda
cuando el catálogo no se puede leer (se recuerda la última lectura, y sin ninguna vale esto)
y lo que nombra un modelo que el catálogo no lista. Todo lo demás va a Ollama.

`gemma-4-31b` por defecto: el id exacto del catálogo de Cerebras (~1.850 tok/s, ventana de
131.072, salida máxima 40.000, structured outputs con `strict` y razonamiento vía
`reasoning_effort`).

LAS CUOTAS SON POR MODELO, y las de la cuenta no son las que anuncia la página del modelo.
Medido contra la API: `gemma-4-31b` declara 500 peticiones/min y 250.000 tokens
uncached/min, mientras la cuenta admite 5 peticiones/min, 30.000 tokens/min, 2.400
peticiones/día y 1.000.000 de tokens/día — un build entero no cabe ahí. Los headers no
sirven para averiguarlo: `remaining-*` también cuenta contra la cuota del MODELO, así que
quien lo administra son los CEREBRAS_MAX_* de abajo, y son un tope rígido.""",
    ),
    # The four ceilings that actually bind, seeded with the free tier's figures. They are a
    # hard cap: no Cerebras header states the account's own quota — `limit-*` and
    # `remaining-*` both count against the MODEL's — so a header may lower what we believe
    # is left, never raise the ceiling.
    Setting(
        key="engine.cerebras_max_requests_minute",
        name="CEREBRAS_MAX_REQUESTS_MINUTE",
        kind="int",
        default=5,
        minimum=1,
        group="Motor",
        impact=Impact.NONE,
        doc="""Cuántas peticiones por minuto admite la cuenta para CADA modelo enrutado a Cerebras.

5 en el nivel gratuito (medido: la primera llamada dejó
`x-ratelimit-remaining-requests-minute` en 4, mientras el header `limit-` anunciaba 1000).
Es el techo que más ata: 5/min es un suelo de 12 segundos entre llamadas, así que un build
con cientos de llamadas pasa a durar horas. El limitador espera a que ruede la ventana en
vez de comerse un 429, y lo dice en «Motor».

Es un TOPE RÍGIDO: manda este número y nada lo sube. Dejar que la API lo levante es lo que
rompe el limitador — `remaining-*` cuenta contra la cuota del MODELO, así que la primera
respuesta subiría el techo a 499 y no se retendría ni una llamada más. Lo que la API informe
solo puede BAJAR lo que creemos que queda.

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
el nivel gratuito, medido.

Se cuentan con el `usage` exacto que trae cada respuesta, no con los headers: medido, el
contador de tokens del servidor va con retraso — una llamada de 74 tokens y otra de 20
movieron `remaining-tokens-day` exactamente 6 las dos veces. El header solo se usa para
BAJAR lo que creemos que queda, nunca para subirlo.

Es un TOPE RÍGIDO: manda este número y nada lo sube. La API solo se lee para BAJAR lo que
creemos que queda; dejar que un `remaining` generoso levante el techo es lo que deja al
limitador sin efecto desde la primera llamada.""",
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
nivel gratuito (medido: `remaining-requests-day` en 2399 tras una llamada, mientras el header
`limit-` anunciaba 720.000).

La ventana es deslizante de 24 h, no un día natural: la API no manda ningún header de
`reset`, así que la única ventana reconstruible es la que sale de nuestras propias marcas
de tiempo. Ser deslizante es lo conservador — nunca gasta de más.

Es un TOPE RÍGIDO: manda este número y nada lo sube. La API solo se lee para BAJAR lo que
creemos que queda; dejar que un `remaining` generoso levante el techo es lo que deja al
limitador sin efecto desde la primera llamada.""",
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
nivel gratuito, medido.

Es el techo que decide si un build cabe: con prompts de ~8.000 tokens salen unas 125
llamadas al día. El desglose por fase de «Motor» existe para responder a la pregunta que
sigue — QUÉ fase se lo está comiendo — y se descarga en CSV.

Es un TOPE RÍGIDO: manda este número y nada lo sube. La API solo se lee para BAJAR lo que
creemos que queda; dejar que un `remaining` generoso levante el techo es lo que deja al
limitador sin efecto desde la primera llamada.""",
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
        editable=False,
        doc="""El host de Ollama como `host:puerto` (o una URL `http(s)://` completa). El registro guarda
el valor desnudo y el `http://` se antepone en otro sitio, no aquí.

SOLO DEL ENTORNO, y no por comodidad: es la dirección a la que este proceso manda TODAS sus
llamadas al motor, así que dejarla reescribible sería dejar que la configuración decida a
qué máquina de la red interna se llama y qué se devuelve como si fuera del modelo.

Apuntarlo a otra máquina, o al puerto local que abra un túnel SSH, se hace por `OLLAMA_HOST`
(o el `.env`).""",
    ),
    Setting(
        key="models.guardrail",
        name="GUARDRAIL_LLM",
        kind="str",
        default="granite4.1-guardian:8b-q4_K_M",
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        editable=False,
        doc=_GUARDRAIL_DOC,
    ),
    Setting(
        key="models.embedding",
        name="EMBEDDING_LLM",
        kind="str",
        default="qwen3-embedding:4b",
        group="Modelos",
        impact=Impact.REINDEX,
        scope="engine",
        editable=False,
        doc=_EMBEDDING_DOC,
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
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_TRANSCRIBE_DOC,
    ),
    Setting(
        key="models.phases.transcribe_seam",
        name="TRANSCRIBE_SEAM_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_TRANSCRIBE_SEAM_DOC,
    ),
    Setting(
        key="models.phases.ep_scan",
        name="EP_SCAN_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de escaneo del generador de perfil de ejemplares (exemplars_profile_builder)."
        ),
    ),
    Setting(
        key="models.phases.ep_consolidate",
        name="EP_CONSOLIDATE_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de consolidación del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.ep_context",
        name="EP_CONTEXT_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de contexto del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.eb_extract",
        name="EB_EXTRACT_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de extracción del generador del banco de ejemplares."),
    ),
    Setting(
        key="models.phases.kg_extract",
        name="KG_EXTRACT_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de extracción del constructor del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_merge",
        name="KG_CLEAN_MERGE_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de fusión de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_drop",
        name="KG_CLEAN_DROP_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc("Fase de descarte de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_units",
        name="KG_UNITS_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de segmentación del temario del grafo de conocimiento: lee el índice de "
            "encabezados del corpus y dice cuáles abren unidad didáctica."
        ),
    ),
    Setting(
        key="models.phases.kg_domains",
        name="KG_DOMAINS_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_KG_DOMAINS_DOC,
    ),
    Setting(
        key="models.phases.kg_domains_leftovers",
        name="KG_DOMAINS_LEFTOVERS_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de colocación de los conceptos sobrantes de la asignación de dominios "
            "del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_domain",
        name="KG_LINK_DOMAIN_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de enlace de relaciones dentro de un mismo dominio del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_cross_domain",
        name="KG_LINK_CROSS_DOMAIN_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de enlace de relaciones entre dominios distintos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_context",
        name="KG_CONTEXT_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de síntesis del contexto de la materia a partir del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.description_generation",
        name="DESCRIPTION_GENERATION_LLM",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de generación de descripciones de conceptos del grafo de conocimiento. "
            "La llamada no la hace el constructor: la escribe el embebedor al levantarse, "
            "así que la pagan el indexado, el etiquetado, la generación y la evaluación."
        ),
    ),
    Setting(
        key="models.phases.kg_taggable",
        name="KG_TAGGABLE_MODEL",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de revisión de etiquetabilidad de los conceptos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.concept_tagger",
        name="CONCEPT_TAGGER_LLM",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_phase_doc(
            "Fase de etiquetado de conceptos sobre el banco de ejemplares, en el pipeline en "
            "tiempo de ejecución."
        ),
    ),
    Setting(
        key="generation.models",
        name="GENERATION_MODELS",
        kind="list[str]",
        default=[_MAIN],
        group=OFFERED_GROUP,
        impact=Impact.CONTEXTS,
        scope="engine",
        min_items=1,
        engine_defaults=(("cerebras+ollama", ["gemma-4-31b"]),),
        doc=_OFFERED_DOC,
    ),
    Setting(
        key="generation.fixed_effort",
        name="FIXED_EFFORT_MODELS",
        kind="list[str]",
        default=[],
        group=OFFERED_GROUP,
        # Nothing on the server reads it: it travels to the browser through `/api/health`
        # and decides one control. No context to rebuild, no index to re-embed.
        impact=Impact.NONE,
        scope="engine",
        engine_defaults=(("cerebras+ollama", ["gemma-4-31b"]),),
        doc=_FIXED_EFFORT_DOC,
    ),
    Setting(
        key="generation.fixed_effort_levels",
        name="FIXED_EFFORT_LEVELS",
        kind="dict[str,str]",
        default={},
        group=OFFERED_GROUP,
        # Read by the same two readers as the list it accompanies — the generate screen and
        # the handler that resolves a commission. No context to rebuild, no index to
        # re-embed.
        impact=Impact.NONE,
        scope="engine",
        choices=("low", "medium", "high", "max"),
        doc=_FIXED_LEVEL_DOC,
    ),
    Setting(
        key="models.phases.admissibility",
        name="ADMISSIBILITY_LLM",
        kind="str",
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
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
        default=_MAIN,
        group="Modelos",
        impact=Impact.CONTEXTS,
        scope="engine",
        engine_defaults=_MAIN_BY_ENGINE,
        doc=_REPAIR_DOC,
    ),
]
