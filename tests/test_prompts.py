import inspect

from system import prompts

CONTEXT = {
    "materia": "Programación I",
    "lenguaje_programacion": "Python",
    "nivel_educativo": "Universitario",
}

SCHEMA = '{\n  "type": "object",\n  "properties": {\n    "statement": {"type": "string"}\n  }\n}'

PUBLIC_PROMPTS = {
    "clean_graph_nodes_prompt",
    "concept_description_prompt",
    "curate_graph_domains_prompt",
    "extract_typed_graph_prompt",
    "format_content_prompt",
    "generate_content_prompt",
    "infer_content_profile_prompt",
    "json_repair_prompt",
    "link_global_relations_prompt",
    "tag_concepts_prompt",
    "type_graph_relations_prompt",
}


def test_public_prompt_surface_is_stable():
    exported = {
        name
        for name, obj in vars(prompts).items()
        if inspect.isfunction(obj) and not name.startswith("_")
    }

    assert exported == PUBLIC_PROMPTS


def test_every_prompt_returns_a_non_empty_string():
    for name in PUBLIC_PROMPTS:
        signature = inspect.signature(getattr(prompts, name))
        required = [
            p.name for p in signature.parameters.values() if p.default is inspect.Parameter.empty
        ]
        assert required, f"{name} takes no required argument"


def test_json_repair_prompt_array(assert_snapshot):
    assert_snapshot(
        "json_repair_array",
        prompts.json_repair_prompt(broken_output='{"a": 1,}', error_msg="trailing comma"),
    )


def test_json_repair_prompt_object_shape(assert_snapshot):
    assert_snapshot(
        "json_repair_object",
        prompts.json_repair_prompt(
            broken_output='{"a": 1,}', error_msg="trailing comma", shape="objeto"
        ),
    )


def test_format_content_prompt_with_guidance(assert_snapshot):
    assert_snapshot(
        "format_content_with_guidance",
        prompts.format_content_prompt(
            content="1. Escribe una función.",
            schema=SCHEMA,
            context=CONTEXT,
            field_guidance_block="- `statement`: copia el enunciado literal.",
        ),
    )


def test_format_content_prompt_without_guidance(assert_snapshot):
    assert_snapshot(
        "format_content_without_guidance",
        prompts.format_content_prompt(content="1. Escribe una función.", schema=SCHEMA),
    )


def test_concept_description_prompt_full(assert_snapshot):
    assert_snapshot(
        "concept_description_full",
        prompts.concept_description_prompt(
            concept="Bucles",
            domain="Control de flujo",
            relations={"es un tipo de este concepto": ["Bucle for", "Bucle while"]},
            siblings=["Condicionales"],
            context=CONTEXT,
        ),
    )


def test_concept_description_prompt_bare(assert_snapshot):
    assert_snapshot(
        "concept_description_bare",
        prompts.concept_description_prompt(
            concept="Bucles",
            domain="Control de flujo",
            relations={},
            siblings=[],
            context={},
        ),
    )


def test_tag_concepts_prompt_with_context(assert_snapshot):
    assert_snapshot(
        "tag_concepts_with_context",
        prompts.tag_concepts_prompt(
            statement="Escribe una función que sume dos números.",
            candidates="1. Funciones (score: 0.812)\n2. Parámetros (score: 0.640)",
            context=CONTEXT,
        ),
    )


def test_tag_concepts_prompt_without_context(assert_snapshot):
    assert_snapshot(
        "tag_concepts_without_context",
        prompts.tag_concepts_prompt(
            statement="Escribe una función que sume dos números.",
            candidates="1. Funciones (score: 0.812)\n2. Parámetros (score: 0.640)",
        ),
    )


def test_tag_concepts_prompt_is_domain_agnostic():
    rendered = prompts.tag_concepts_prompt(
        statement="Redacta un enunciado de examen sobre derivadas.",
        candidates="1. Derivadas (score: 0.900)",
        context={"materia": "Cálculo", "nivel_educativo": "Bachillerato"},
    )

    assert "Python" not in rendered
    assert "programación" not in rendered
    assert "materia: Cálculo" in rendered


def test_generate_content_prompt_full(assert_snapshot):
    assert_snapshot(
        "generate_content_full",
        prompts.generate_content_prompt(
            context=CONTEXT,
            target_concepts_block="- **Bucles**: itera sobre secuencias.",
            curriculum_block="- Bucles\n- Condicionales",
            rules_block="- Usa nombres significativos.",
            few_shot_block="---\nITEM:\nEscribe un bucle.",
            already_generated=["Recorre una lista de precios."],
            instance_template='{\n  "statement": <valor concreto para statement>\n}',
            field_guidance_block="- `statement`: redacta el enunciado.",
            fixed_values_block="- `difficulty_level`: debe ser exactamente \"intermedio\".",
            schema=SCHEMA,
        ),
    )


def test_generate_content_prompt_minimal(assert_snapshot):
    assert_snapshot(
        "generate_content_minimal",
        prompts.generate_content_prompt(
            context=CONTEXT,
            target_concepts_block="- **Bucles**",
            curriculum_block="",
            rules_block="- Usa nombres significativos.",
            few_shot_block="",
            already_generated=[],
            instance_template='{\n  "statement": <valor concreto para statement>\n}',
            field_guidance_block="(ningún campo con guía específica adicional)",
            fixed_values_block="(no hay valores fijos)",
            schema=SCHEMA,
        ),
    )


def test_clean_graph_nodes_prompt(assert_snapshot):
    assert_snapshot(
        "clean_graph_nodes",
        prompts.clean_graph_nodes_prompt(
            nodes_block="- Bucles  [incluye Bucle for]\n- bucles"
        ),
    )


def test_curate_graph_domains_prompt(assert_snapshot):
    assert_snapshot(
        "curate_graph_domains",
        prompts.curate_graph_domains_prompt(
            nodes_block="- Bucles  [incluye Bucle for]\n- Variables"
        ),
    )


def test_type_graph_relations_prompt(assert_snapshot):
    assert_snapshot(
        "type_graph_relations",
        prompts.type_graph_relations_prompt(
            edges_block='- "incluye"  (p.ej. Bucles → Bucle for)'
        ),
    )


def test_extract_typed_graph_prompt(assert_snapshot):
    assert_snapshot(
        "extract_typed_graph",
        prompts.extract_typed_graph_prompt(
            source_text="Una lista es una colección ordenada y mutable de elementos."
        ),
    )


def test_extract_typed_graph_prompt_is_domain_agnostic():
    rendered = prompts.extract_typed_graph_prompt(source_text="El soneto es un tipo de poema.")

    assert "Python" not in rendered
    assert "Mamífero" in rendered


def test_link_global_relations_prompt(assert_snapshot):
    assert_snapshot(
        "link_global_relations",
        prompts.link_global_relations_prompt(concepts_block="- Listas\n- Tuplas\n- Diccionarios"),
    )


def test_infer_content_profile_prompt(assert_snapshot):
    assert_snapshot(
        "infer_content_profile",
        prompts.infer_content_profile_prompt(
            sample="===== DOCUMENTO: WB1 =====\n\n1. Escribe una función."
        ),
    )
