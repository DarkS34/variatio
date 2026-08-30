"""The two prompt sets, and the one property that keeps them from becoming two systems.

A prompt is not a translation of a string: it is a measured artefact, and the Spanish ones
carry measurements the English ones do not have yet. What CAN be checked mechanically is
that the two sets are interchangeable — same names, same signatures, same JSON keys — so a
caller resolving one or the other cannot break, and so a function added to one is not
quietly missing from the other.

The JSON keys are the reason the second half of this file exists. They are the grammar
`schemas.py` pins and what the parsers read: a translated key yields a well-formed answer
that parses to nothing, which is the failure mode the closed-decisions register describes.
"""

import inspect

import pytest

from variatio.core import languages
from variatio import prompts

SETS = {code: prompts.of(code) for code in languages.LANGUAGES}


def test_there_is_one_set_per_declared_language():
    assert set(SETS) == set(languages.LANGUAGES)


def test_every_set_exposes_the_same_names():
    exported = {code: sorted(module.__all__) for code, module in SETS.items()}
    reference = exported[languages.DEFAULT]
    for code, names in exported.items():
        assert names == reference, f"«{code}» exposes a different set of names"


def test_every_exported_name_actually_exists():
    for code, module in SETS.items():
        for name in module.__all__:
            assert hasattr(module, name), f"«{code}» declares «{name}» and does not have it"


def _functions(module) -> dict:
    return {
        name: getattr(module, name)
        for name in module.__all__
        if callable(getattr(module, name))
    }


def test_the_same_call_works_against_either_set():
    # The whole point of the resolver: a caller holds one of these and does not know which.
    reference = _functions(SETS[languages.DEFAULT])
    for code, module in SETS.items():
        theirs = _functions(module)
        assert set(theirs) == set(reference), f"«{code}» has different functions"
        for name, function in theirs.items():
            assert inspect.signature(function) == inspect.signature(reference[name]), (
                f"«{name}» has a different signature in «{code}»"
            )


# THE PROTOCOL TOKENS ----------------------------------------------------------------------


def test_the_marks_are_shared_and_not_translated():
    # They are protocol tokens, not prose: `EMPTY_PAGE_MARK` is written into the cached
    # markdown and read back by the transcriber, so translating it would strand every page
    # already transcribed and give the reader two strings to recognise instead of one.
    for module in SETS.values():
        assert module.CORRECT_ANSWER_MARK is prompts.CORRECT_ANSWER_MARK
        assert module.EMPTY_PAGE_MARK is prompts.EMPTY_PAGE_MARK
        assert module.SEAM_SEPARATORS is prompts.SEAM_SEPARATORS


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_the_seam_separator_names_stay_english_in_both(code):
    # They are the values a grammar pins and `pages.py` matches against.
    assert prompts.of(code).SEAM_SEPARATORS == ("none", "space", "newline", "paragraph")


# THE JSON KEYS ----------------------------------------------------------------------------

# What the parsers read. Each entry is (function name, the keys its output shape must name).
DRAWN_KEYS = {
    "extract_typed_graph_prompt": ("concepts", "relations"),
    "glean_typed_graph_prompt": ("concepts", "relations"),
    "link_domain_relations_prompt": ("relations",),
    "link_cross_domain_relations_prompt": ("relations",),
    "merge_candidate_groups_prompt": ("merges", "canonical", "aliases"),
    "filter_graph_nodes_prompt": ("drop",),
    "curate_graph_domains_prompt": ("domains",),
    "assign_leftover_concepts_prompt": ("domains",),
    "review_taggable_concepts_prompt": ("non_taggable",),
    "segment_syllabus_prompt": ("units", "opens_at"),
    "tag_concepts_prompt": ("concepts", "primary_concept"),
    "scan_item_types_prompt": ("types", "key", "label", "fields", "excerpt"),
    "consolidate_exemplars_profile_prompt": ("item_types", "primary_field", "embed_fields"),
    "synthesize_content_context_prompt": (
        "narrative",
        "subject",
        "educational_level",
        "language_of_instruction",
    ),
    "merge_pages_prompt": ("continues", "separator", "drop_head_lines", "reason"),
    "concept_description_prompt": ("description",),
    "describe_domain_concepts_prompt": ("descriptions",),
    "classify_instructions_prompt": ("requests", "slot", "owner", "term"),
}


