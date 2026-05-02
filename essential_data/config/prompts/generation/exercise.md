Genera UN ejercicio nuevo de programación Python sobre el concepto indicado, en español.

# CONCEPTO PRINCIPAL
{concept}  (dominio: {domain})

# EJEMPLOS DEL BANCO
Estos ejercicios del banco trabajan el mismo concepto. Imítalos en estilo, longitud y nivel de detalle, pero NO los copies — el enunciado generado debe ser original.

{few_shots}

# CAMPOS A PRODUCIR
{fields}

# ESQUEMA DE SALIDA
{{
  "statement": "...",
  "solution": "...",      // sólo si está en CAMPOS
  "concepts": ["..."],     // sólo si está en CAMPOS — conceptos relevantes del temario
  "hints": ["...", "..."]  // sólo si está en CAMPOS — 2 o 3 pistas progresivas
}}

# REGLAS
- Incluye en el JSON SOLO los campos listados en CAMPOS A PRODUCIR. `statement` siempre es obligatorio.
- El enunciado debe centrarse en el CONCEPTO PRINCIPAL, sin asumir conocimientos fuera del dominio.
- Si pides `solution`, escribe código Python válido, autocontenido y comentado mínimamente.
- Si pides `hints`, ordena de la más general (orientación conceptual) a la más concreta (cercana a la solución), sin revelar la solución entera.
- Responde SOLO con el JSON. Sin texto antes ni después, sin backticks, sin comentarios.

JSON:
