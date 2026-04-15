
def get_input_validation_prompt(user_input: str):
    return  f"""Eres un validador de entrada para un sistema de tutoría pedagógica.

            Tu tarea es validar si la entrada del usuario es apropiada para una sesión de aprendizaje.

            CRITERIOS DE VALIDACIÓN:
            1. La entrada NO debe estar vacía o ser solo espacios.
            2. La entrada debe tener intención pedagógica (pregunta, explicación, código, ejercicio, etc.).
            3. La entrada debe estar en español o ser código universalmente entendible.
            4. La entrada NO debe ser abusive, grosera o inapropiada.

            ENTRADA DEL USUARIO:
            "{user_input}"

            Proporciona tu respuesta ÚNICAMENTE en formato JSON sin markdown, sin explicaciones adicionales:
            {{
                "valid": true|false,
                "reason": "breve explicación si no es válida",
                "cleaned_input": "la entrada limpiada si es válida, sino null"
            }}"""