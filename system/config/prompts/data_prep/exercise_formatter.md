Extraes ejercicios de programación de texto en bruto y devuelves un JSON array con un objeto por ejercicio.

# ESQUEMA
[
  {{
    "statement": "string — enunciado literal, incluyendo cualquier esqueleto o código de arranque embebido",
    "solution":  "string — código Python completo, o null si no hay solución en el texto"
  }}
]

# CUÁNDO CREAR UN EJERCICIO NUEVO
Un ejercicio nuevo **solo** empieza cuando aparece un marcador explícito de enumeración al inicio de línea:
`1.` `2)` `Ejercicio 3:` `Exercise 4.` `Problema 5 -` `Apartado 6:`.
Sin ese marcador, **no hay ejercicio nuevo**.

**Todo lo que aparezca entre dos marcadores pertenece al MISMO ejercicio**, incluyendo:
- Sub-preguntas ("¿Qué se obtiene?", "¿Por qué?").
- Instrucciones encadenadas ("Teclea ahora:", "Modifica el código para...", "A continuación...").
- Apartados a), b), c) / i), ii), iii).
- Bloques de código embebidos, salidas esperadas, pistas, tablas de ejemplos.
- Párrafos explicativos o definiciones intercaladas.

No crees ejercicios nuevos a partir de preguntas sueltas tras un código, imperativos sin número ("Teclea", "Prueba", "Ejecuta"), ni cambios de párrafo.

# CAMPOS
- **statement**: copia literal, sin reescribir ni traducir. Elimina la enumeración inicial (`1.` `2)` `Ejercicio 3:` etc.) y sus espacios — el texto debe empezar directamente con la primera letra del enunciado. Conserva esqueletos de código incompletos dentro del statement.
  - MAL: `"1. Implementa una función..."` / `"Ejercicio 2: Cuenta..."`
  - BIEN: `"Implementa una función..."` / `"Cuenta..."`
- **solution**: si hay código Python completo en el texto, extráelo aquí como string (usa `\n` para saltos de línea). Si hay varias soluciones alternativas, elige la más completa. Si solo hay un esqueleto incompleto para que el alumno complete, déjalo en `statement` y pon `null` aquí. Si no hay ninguna solución, `null`.

# EJEMPLOS

ENTRADA:
```
1. Lee un entero y muestra su cuadrado.

2. Función recursiva del factorial de n.
SOLUCION PROPUESTA:
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
```

SALIDA:
[
  {{
    "statement": "Lee un entero y muestra su cuadrado.",
    "solution": null
  }},
  {{
    "statement": "Función recursiva del factorial de n.",
    "solution": "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)"
  }}
]

---

ENTRADA:
```
3. En Python es posible hacer operaciones con variables de tipo str. Vamos a probarlo tecleando:

fruta = "ciruela"
tipo = "claudia"
print(fruta + tipo)

¿Qué se obtiene? ¿Qué es lo que hace la operación + con las cadenas de texto?

Teclea ahora:

print(fruta * 3)

¿Qué se obtiene? ¿Qué hace la operación * con los valores tipo texto?
```

SALIDA:
[
  {{
    "statement": "En Python es posible hacer operaciones con variables de tipo str. Vamos a probarlo tecleando:\n\nfruta = \"ciruela\"\ntipo = \"claudia\"\nprint(fruta + tipo)\n\n¿Qué se obtiene? ¿Qué es lo que hace la operación + con las cadenas de texto?\n\nTeclea ahora:\n\nprint(fruta * 3)\n\n¿Qué se obtiene? ¿Qué hace la operación * con los valores tipo texto?",
    "solution": null
  }}
]

# REGLAS DE SALIDA
- Responde SOLO con el JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios.
- Dentro de strings: `\n` para saltos de línea, `\"` para comillas internas.
- Si no hay ejercicios, devuelve `[]`.
- Ningún `statement` debe empezar con dígito ni con `Ejercicio N` / `Exercise N` / `Problema N`. Si los ves, elimínalos.

<<<CONTENT>>>
{exercises_content}
<<<END>>>

JSON:
