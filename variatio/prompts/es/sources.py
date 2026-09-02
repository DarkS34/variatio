"""Reading the raw documents: a page transcribed, a seam decided, a fragment made items."""

from ..marks import CORRECT_ANSWER_MARK, EMPTY_IMAGE_MARK, EMPTY_PAGE_MARK, SEAM_SEPARATORS

__all__ = [
    "CORRECT_ANSWER_MARK",
    "EMPTY_IMAGE_MARK",
    "EMPTY_PAGE_MARK",
    "IMAGE_RULES",
    "SEAM_SEPARATORS",
    "format_content_prompt",
    "merge_pages_prompt",
    "transcribe_image_prompt",
    "transcribe_page_prompt",
]

# ONE block for the two prompts that meet an image: the page prompt, where the image is a
# figure on the page, and the image prompt, where it arrives alone out of a Word or
# PowerPoint file. An image is transcribed by what it CONTAINS and described only when
# nothing can be copied — a description of a formula cannot be solved from, and a
# description of a screenshot destroys the «write a program that prints this» exercise
# whose expected output was the screenshot.
IMAGE_RULES = """\
# IMÁGENES Y FIGURAS
Una imagen se transcribe por lo que CONTIENE, y solo se describe cuando no hay nada que copiar:
- Una fórmula o expresión matemática compuesta como imagen se transcribe en LaTeX, símbolo a símbolo — `$…$` en línea, `$$…$$` aparte.
- Una captura de código, de una terminal o de la salida de un programa se transcribe como bloque ``` con sus saltos de línea y su sangría exactos. Solo cuenta el contenido: se omite todo lo que sea de la aplicación y no del documento (menús, barras de herramientas, regla, pestañas, números de línea del editor, bordes de ventana, barra de tareas).
- Una tabla se transcribe como tabla Markdown, celda a celda.
- Un texto (un enunciado escaneado, una nota, un rótulo) se transcribe como texto.
- Solo lo que no puede copiarse como texto —un diagrama, una gráfica, un esquema, una fotografía— se anota en su sitio como `[figura: qué muestra]`, en una frase. Di lo que se VE (los ejes y magnitudes de una gráfica, los componentes de un esquema, las etiquetas que lleve) sin leer valores que no se lean con claridad ni interpretar lo que significa. La anotación nunca sustituye al texto que acompaña a la figura, que se transcribe como todo lo demás.
- Dentro de una imagen rigen las mismas reglas de fidelidad: se copia carácter a carácter, no se resuelve, no se completa, no se corrige, y `[ilegible]` marca lo que no se lee."""


