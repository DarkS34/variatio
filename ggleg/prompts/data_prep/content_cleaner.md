Limpia texto educativo de programación (markdown convertido desde .docx/.pdf). Devuelve el texto IGUAL: no resuelvas, no reescribas, no traduzcas.

# CONSERVA exacto
- Cabeceras de sección: "# Ejercicios resueltos", "# Nivel básico", "## Exercises".
- Enunciados (es / en / fr).
- Bloques de código, código inline y docstrings.
- Soluciones completas con sus comentarios y tests.
- Etiquetas de solución: "SOLUCION PROPUESTA", "Solución:", "Answer:".

# ELIMINA
- Números de página sueltos ("3", "- 12 -").
- Pies de página, copyright, URLs institucionales.
- Índices y tablas de contenido.
- Metadatos autor / fecha / versión.
- Más de 2 líneas vacías seguidas (deja máximo 2).

# CORRIGE artefactos de conversión
- `cuenta\_aes` → `cuenta_aes`
- `*""" ... """*` → `""" ... """`
- `*return*` → `return`
- `n \* 2` → `n * 2` ;  `a \| b` → `a | b`

# PROHIBIDO
- Resolver ejercicios sin solución.
- Reescribir enunciados.
- Añadir introducción, explicación o cierre.
- Cambiar el idioma.

Si el texto ya está limpio, devuélvelo tal cual.

<<<CONTENT>>>
{raw_content}
<<<END>>>

Texto limpio:
