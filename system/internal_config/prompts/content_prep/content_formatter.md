Extrae elementos estructurados de un fragmento markdown pre-segmentado.

El input contiene uno o varios elementos. Si hay varios, vienen separados por líneas `---`. Cada bloque entre separadores (o el input completo si es un único bloque) representa exactamente UN elemento. Dentro de un bloque, todo lo que encuentres — sub-preguntas, apartados (a/b/c, i/ii/iii), bloques de código embebidos, instrucciones de seguimiento, párrafos explicativos, tablas, ejemplos — pertenece a ese único elemento.

Produce un JSON array con un objeto por elemento, conforme al schema de abajo.

# SCHEMA DE SALIDA
Cada objeto del array debe cumplir este JSON Schema. El campo `description` de cada propiedad es una instrucción concreta sobre QUÉ extraer y CÓMO formatearlo — léelo y síguelo literalmente para cada elemento.

{schema}

# REGLAS DE EXTRACCIÓN
- Copia los valores literalmente del texto fuente. No reescribas, no traduzcas, no resumas, no inventes contenido.
- Si un campo admite null y el contenido no aparece en la fuente, ponlo a null. Nunca fabriques contenido para rellenar.
- Elimina marcadores de enumeración inicial (`1.`, `2)`, `Ejercicio 3:`, `Exercise 4.`, `Problema 5 -`, `Apartado 6:`, `Sección 7 –`, etc.) en los campos de texto. Los valores deben empezar con el primer carácter real del contenido, no con un número o etiqueta.
- Para strings multilínea (código, prosa con párrafos): escapa saltos como `\n` y comillas internas como `\"`.
- Respeta los constraints del schema (`minLength`, `maxLength`, `pattern`, etc.).

# REGLAS DE SALIDA
- Un único JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios.
- Si no hay elementos extraíbles del input, devuelve `[]`.

<<<CONTENT>>>
{content}
<<<END>>>

JSON: