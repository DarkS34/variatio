EXEMPLARS_PROFILE_FIELD_NAMING = """\
- CLAVES EN ESPAÑOL, SIN TILDES (INNEGOCIABLE): los nombres de campo — las claves del objeto `fields` — van en ESPAÑOL, en snake_case y en ASCII puro; cada uno debe casar con `^[a-z][a-z0-9_]*$`. Español sí, tildes no: se convierten en identificadores de código, así que escribe `solucion` y no «solución», `explicacion` y no «explicación», `disenio` o `diseno` y nunca «diseño». Sin ñ, sin espacios, sin mayúsculas, sin guiones.
- VOCABULARIO CANÓNICO: los nombres deben ser estables entre asignaturas distintas, para que un ejercicio de programación y uno de física se describan con las mismas claves. Si un campo desempeña uno de estos roles, usa EXACTAMENTE ese nombre en vez de inventar un sinónimo:
  · el texto principal que plantea al alumno la tarea, el problema o la pregunta → `enunciado`
  · la respuesta, resolución o resultado esperado → `solucion`
  · el grado de dificultad o exigencia → `nivel_dificultad`
  · el título o nombre corto del ejercicio → `titulo`
  · las alternativas de una pregunta cerrada → `opciones`
  · cuál de las alternativas es la correcta → `respuesta_correcta`
  · el material de partida que se le entrega ya escrito al alumno (código con un fallo, plantilla a completar, texto a corregir, datos de entrada) → `material_base`
  · la explicación didáctica o justificación de la respuesta → `explicacion`
  Inventa un nombre nuevo SOLO si el rol del campo no aparece en esta lista; entonces aplícale las mismas reglas. No añadas sufijos que describan el soporte concreto de esta muestra: `solucion`, no `codigo_solucion`.
- NOMBRES RESERVADOS, prohibidos como campo: `item_type`, `id`, `source`, `concepts`, `primary_concept`. Los usa el propio sistema.
- NADA DE CAMPOS DE MODALIDAD: no declares un campo `tipo`, `tipo_item`, `modalidad`, `formato` ni equivalente. La modalidad del ejercicio ES la clave de su entrada en `item_types`; un campo así la duplicaría.\
"""


EXEMPLARS_PROFILE_SCHEMA_GRAMMAR = """\
`schema` es SIEMPRE un objeto JSON. Nunca una lista, nunca una cadena suelta. TODAS sus claves van DENTRO de ese objeto; ninguna como hermana de `schema`. Vocabulario permitido, y ninguno más:
- `"type"`: uno de `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`.
- `"type"` como LISTA de esos mismos nombres, para valores que admiten ausencia: {"type": ["string", "null"]}. Dentro de `type` todo son NOMBRES DE TIPO entrecomillados, `"null"` incluido.
- con `"type": "array"`, la clave `"items"` va DENTRO del schema: {"type": "array", "items": {"type": "string"}}. Una lista que puede faltar combina ambas formas: {"type": ["array", "null"], "items": {"type": "string"}}.
- `"enum"`: lista no vacía de VALORES literales permitidos (no nombres de tipo), para campos categóricos: {"enum": ["básico", "intermedio", "avanzado"]}. SOLO aquí, y solo si el campo admite ausencia según la POLÍTICA DE NULOS, puede aparecer el literal JSON `null` como un valor más de la lista.
- restricciones opcionales, dentro del mismo objeto: `"minLength"`, `"maxLength"`, `"minimum"`, `"maximum"`, `"default"`.

Formas VÁLIDAS de `schema` — no hay ninguna más:
  {"type": "string"}
  {"type": ["string", "null"]}
  {"type": "array", "items": {"type": "string"}}
  {"enum": [1, 2, 3, 4]}

Formas INVÁLIDAS (errores reales ya cometidos; no los repitas):
  ["string", "null"]                    → falta el envoltorio: es {"type": ["string", "null"]}
  {"type": "array"} + `items` hermana   → `items` va dentro del objeto `schema`
  {"type": "str"} / "text" / "list"     → esos nombres de tipo no existen\
"""


