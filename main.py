# from loguru import logger

from builders.content_bank_builder import ContentBankBuilder
from system import config
from system.concept_tagger import ConceptTagger
from system.content_bank import ContentBank
from system.content_generator import ContentGenerator
from system.content_profile import ContentProfile
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph

if __name__ == "__main__":
    content_profile = ContentProfile(config.CONTENT_PROFILE_PATH)
    graph = KnowledgeGraph(config.KG_PATH)

    curriculum = [
        "Variable",
        "Literal",
        "Tipo de dato básico",
        "Operador",
        "Expresión",
        "Asignación",
        "Entrada / Salida",
        "Comentario",
        "Indentación",
        "Expresión booleana",
        "Expresión de comparación",
        "Sentencia condicional",
        "Bucle",
        "Bucle for",
        "Bucle while",
        "Iterable",
        "Lista",
        "Cadena",
        "Indexación",
        "Función",
        "Llamada a función",
        "Parámetro",
        "Argumento",
        "Valor de retorno",
    ] if content_profile.enforce_curriculum else None

    content_bank = ContentBank(config.CONTENT_BANK_PATH)
    bank = content_bank.bank
    if bank is None:
        bank = ContentBankBuilder(content_profile).build(
            config.RAW_CONTENT_BANK_DIR, config.CONTENT_BANK_PATH
        )

    embedder = Embedder(
        graph,
        config.EMBEDDING_LLM,
        primary_field=content_profile.primary_field,
        context=content_profile.content_context,
    )

    tagger = ConceptTagger(
        embedder, config.CONCEPT_TAGGER_LLM, primary_field=content_profile.primary_field
    )

    # annotated_bank = tagger.tag_all(bank, config.CONTENT_BANK_PATH)
    # embedder.enrich_index_with_content(annotated_bank)

    generator = ContentGenerator(
        knowledge_graph=graph,
        content_bank=bank,
        embedder=embedder,
        content_profile=content_profile,
        generator_model=config.CONTENT_GENERATION_LLM,
    )

    results = generator.generate(
        concepts=["Bucle", "Lista"],
        fixed={"difficulty": 4},
        curriculum=curriculum,
    )

    print(results)