def _render(function, schema=None):
    kwargs = {}
    for name, parameter in inspect.signature(function).parameters.items():
        if parameter.default is not inspect.Parameter.empty:
            continue
        if name == "schema":
            kwargs[name] = schema
        elif parameter.annotation is int or name.endswith(("_chars", "_number", "_count")):
            kwargs[name] = 1
        elif name in ("concepts", "targets", "already_generated", "catalog", "owners"):
            kwargs[name] = []
        elif name in ("definitions", "siblings"):
            kwargs[name] = {}
        elif name == "relations":
            # A list of triples in the graph prompts and a verbose→neighbours map in the
            # description one. Both sets take the same shape, which is the property under
            # test; only the stub has to know which.
            kwargs[name] = {} if function.__name__ == "concept_description_prompt" else []
        else:
            kwargs[name] = "x"
    return function(**kwargs)


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_the_json_keys_are_never_translated(code):
    from variatio.instance.relations import RELATION_SCHEMAS

    module = prompts.of(code)
    schema = RELATION_SCHEMAS[code]
    for name, keys in DRAWN_KEYS.items():
        rendered = _render(getattr(module, name), schema=schema)
        for key in keys:
            assert key in rendered, f"«{code}»: «{name}» does not name the key «{key}»"


# THE CHAIN A WORKSPACE STARTS -------------------------------------------------------------


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_a_workspace_resolves_a_matching_prompt_set_and_relation_schema(tmp_path, code):
    # The property the whole design rests on: the catalogue the KG prompts interpolate is
    # prose written in the schema's language and naming its own slots, so a workspace that
    # resolved one from its file and the other from a global would render an English
    # definition under a Spanish heading — which is exactly what kept `RELATION_SCHEMA_EN`
    # unusable before this.
    from variatio.core.workspace import Workspace
    from variatio.instance import locale

    ws = Workspace(root=tmp_path / code, slug=code)
    locale.set_prompt_language(ws, code)

    schema = locale.relation_schema(ws)
    module = prompts.of(locale.prompt_language(ws))

    assert schema.language == code
    rendered = module.link_domain_relations_prompt("D", "- A\n- B", schema)
    assert schema.source_slot in rendered
    assert schema.target_slot in rendered
    # And never the other language's slot names, which is what a mismatch would look like.
    other = next(c for c in languages.LANGUAGES if c != code)
    from variatio.instance.relations import CATALOG_WORDS

    assert CATALOG_WORDS[other]["source"] not in rendered


def test_the_relation_keys_differ_by_language_and_that_is_why_it_is_chosen_once(tmp_path):
    # `verbose` is what the loader indexes a graph by and it is written into
    # `knowledge_graph.json`, so the language is baked into the artifact at build time.
    # This test exists to make that consequence visible rather than surprising.
    from variatio.instance.relations import RELATION_SCHEMA_EN, RELATION_SCHEMA_ES

    assert RELATION_SCHEMA_ES.prerequisite_verbose != RELATION_SCHEMA_EN.prerequisite_verbose
    assert set(RELATION_SCHEMA_ES.keys) != set(RELATION_SCHEMA_EN.keys)
    # Same shape, different words: the two schemas declare the same three relations.
    assert len(RELATION_SCHEMA_ES) == len(RELATION_SCHEMA_EN) == 3


# CLAUDE.md states it as a property of the whole system: «every prompt receives the
# context's `prompt_block()` and is told to take register, level and language from it. That
# is how they stay subject-agnostic while sounding native to the subject.» Two did not, and
# they were the two whose output came back in the wrong language — measured on a workspace
# whose material and `locale.json` are both English, where the graph, the concept
# descriptions and the bank all came out English and only the profile's `description` and
# `guidance` came out Spanish.
CONTEXT_AWARE = [
    "scan_item_types_prompt",
    "consolidate_exemplars_profile_prompt",
    "concept_description_prompt",
    "describe_domain_concepts_prompt",
]


@pytest.mark.parametrize("code", languages.LANGUAGES)
@pytest.mark.parametrize("name", CONTEXT_AWARE)
def test_the_subject_facing_prompts_take_the_context_block(code, name):
    function = getattr(prompts.of(code), name)
    assert "context_block" in inspect.signature(function).parameters, (
        f"«{name}» does not take the subject's context in «{code}»"
    )


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_the_profile_prompts_render_the_context_they_are_given(code):
    module = prompts.of(code)
    block = "MATERIA: Física · IDIOMA DE INSTRUCCIÓN: English"
    scan = module.scan_item_types_prompt("fragmento", context_block=block)
    consolidate = module.consolidate_exemplars_profile_prompt("hallazgos", 4, context_block=block)
    assert block in scan and block in consolidate


@pytest.mark.parametrize("code", languages.LANGUAGES)
def test_no_context_renders_no_empty_heading(code):
    """A first build has no context yet, and an empty section is worse than none."""
    module = prompts.of(code)
    for rendered in (
        module.scan_item_types_prompt("fragmento"),
        module.consolidate_exemplars_profile_prompt("hallazgos", 4),
    ):
        assert "CONTEXTO DOCENTE" not in rendered
        assert "TEACHING CONTEXT" not in rendered