def scan_item_types_prompt(content: str, location: str = "", excerpt_chars: int = 400) -> str:
    where = f"\nFragmento procedente de: {location}\n" if location else ""
    return f"""\
Analiza un FRAGMENTO de material docente en bruto (ejercicios, problemas, actividades, preguntas) e inventaria las MODALIDADES de ejercicio que aparecen en él.

Una modalidad es una FORMA de plantear la tarea al alumno, definida por la anatomía del ejercicio: qué piezas de información lo componen. Ejemplos de modalidades distintas: una pregunta cerrada con alternativas; un problema numérico que pide calcular un resultado a partir de unos datos; un encargo de escribir un programa desde cero; un material de partida (un código, un texto, un esquema) con un fallo que hay que localizar y corregir; un supuesto práctico que hay que analizar y resolver razonando por escrito.

Este fragmento es SOLO UNA PARTE del material: no intentes describir la asignatura entera ni adivinar modalidades que no estén aquí. Inventaria lo que VES en este fragmento, y nada más. Otro paso posterior reunirá los inventarios de todos los fragmentos.
{where}
# QUÉ CUENTA COMO EJERCICIO
Cuenta toda unidad que el material PLANTEA AL ALUMNO COMO TAREA. No cuentan: la exposición teórica, las explicaciones y definiciones, los ejemplos que ilustran una explicación sin pedir nada, los índices, los objetivos de la unidad, las rúbricas ni la bibliografía. Si el fragmento no plantea ninguna tarea, devuelve `{{"types": []}}`.

# DOS MODALIDADES SON LA MISMA SI SE RELLENAN IGUAL
La prueba, aplícala antes de separar nada: ¿se rellenarían las MISMAS piezas de información al redactar uno y otro? Si sí, es UNA modalidad, por muy distinto que sea el rótulo del documento.
- «Ejercicio propuesto» y «Ejercicio resuelto» son la MISMA modalidad: que uno traiga la solución y el otro no es un campo vacío, no una modalidad nueva.
- «Ejercicio básico» y «Ejercicio avanzado» son la MISMA modalidad: la dificultad es un campo, no una modalidad.
- «Ejercicio 3.1» y «Ejercicio 7.2» son la misma modalidad: la numeración y el tema no la cambian.
- Una pregunta con alternativas y un encargo de programar SÍ son modalidades distintas: la primera necesita una lista de opciones y una respuesta correcta; el segundo, un enunciado y código.
Ante la duda, AGRUPA. Separar de más fragmenta el material en modalidades anecdóticas; agrupar de más se corrige después.

# QUÉ DEBES PRODUCIR
Un único objeto JSON:

{{
  "types": [
    {{
      "key": "<clave en espanol, snake_case, sin tildes>",
      "label": "<nombre legible de la modalidad, en el idioma del material>",
      "signals": "<como se reconoce en el documento: rotulos, encabezados, estructura visible>",
      "fields": ["<nombre_de_campo>", "..."],
      "excerpt": "<hasta {excerpt_chars} caracteres literales del ejemplar mas representativo>"
    }}
  ]
}}

- `key`: en español, `^[a-z][a-z0-9_]*$`, sin tildes ni ñ. Nombra la MODALIDAD, no el tema: `pregunta_test`, `problema_numerico`, `escritura_codigo`, `correccion_error`, `analisis_caso`, `problema_teorico`.
- `fields`: las piezas que componen ESTA modalidad, con los nombres canónicos de abajo. Solo las que el fragmento muestra de verdad.
- `excerpt`: copia LITERAL, recortada a {excerpt_chars} caracteres, del ejemplar que mejor representa la modalidad. Es lo que verá el paso siguiente para redactar las instrucciones de extracción, así que elige uno completo y típico, no el más raro. Escapa saltos (`\\n`) y comillas (`\\"`).

# NOMBRES DE CAMPO
{EXEMPLARS_PROFILE_FIELD_NAMING}

# REGLAS DE SALIDA
- Un único objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Si el fragmento no plantea ninguna tarea al alumno, devuelve `{{"types": []}}`.

<<<FRAGMENTO>>>
{content}
<<<FIN>>>

JSON:"""