def transcribe_page_prompt(page_number: int, page_count: int) -> str:
    """Ask for one page image copied into Markdown, character by character.

    The whole route stands on «copy, do not interpret»: a later extractor reads the
    transcription believing it is the original document, so anything changed becomes false
    teaching material. The only mark the model may add is `CORRECT_ANSWER_MARK`, on a
    visually highlighted answer option; a page carrying nothing but logos and page numbers
    comes back as `EMPTY_PAGE_MARK`, which `pages.py` matches. The answer is bare Markdown.
    A figure on the page follows `IMAGE_RULES`, the same block the standalone image prompt
    carries, so an image is read the same way whichever route brought it.
    """
    return f"""\
Transcribe a Markdown la PÁGINA {page_number} de {page_count} de un documento de material docente. La tienes delante como imagen.

Tu trabajo es COPIAR lo que hay en la página, no interpretarlo. Un extractor posterior leerá tu transcripción creyendo que es el documento original, así que cualquier cosa que cambies se convierte en material docente falso.

# ORDEN DE LECTURA
Transcribe en el orden en que lo leería una persona. Cada enunciado debe quedar junto al código, la tabla, la imagen o las opciones que le pertenecen, en el sitio donde aparecen. Si la página tiene columnas, sigue la columna entera antes de pasar a la siguiente.

# FIDELIDAD — LO MÁS IMPORTANTE
- Copia CARÁCTER A CARÁCTER. `a -= 1` no es `a = a - 1`. `x = x - 1` no es `x = x + 1`. `range (0,8)` conserva su espacio. No normalices, no modernices, no arregles el estilo.
- NO resuelvas nada, NO completes lo que falte, NO corrijas errores del documento. Si el código tiene un fallo, el fallo es parte del ejercicio y se transcribe tal cual.
- Respeta la ortografía y los acentos del original.
- Si algo es ilegible, escribe `[ilegible]` en su lugar. Nunca adivines.

# CÓDIGO
El código va en bloques delimitados por ``` conservando EXACTAMENTE sus saltos de línea y su indentación. Es lo que peor sobrevive a una transcripción descuidada y lo que más daño hace: un fragmento de código con la indentación aplanada o un operador cambiado deja de ser el ejercicio que era.

# NOTACIÓN MATEMÁTICA
Las fórmulas y expresiones matemáticas se copian con su notación, símbolo a símbolo y unidad a unidad. Si el original las compone tipográficamente (fracciones, subíndices, integrales, vectores), transcríbelas en LaTeX — `$…$` en línea, `$$…$$` aparte — y usa esa misma convención en TODO el documento. Si el original las escribe en texto plano, déjalas en texto plano. No resuelvas, no simplifiques, no cambies la notación por otra equivalente.

{IMAGE_RULES}

# RESPUESTAS MARCADAS
Si una opción de respuesta está destacada visualmente respecto a las demás — color distinto, negrita, subrayado, recuadro, una marca al margen — añade ` {CORRECT_ANSWER_MARK}` al final de esa línea y nada más. Es la única marca que puedes añadir al texto. Si ninguna está destacada, no marques ninguna: no deduzcas cuál es la correcta.

# QUÉ OMITIR
Logotipos, escudos, cabeceras y pies institucionales, números de página y marcas de agua. Todo lo demás se transcribe, incluidas las tablas (en Markdown) y los enunciados administrativos que formen parte de un ejercicio.

# CONTINUIDAD
Transcribe solo lo que ves en ESTA página. Si un ejercicio empieza aquí y sigue en la siguiente, corta donde corta la página: no lo completes ni escribas notas sobre ello.

# SALIDA
Solo el Markdown de la página. Sin preámbulo, sin comentarios tuyos, sin ```markdown envolviendo el conjunto, sin decir «Aquí está la transcripción». Si la página no contiene nada más que elementos omitibles, responde exactamente `{EMPTY_PAGE_MARK}`.

Markdown:"""


def transcribe_image_prompt(image_number: int, image_count: int) -> str:
    """Ask for one image of a Word or PowerPoint document copied into Markdown.

    The image reaches the model alone — Docling keeps the text around it — and what comes
    back is spliced into the document exactly where the image was, so the answer has to be
    the content itself in the form the surrounding Markdown would give it: LaTeX for a
    formula, a fence for a screenshot of code, a table for a table, `[figura: …]` only for
    what cannot be copied. A logo, a crest or an ornament comes back as `EMPTY_IMAGE_MARK`,
    which `pages.py` matches and drops.
    """
    return f"""\
Transcribe a Markdown la IMAGEN {image_number} de {image_count} de un documento de material docente (un archivo de Word o de PowerPoint). La tienes delante; el texto que la rodea no lo ves.

Tu trabajo es COPIAR lo que hay en la imagen, no interpretarla. Lo que devuelvas se insertará en el documento en el lugar exacto que ocupaba la imagen, y un extractor posterior lo leerá creyendo que es el documento original, así que cualquier cosa que cambies se convierte en material docente falso.

{IMAGE_RULES}

# RESPUESTAS MARCADAS
Si la imagen contiene opciones de respuesta y una está destacada visualmente respecto a las demás — color distinto, negrita, subrayado, recuadro, una marca al margen — añade ` {CORRECT_ANSWER_MARK}` al final de esa línea y nada más. Es la única marca que puedes añadir. Si ninguna está destacada, no marques ninguna.

# QUÉ NO TRANSCRIBIR
Un logotipo, un escudo, un adorno, una línea decorativa, un icono o una fotografía sin contenido docente: responde exactamente `{EMPTY_IMAGE_MARK}` y nada más.

# SALIDA
Solo el Markdown que sustituye a la imagen. Sin preámbulo, sin comentarios tuyos, sin ```markdown envolviendo el conjunto, sin decir «Aquí está la transcripción». Si la imagen no tiene nada que transcribir, responde exactamente `{EMPTY_IMAGE_MARK}`.

Markdown:"""


