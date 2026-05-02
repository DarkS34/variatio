from pydantic import BaseModel, Field

from system.concept_tagger import ConceptTagger
from system.embedder import Embedder
from system.content_bank_handler import ContentBankHandler
from system.knowledge_graph import KnowledgeGraph
from system.utils import load_models

KG_PATH = "data/knowledge_graph_raw.json"
RAW_BANK_PATH = "data/formatted_exercises.json"


class ExtractedExercise(BaseModel):
    statement: str = Field(
        min_length=10,
        description=(
            "Enunciado del ejercicio en prosa, sin el marcador de enumeración inicial "
            "(`1.`, `Ejercicio 3:`, etc.). Conserva sub-preguntas, apartados (a/b/c, "
            "i/ii/iii) e instrucciones encadenadas. "
            "Tratamiento del código embebido: si dentro del enunciado aparece un "
            "BLOQUE de código (indentado con 4+ espacios, dentro de triple backtick, "
            "o como párrafo aislado entre líneas en blanco), NO lo incluyas literalmente "
            "aquí — sustitúyelo en su posición exacta por un placeholder `§code_N§` "
            "(N empezando en 0 e incrementando por cada bloque) y mueve el contenido "
            "a starter_code bajo la clave `code_N`. El código INLINE corto que aparezca "
            "dentro de una frase (p.ej. `print(x)` o nombres de variable mencionados "
            "como `cuenta_aes`) se queda dentro del statement tal cual, sin placeholder. "
            "Copia literal del resto del texto, sin reescribir ni traducir."
        ),
    )
    starter_code: dict[str, str] = Field(
        ...,
        description=(
            "Diccionario con los bloques de código Python referenciados desde el "
            "statement mediante placeholders `§code_N§`. Las claves son `code_0`, "
            "`code_1`, ... siguiendo el orden de aparición en el enunciado. Los valores "
            "son el código en bruto, sin envolver en triple backtick y sin la "
            "indentación markdown de bloque (los 4 espacios iniciales o el tab los "
            "elimina). Preserva saltos de línea internos con `\\n`. Incluye solo "
            "bloques visualmente separados del texto; el código inline mencionado "
            "dentro de una frase NO va aquí. Si el ejercicio no contiene ningún bloque "
            "de código separado, devuelve un diccionario vacío {}."
        ),
    )
    solution: str | None = Field(
        default=None,
        description=(
            "Código Python completo de la solución, si aparece en el texto fuente "
            "(habitualmente bajo etiquetas tipo \"SOLUCION PROPUESTA\", \"Solución:\", "
            "\"Answer:\"). Solo el código, sin envolver en triple backtick. Si hay "
            "varias soluciones alternativas, elige la más completa. Si no hay solución "
            "en el texto fuente, null."
        ),
    )


if __name__ == "__main__":
    # Load model into memory
    models = load_models()

    # Phase 0: Initialize esentials
    # knowledge_graph = KnowledgeGraph(KG_PATH)

    handler = ContentBankHandler(
        cleaning_llm=models.get("content_cleaning"),
        formating_llm=models.get("content_formatting"),
        item_model=ExtractedExercise,
        item_pattern=(r"^(?:\d+[.)]\s+|(?:Ejercicio|Exercise|Problem|Problema)\s*\d+[:.)\s])"),
        id_from="statement",
    )

    handler.format_file("./essential_data/content_bank/raw_content/workbooks/WB1.docx", "o.json")

    # embedder = Embedder(knowledge_graph, embedding_model=models.get("embedding"))
    # tagger = ConceptTagger(knowledge_graph=knowledge_graph, embedder=embedder, llm=models.get_generative_LLM("tag_concepts"))

    # # Phase 0.1: Format exercises or import existing formatted exercises
    # raw_bank = content_bank_handler.format_dir(input_dir="./workbooks", output_file_path=RAW_BANK_PATH)

    # # Phase 0.2: Tag all existing exercises
    # annotated_bank = tagger.tag_all(raw_bank)

    # # Phase 0.3: Enrich embeddings with tagged exercises
    # embedder.enrich_with_exercises(annotated_bank)