def consolidate_exemplars_profile_prompt(findings: str, max_types: int) -> str:
    return f"""\
Has recibido el INVENTARIO de modalidades de ejercicio que un escaneo previo encontró, fragmento a fragmento, en todo el material docente en bruto de una asignatura. Consolídalo en el PERFIL DE EJEMPLARES definitivo.

El perfil es la ÚNICA pieza que instancia el sistema para una asignatura concreta: el mismo motor genera ejercicios de programación, problemas de física, preguntas de test o supuestos prácticos, pero siempre material de aprendizaje. Declara, de forma abstracta, la anatomía de cada modalidad de ejercicio de esta asignatura: qué campos la componen, de qué tipo son, cómo se extraen de un documento y cómo se redactaría uno nuevo.

El inventario viene de fragmentos analizados por separado, así que TRAE DUPLICADOS: la misma modalidad aparecerá con claves distintas, con conjuntos de campos que se solapan y con etiquetas parecidas. Unificarlos es tu trabajo principal.

# QUÉ DEBES PRODUCIR
Un único objeto JSON con EXACTAMENTE estas claves de nivel superior:

{{
  "item_types": {{
    "<clave_de_modalidad>": {{
      "label": "<nombre legible>",
      "description": "<que es esta modalidad y como se reconoce>",
      "primary_field": "<nombre de uno de sus campos>",
      "embed_fields": ["<primary_field>", "<otro campo que el alumno RECIBE>"],
      "general_generation_rules": ["<regla>", "..."],
      "fields": {{
        "<nombre_de_campo>": {{
          "schema": {{ "type": "string" }},
          "description": "...",
          "guidance": {{ "extraction": "..." }}
        }}
      }}
    }}
  }}
}}

# QUÉ NO DEBES DECLARAR
Nada sobre la asignatura en sí: ni la materia, ni el nivel educativo, ni el idioma, ni convenciones generales de la carrera. Eso se escribe aparte, en prosa, en otro paso del sistema. Aquí describes ÚNICAMENTE la anatomía de las modalidades. No añadas claves de nivel superior: `item_types` es la única.

# item_types — CUÁNTAS MODALIDADES
- FUSIONA SIN MIEDO. Dos entradas del inventario son la MISMA modalidad si se rellenan las mismas piezas al redactarlas. Que una traiga solución y otra no, que una sea básica y otra avanzada, que estén en unidades distintas: nada de eso separa. Al fusionar, quédate con la clave más clara y con la UNIÓN de sus campos (los que falten en una variante son campos que admiten `null`, ver POLÍTICA DE NULOS).
- SEPARA SOLO CUANDO CAMBIA LA ANATOMÍA. Una modalidad distinta necesita campos que la otra no tiene sentido que tenga, o una forma de redactarse claramente distinta. Prueba: si las dos comparten `fields` y sus `general_generation_rules` saldrían casi iguales, es una sola.
- DESCARTA LO ANECDÓTICO. Una modalidad que aparece una vez en todo el corpus y que encaja razonablemente dentro de otra, va dentro de la otra. Solo sobrevive por su cuenta la que el material usa de verdad como formato propio.
- COMO MUCHO {max_types} modalidades. Si te salen más, es que estás separando por tema o por dificultad en vez de por anatomía: vuelve a fusionar. Lo habitual son 1-3.
- Ordénalas de más frecuente a menos: la primera es la que el sistema usa por defecto.

Para cada modalidad:
- `label`: su nombre legible, en el idioma del material («Pregunta tipo test», «Corrección de errores»).
- `description`: qué es y cómo se reconoce. Lo lee tanto el extractor —para decidir a qué modalidad pertenece cada ejercicio del documento— como el generador. Sé discriminante: describe lo que la distingue de las demás modalidades del perfil, no lo que tienen en común.
- `general_generation_rules`: cómo se redacta un ejercicio NUEVO de esta modalidad. Es la parte más importante de lo que produces y tiene sección propia más abajo — léela antes de escribirlas.

# fields — CÓMO SE LLAMAN
{EXEMPLARS_PROFILE_FIELD_NAMING}
- COHERENCIA ENTRE MODALIDADES: si dos modalidades tienen un campo con el mismo papel, debe llamarse IGUAL en las dos (`enunciado` en todas, no `enunciado` en una y `pregunta` en otra).

# fields — CUÁLES INCLUIR
Un campo por cada pieza de información ESENCIAL que compone un ejercicio de esa modalidad.

- MENOS ES MÁS: incluye el conjunto MÍNIMO de campos que capture por completo un ejercicio. Cada campo debe ganarse su sitio: NO añadas campos especulativos, redundantes, derivables de otros ni presentes solo de forma anecdótica. Al mismo tiempo, NO omitas nada esencial para representar o redactar el ejercicio (como mínimo, el que porta la carga semántica principal). Ante la duda entre añadir un campo marginal o dejarlo fuera, déjalo fuera. Lo habitual son 3-5 campos por modalidad.
- PRUEBA DE DERIVABILIDAD (aplícala a CADA campo antes de incluirlo): si su valor puede calcularse a partir de los demás campos sin volver a mirar el documento, NO es un campo — se deduce, y sobra. Descarta en particular: banderas que solo indican si otro campo tiene valor o está vacío (`is_solved`, `tiene_solucion`: eso ya lo dice que `solucion` sea null); contadores, longitudes o tamaños de otro campo; y campos cuyo valor sea una reformulación de otro. Si al describir un campo necesitas mencionar otro campo para definirlo, es señal casi segura de que es derivable.
- NADA DE CONCEPTOS NI TEMAS: no declares campos de conceptos, temas, materia o etiquetas temáticas (`temas`, `conceptos`, `palabras_clave`…). Qué concepto del currículo practica cada ejercicio lo anota el sistema aguas abajo contra un grafo de conocimiento, y un campo así se solaparía con esa anotación. Lo que sitúe a la asignatura entera (materia, nivel educativo, idioma) no va en `fields` ni en ningún otro sitio de este perfil.
- COBERTURA MÍNIMA: el perfil debe bastar para (a) representar el ejercicio, (b) recuperarlo semánticamente y (c) redactar uno nuevo PARAMETRIZADO. En la práctica eso casi siempre exige: el enunciado que porta la carga semántica (el `primary_field`, obligatorio); la solución esperada, cuando el material la trae o la admite; y al menos un campo CLASIFICATORIO que se pueda fijar como parámetro al pedir un ejercicio nuevo (dificultad, nivel…). Si la muestra no etiqueta ese eje clasificatorio pero es deducible observando el ejercicio, decláralo igualmente y define el criterio (ver POLÍTICA DE NULOS).

Para cada campo:
- `schema`: la forma del valor.
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}
- `description`: la NATURALEZA intrínseca del campo (qué representa), en el idioma de instrucción de la asignatura.
- `guidance.extraction`: cómo EXTRAER este campo de un documento fuente. **Redáctala con más detalle y precisión que el resto de textos**: alimenta un proceso de extracción posterior que debe ser exacto y determinista, así que sé concreto y accionable, y apóyate en los fragmentos literales del inventario. Cubre, cuando apliquen: qué copiar y si va LITERAL o normalizado; los LÍMITES con los campos vecinos (qué pertenece a este campo y qué NO, para que no se solapen); los marcadores o encabezados concretos del documento que lo delimitan (p. ej. "Solución:", "Ejercicios propuestos"); qué EXCLUIR (etiquetas de enumeración, cabeceras de sección, artefactos de página); y, solo en campos que admitan ausencia según la POLÍTICA DE NULOS, cuándo el campo va a null. Aplica a todo campo que pueda localizarse en el material.
- `guidance.generation`: **NO la escribas. Nunca.** Existe en el formato, pero es un campo que rellena a mano quien administra la asignatura cuando un campo concreto necesita un matiz que las reglas no cubren. Tú deja en `guidance` únicamente `extraction`. Lo que sepas sobre cómo se REDACTA esta modalidad va entero en `general_generation_rules`.

# POLÍTICA DE NULOS — DEPENDE DE SI EL CAMPO SE COPIA O SE DEDUCE
La pregunta no es «¿suele traer esta modalidad este campo?», sino «¿podría existir UN SOLO ejercicio de esta modalidad al que le falte?». La respuesta depende de dónde sale el valor, y son dos casos con reglas OPUESTAS.

## Campos que se COPIAN del documento (enunciado, solución, material de partida, opciones, explicación)
Admiten `null` SALVO que el ejercicio no se sostenga sin ellos. La única excepción segura es el `primary_field`: un ejercicio sin enunciado no es un ejercicio. Declara obligatorio un campo copiado solo cuando su ausencia rompería la modalidad entera: las `opciones` de una pregunta cerrada, el código que hay que arreglar en una corrección de errores.

Los dos errores NO cuestan lo mismo, y esa asimetría es la regla:
- Declararlo nulable cuando el contenido siempre está no cuesta nada: el extractor lo rellenará siempre, porque siempre lo encuentra.
- Declararlo obligatorio cuando puede faltar OBLIGA A INVENTARLO. Aguas abajo este campo entra como obligatorio en la gramática del extractor, así que ante un ejercicio que no lo trae el modelo no puede responder «no está»: lo fabrica, y sale material docente falso indistinguible del real.

Dos indicios que NO demuestran que un campo copiado esté siempre:
- Que el inventario no traiga ni un ejemplar sin él. El inventario es una MUESTRA de fragmentos, no el corpus entero.
- Cómo se llaman los documentos. Un corpus entero de archivos «soluciones» resuelve típicamente la parte teórica y deja los enunciados de la parte práctica en crudo.

## Campos que se DEDUCEN observando el ejercicio (los CLASIFICATORIOS: nivel, categoría…)
Aquí `null` ES EL ÚLTIMO RECURSO, por la razón contraria: su valor no hay que encontrarlo en el documento, hay que juzgarlo, y siempre se puede juzgar. Que el documento no lo ETIQUETE explícitamente NO es motivo para admitir `null`: es motivo para definir un criterio que permita DEDUCIRLO del propio contenido.
- NO lo declares opcional por defecto. Si su valor es deducible observando el ejercicio, el campo NO lleva `null`.
- Su `description` debe incluir un CRITERIO INTERNO DE CLASIFICACIÓN propio de la asignatura: enumera cada valor posible junto a las SEÑALES OBSERVABLES que lo identifican (qué construcciones, qué complejidad, qué exigencia o qué conocimientos previos supone el ejercicio). El criterio debe cubrir TODO el material, de modo que cualquier ejercicio pueda clasificarse sin excepción.
- Su `guidance.extraction` debe decir: si el documento trae una etiqueta explícita, se usa esa; si NO la trae, se aplica al contenido del ejercicio el criterio definido en `description`. NUNCA "si no hay etiqueta, null".

# general_generation_rules — CÓMO ESCRIBE ESTA ASIGNATURA (LA PARTE QUE MÁS IMPORTA)
Es lo ÚNICO que el perfil le dice al generador sobre cómo se redacta un ejercicio de esta modalidad. Aquí no hay una segunda oportunidad campo a campo: lo que no esté en estas reglas, el generador no lo sabe. Dedícale más atención que a ninguna otra parte del perfil.

Escríbelas mirando los `excerpt` del inventario y preguntándote qué tienen en común TODOS los ejemplares de esta modalidad. Una regla es una CONVENCIÓN OBSERVADA en este material, no una opinión tuya sobre didáctica.

- CADA REGLA DEBE SER COMPROBABLE. Tiene que poder leerse un ejercicio ya escrito y decir si la cumple o no. «El enunciado debe ser claro» no es comprobable y no es una regla; «el enunciado debe especificar la entrada, la salida y el comportamiento esperado» sí lo es.
- NOMBRA EL CAMPO al que se aplica cuando la regla sea de un campo concreto («la solución debe…», «el enunciado debe…»). No hay guía por campo que lo diga en tu lugar, así que la regla tiene que decirlo ella.
- CUBRE, cuando el material los muestre de forma consistente: qué debe contener obligatoriamente cada campo redactado; la NOTACIÓN y las convenciones de formato propias de la asignatura (cómo se documenta, qué encabezados, qué unidades, qué símbolos); la EXTENSIÓN y el alcance típicos de un ejemplar; y las relaciones de COHERENCIA entre campos (que la solución responda exactamente a lo que pide el enunciado, que el material de partida y la solución encajen).
- NADA DE DIDÁCTICA GENÉRICA. «Debe fomentar el pensamiento crítico», «debe ser motivador», «adecuar la dificultad al nivel»: de todo eso ya se ocupa el generador, que sabe de didáctica y no sabe de esta asignatura. Tú aportas lo segundo. Si una regla valdría igual para cualquier asignatura del mundo, sobra.
- NADA DE CONTENIDO. No fijes el tema, el ámbito ni los conceptos de los ejercicios: eso lo decide cada encargo contra el grafo del currículo. Las reglas hablan de la FORMA.
- SOLO DE ESTA MODALIDAD. Una regla que solo tiene sentido aquí (exigir docstring y bloque de prueba, exigir el resultado con sus unidades y cifras significativas) va SOLO aquí. Si es cierta de todas las modalidades por igual, es que describe la asignatura entera y no aporta nada en ninguna.
- CANTIDAD: entre 3 y 8. Menos de 3 casi siempre significa que no has mirado los ejemplares; más de 8, que estás desmenuzando una regla en sus consecuencias o colando didáctica genérica.

# primary_field
Uno por modalidad. El nombre del campo que porta la CARGA SEMÁNTICA principal del ejercicio: el enunciado, el texto que plantea la tarea al alumno. Aguas abajo es lo que se compara contra el grafo del currículo para decidir qué concepto practica cada ejercicio, así que debe ser el campo que se lee para saber de qué va el ejercicio. Debe ser una de las claves de los `fields` de ESA modalidad.

# embed_fields
La lista de campos que, JUNTOS, se leen para decidir qué concepto del currículo practica el ejercicio. Es una lista porque en algunas modalidades el enunciado por sí solo no dice de qué va el ejercicio: en «¿qué imprime el siguiente código?» el enunciado es una fórmula fija y el concepto está en el CÓDIGO QUE SE LE ENTREGA al alumno.

- Empieza SIEMPRE por el `primary_field`, y añade después solo los campos que el alumno RECIBE junto al enunciado y sin los cuales el ejercicio no se entiende: el material de partida, el fragmento de código a analizar, las opciones de una pregunta de test.
- NUNCA incluyas la SOLUCIÓN ni la explicación de la respuesta. Es la respuesta, no el ejercicio: al medirlo, incluirla EMPEORÓ el acierto. Tampoco incluyas campos clasificatorios (dificultad, nivel): no aportan concepto y añaden ruido idéntico en todos los ejercicios.
- Prueba: tapa el campo. Si al leer lo que queda ya no puede decirse qué concepto se practica, el campo va en la lista. Si sigue pudiendo decirse, se queda fuera.
- Si el enunciado se basta solo, `embed_fields` es exactamente `["<primary_field>"]`.

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Los nombres de campo (claves de `fields`) y las claves de `item_types` SIEMPRE en español, snake_case, sin tildes ni ñ. El resto de texto de cara al humano (`label`, `description`, `guidance`, `general_generation_rules`) en el idioma del material.
- Incluye solo los campos ESENCIALES: menos es más, pero sin dejar fuera nada imprescindible. Ninguno derivable de otro. `null` en todo campo copiado del documento que pueda faltar en algún ejercicio, y en ninguno deducible.
- Cada valor de texto en UNA SOLA LÍNEA: sin saltos de línea reales, sin backticks ni bloques de código dentro de los strings. Escapa saltos (`\\n`) y comillas internas (`\\"`).
- ANTES DE RESPONDER, verifica las siete cosas que más fallan: (1) el valor de cada `schema` es un OBJETO `{{...}}`, nunca una lista; (2) cada clave de `fields` y cada clave de `item_types` casa con `^[a-z][a-z0-9_]*$`; (3) el `primary_field` de cada modalidad es exactamente una de las claves de SUS `fields`; (4) `embed_fields` empieza por el `primary_field`, solo nombra campos de SUS `fields` y no incluye la solución; (5) no hay dos modalidades que se rellenen igual; (6) NINGÚN `guidance` lleva la clave `generation`, y cada modalidad trae entre 3 y 8 `general_generation_rules` comprobables; (7) cada campo COPIADO del documento distinto del `primary_field` admite `null`, salvo que sin él la modalidad no se sostenga.

<<<INVENTARIO>>>
{findings}
<<<FIN>>>

JSON:"""