def merge_pages_prompt(tail: str, head: str, page_number: int, page_count: int) -> str:
    """Ask how two consecutively transcribed pages join, and nothing else.

    The certain seams are decided deterministically before the call; only the ambiguous ones
    reach here. The answer is `continues`, a `separator` out of `SEAM_SEPARATORS`,
    `drop_head_lines` (0 when in doubt — dropping a line of content loses teaching material
    and leaving a repeated header does not) and a short `reason`. The model classifies and
    never rewrites: one word of its own in the document would be false teaching material.
    """
    return f"""\
Dos páginas consecutivas de un documento docente se transcribieron por separado. Decide CÓMO SE UNEN, y nada más.

No escribes texto: no completas, no corriges, no reescribes, no resumes, no traduces. Otro proceso ya copió carácter a carácter lo que había en cada página, y tu única salida es un separador y un número. Cualquier palabra tuya que acabara en el documento sería material docente falso.

# FINAL DE LA PÁGINA {page_number - 1} DE {page_count}
<<<COLA>>>
{tail}
<<<FIN DE LA COLA>>>

# PRINCIPIO DE LA PÁGINA {page_number} DE {page_count}
<<<CABEZA>>>
{head}
<<<FIN DE LA CABEZA>>>

# QUÉ DECIDIR
1. `continues`: true si lo que abre la segunda página continúa lo que la primera dejó a medias — una frase cortada, un bloque de código partido, una tabla que sigue, una lista que sigue, una palabra partida. false si la segunda página empieza algo nuevo.
2. `separator`: qué se pone entre las dos transcripciones.
   - `none`: nada. Solo cuando la primera corta una palabra o un identificador por la mitad.
   - `space`: un espacio. Una frase que sigue en la página siguiente.
   - `newline`: un salto de línea. Un bloque de código, una tabla o una lista que continúan: una línea en blanco rompería la estructura.
   - `paragraph`: una línea en blanco. El caso normal, cuando la segunda página empieza algo nuevo.
3. `drop_head_lines`: cuántas líneas del principio de la CABEZA hay que descartar por ser repetición mecánica de la maquetación y no contenido — una cabecera de página repetida, un pie, el número del mismo ejercicio que la cola ya llevaba escrito. 0 casi siempre. Ante la duda, 0: descartar una línea de contenido pierde material docente y dejar una cabecera repetida no.
4. `reason`: una frase corta en español que diga por qué.

# SALIDA
Un único objeto JSON: {{"continues": true|false, "separator": "none"|"space"|"newline"|"paragraph", "drop_head_lines": 0, "reason": "..."}}
Nada antes, nada después, sin ```json.

JSON:"""


