"""Phase orchestration — the library's public API.

Stages are mechanism, not policy: they return data and raise (`MissingArtifactError`),
never `print()`, never `SystemExit`, and never trigger a heavier phase on their own —
deciding to auto-build belongs to the caller. They import components and loaders, and
`build.py` alone imports `builders/`; nothing under those may import a stage back.

    _artifacts.py  curated-over-draft path choice, and what is missing
    transcribe.py  phase 0.5: the raw slots as reviewable markdown pages
    build.py       phase 0: one function per artifact, plus `build_missing`
    initialize.py  phase 1: load the instance, warm the indices, return a context
    index.py       the concept descriptions, read and written apart from any build
    tag.py         assign graph concepts to bank items
    generate.py    phase 2: generate variants from a context
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
from .generate import generate
from .index import (
    describe_concepts,
    load_concept_descriptions,
    load_concept_sources,
    restamp_descriptions,
    save_concept_descriptions,
)
from .initialize import PipelineContext, initialize
from .tag import save_bank, tag_bank
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
    "TRANSCRIBE_PHASES",
    "MissingArtifactError",
    "PipelineContext",
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
    "initialize",
    "insert_document_page",
    "knowledge_graph_path",
    "load_concept_descriptions",
    "load_concept_sources",
    "load_content_context",
    "missing_artifacts",
    "restamp_descriptions",
    "save_bank",
    "save_concept_descriptions",
    "tag_bank",
    "transcribe_slot",
    "transcription_status",
    "write_document_page",
]