def repair_exemplars_profile_prompt(profile: str, error_msg: str) -> str:
    return f"""\
El siguiente PERFIL DE EJEMPLARES parsea como JSON válido pero no cumple el formato exigido. Corrígelo.

# ERROR DE VALIDACIÓN
{error_msg}

# PERFIL A CORREGIR
{profile}

# FORMATO DE `schema` — causa habitual del error
{EXEMPLARS_PROFILE_SCHEMA_GRAMMAR}

# NOMBRES DE CAMPO
{EXEMPLARS_PROFILE_FIELD_NAMING}

# REGLAS
- Conserva el contenido original (`label`, `description`, `guidance`, reglas) tal cual; corrige SOLO lo que incumple el formato. Si renombras un campo, renómbralo también donde se le referencie.
- Clave de nivel superior exactamente una: `item_types`. Nada más a ese nivel. Si el perfil trae un `content_context`, DÉJALO donde está: es de una versión anterior y otro paso lo migra; no lo borres ni lo edites.
- `item_types` es un objeto NO VACÍO. Cada clave casa con `^[a-z][a-z0-9_]*$` y su valor declara al menos `primary_field` y `fields`, y opcionalmente `label`, `description` y `general_generation_rules`.
- El `primary_field` de cada modalidad debe ser una de las claves de SUS PROPIOS `fields`.
- `embed_fields`, si está, es una lista no vacía y sin repeticiones que EMPIEZA por el `primary_field` de esa modalidad y solo nombra claves de SUS PROPIOS `fields`.
- Devuelve UN ÚNICO objeto JSON. Nada antes, nada después. Sin backticks, sin comentarios, sin explicaciones.

JSON:"""
