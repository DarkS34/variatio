"""The library's public API: one function per thing that can be asked of a workspace.

Everything in here takes a `Workspace` and nothing else takes one. That is the whole
division: `builders/` and `runtime/` receive OBJECTS and call the model, and these
functions are what turns a slug into those objects — resolving curated-over-draft paths,
loading the artifacts, installing the phase plan and persisting what came back.

They are mechanism, not policy: they return data and raise (`MissingArtifactError`), never
`print()`, never `SystemExit`, and never trigger a heavier phase on their own — deciding to
auto-build belongs to the caller. Two properties hold across the package and both are one
grep away: nothing under `builders/` or `runtime/` imports an entry point back, and no
module here imports the engine — every model call is delegated to the component or the
builder that owns it, which is what lets the orchestration be read without reading a prompt.
`build.py` is the only one that reaches a builder; `transcribe.py` reaches `source_docs`,
the document plumbing the three builders share.

    _artifacts.py    curated-over-draft path choice, and what is missing
    transcribe.py    phase 0.5: the raw slots as reviewable markdown pages
    build.py         phase 0: one function per artifact, plus `build_missing`
    initialize.py    phase 1: load the instance, warm the indices, return a context
    descriptions.py  the concept descriptions, read and written apart from any build
    tag.py           assign graph concepts to bank items
    taggability.py   which concepts of the graph work as labels at all
    generate.py      phase 2: generate variants from a context
"""

from ._artifacts import (
    EXEMPLARS_BANK,
    EXEMPLARS_PROFILE,
    KNOWLEDGE_GRAPH,
    MissingArtifactError,
    content_context_path,
    exemplars_profile_path,
    knowledge_graph_path,
    load_content_context,
    missing_artifacts,
)
from .build import (
    build_artifact,
    build_exemplars_bank,
    build_exemplars_profile,
    build_knowledge_graph,
    build_missing,
    build_models,
    build_phases,
)
from .generate import (
    UnofferedModelError,
    generate,
    fixed_effort_levels,
    fixed_effort_models,
    generation_models,
    resolve_generation_effort,
    resolve_generation_model,
)
from .descriptions import (
    describe_concepts,
    load_concept_descriptions,
    load_concept_sources,
    restamp_descriptions,
    save_concept_descriptions,
)
from .initialize import RuntimeContext, initialize
from .tag import save_bank, tag_bank
from .taggability import TAGGABILITY_PHASES, review_taggability
from .transcribe import (
    CORPUS,
    EXEMPLARS,
    SLOTS,
    TRANSCRIBE_PHASES,
    delete_document_page,
    document_pages_listing,
    insert_document_page,
    transcribe_slot,
    transcription_status,
    write_document_page,
)

__all__ = [
    "CORPUS",
    "EXEMPLARS",
    "EXEMPLARS_BANK",
    "EXEMPLARS_PROFILE",
    "KNOWLEDGE_GRAPH",
    "SLOTS",
    "TAGGABILITY_PHASES",
    "TRANSCRIBE_PHASES",
    "MissingArtifactError",
    "RuntimeContext",
    "UnofferedModelError",
    "build_artifact",
    "build_exemplars_bank",
    "build_exemplars_profile",
    "build_knowledge_graph",
    "build_missing",
    "build_models",
    "build_phases",
    "content_context_path",
    "delete_document_page",
    "describe_concepts",
    "document_pages_listing",
    "exemplars_profile_path",
    "generate",
    "fixed_effort_levels",
    "fixed_effort_models",
    "generation_models",
    "initialize",
    "insert_document_page",
    "knowledge_graph_path",
    "load_concept_descriptions",
    "load_concept_sources",
    "load_content_context",
    "missing_artifacts",
    "resolve_generation_effort",
    "resolve_generation_model",
    "restamp_descriptions",
    "review_taggability",
    "save_bank",
    "save_concept_descriptions",
    "tag_bank",
    "transcribe_slot",
    "transcription_status",
    "write_document_page",
]