def format_content_prompt(
    content: str,
    types_block: str,
    context_block: str = "",
    type_keys: list[str] | None = None,
) -> str:
    """Ask for the learning items of one markdown fragment, each under one modality's schema.

    Classify first, extract afterwards: every object carries `item_type` — one of
    `type_keys` — plus that modality's own fields and no other's. Values are copied
    verbatim, a field the source does not carry goes to `null` rather than being invented,
    and `CORRECT_ANSWER_MARK` is read for the correct option and then stripped out of the
    value. A fragment that sets no task comes back as `[]`; the answer is a JSON array.
    """
    context_section = (
        f"\n# CONTEXTO DOCENTE DEL DOCUMENTO\n{context_block}\n" if context_block.strip() else ""
    )

    keys = ", ".join(f"`{k}`" for k in (type_keys or []))

    return f"""\
Extrae los ITEMS DE APRENDIZAJE de un fragmento markdown pre-segmentado de material docente.

Un item de aprendizaje es toda unidad que el material PLANTEA AL ALUMNO COMO TAREA: un ejercicio, un problema, una actividad, una pregunta, un supuesto práctico. Que venga acompañado de su solución no lo descalifica — sigue siendo un item, con su solución incluida.

NO son items de aprendizaje y no deben extraerse: la exposición teórica del temario, las explicaciones y definiciones, los ejemplos que el texto usa para ILUSTRAR una explicación sin pedir nada al alumno, los índices, los objetivos de la unidad, las rúbricas, la bibliografía y los avisos administrativos. Si el fragmento no plantea ninguna tarea, devuelve `[]`.

El input contiene uno o varios items. Si hay varios, vienen separados por líneas `---`. Cada bloque entre separadores (o el input completo si es un único bloque) representa exactamente UN item. Dentro de un bloque, todo lo que encuentres — sub-preguntas, apartados (a/b/c, i/ii/iii), bloques de código embebidos, instrucciones de seguimiento, párrafos explicativos, tablas, ejemplos — pertenece a ese único item: los apartados son una progresión de la misma tarea, no tareas distintas.

# PRIMERO CLASIFICA, DESPUÉS EXTRAE
La asignatura plantea sus tareas en varias MODALIDADES, y cada una tiene su propio esquema de campos. Para CADA item: decide primero a qué modalidad pertenece, y extrae después usando el esquema DE ESA modalidad y ninguno otro.

Cada objeto que devuelvas lleva una clave `item_type` con la clave de su modalidad ({keys}), MÁS los campos declarados por esa modalidad. Sin `item_type` el item se descarta.

Elige la modalidad por lo que el item PIDE AL ALUMNO, no por su tema ni por su dificultad. Si un item encaja en dos, quédate con aquella cuyos campos puedas rellenar del todo con lo que hay en el texto. Si no encaja en ninguna, NO lo extraigas: es preferible perder un item que inventarle una anatomía.

# MODALIDADES Y SUS ESQUEMAS
{types_block}

# REGLAS DE EXTRACCIÓN
- Copia los valores literalmente del texto fuente. No reescribas, no traduzcas, no resumas, no inventes contenido. Lo que se extrae es material docente real: alterarlo destruye justamente lo que lo hace útil como ejemplo.
- Si un campo admite null y el contenido no aparece en la fuente, ponlo a null. Nunca fabriques contenido para rellenar: un enunciado sin solución en el material es un item legítimo, uno con la solución inventada es material docente falso.
- No mezcles campos de dos modalidades en un mismo objeto: los únicos campos válidos son los de la modalidad que has declarado en `item_type`.
- El material puede venir de una transcripción que marca con `✔` la opción correcta de una pregunta cerrada. Esa marca NO es parte del texto: úsala para saber cuál es la respuesta correcta y quítala del valor que extraigas.
- Elimina marcadores de enumeración inicial (`1.`, `2)`, `Ejercicio 3:`, `Exercise 4.`, `Problema 5 -`, `Apartado 6:`, `Sección 7 –`, etc.) en los campos de texto. Los valores deben empezar con el primer carácter real del contenido, no con un número o etiqueta.
- Para strings multilínea (código, prosa con párrafos): escapa saltos como `\\n` y comillas internas como `\\"`.
- Respeta los constraints del schema (`minLength`, `maxLength`, `pattern`, etc.).

# REGLAS DE SALIDA
- Un único JSON array. Nada antes, nada después.
- Cada objeto lleva `item_type` más los campos de esa modalidad.
- Sin ```json, sin backticks, sin comentarios.
- Si el fragmento no plantea ninguna tarea al alumno, devuelve `[]`.
{context_section}
<<<CONTENT>>>
{content}
<<<END>>>

JSON:"""
