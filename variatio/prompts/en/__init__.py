"""The English prompt set, mirroring the Spanish one and carrying none of its measurements.

Interchangeable with `es/` by construction: the same names, the same signatures and the
same JSON keys, which is what lets a caller hold one without knowing which.
"""

from .repair import (
    json_repair_prompt,
)
from .admissibility import (
    classify_instructions_prompt,
)
from .sources import (
    CORRECT_ANSWER_MARK,
    EMPTY_PAGE_MARK,
    SEAM_SEPARATORS,
    format_content_prompt,
    merge_pages_prompt,
    transcribe_page_prompt,
)
from .descriptions import (
    concept_description_prompt,
    describe_domain_concepts_prompt,
)
from .tagging import (
    tag_concepts_prompt,
)
from .generation import (
    generate_content_prompt,
)
from .context import (
    synthesize_content_context_prompt,
)
from .profile import (
    DIFFICULTY_FALLBACK_DESCRIPTION,
    DIFFICULTY_FALLBACK_EXTRACTION,
    DIFFICULTY_FIELD,
    DIFFICULTY_LEVELS,
    EXEMPLARS_PROFILE_FIELD_NAMING,
    EXEMPLARS_PROFILE_SCHEMA_GRAMMAR,
    consolidate_exemplars_profile_prompt,
    repair_exemplars_profile_prompt,
    scan_item_types_prompt,
)
from .knowledge_graph import (
    assign_leftover_concepts_prompt,
    curate_graph_domains_prompt,
    extract_typed_graph_prompt,
    filter_graph_nodes_prompt,
    glean_typed_graph_prompt,
    link_cross_domain_relations_prompt,
    link_domain_relations_prompt,
    merge_candidate_groups_prompt,
    review_taggable_concepts_prompt,
    segment_syllabus_prompt,
)

__all__ = [
    "CORRECT_ANSWER_MARK",
    "DIFFICULTY_FALLBACK_DESCRIPTION",
    "DIFFICULTY_FALLBACK_EXTRACTION",
    "DIFFICULTY_FIELD",
    "DIFFICULTY_LEVELS",
    "EMPTY_PAGE_MARK",
    "EXEMPLARS_PROFILE_FIELD_NAMING",
    "EXEMPLARS_PROFILE_SCHEMA_GRAMMAR",
    "SEAM_SEPARATORS",
    "assign_leftover_concepts_prompt",
    "classify_instructions_prompt",
    "concept_description_prompt",
    "consolidate_exemplars_profile_prompt",
    "curate_graph_domains_prompt",
    "describe_domain_concepts_prompt",
    "extract_typed_graph_prompt",
    "filter_graph_nodes_prompt",
    "format_content_prompt",
    "generate_content_prompt",
    "glean_typed_graph_prompt",
    "json_repair_prompt",
    "link_cross_domain_relations_prompt",
    "link_domain_relations_prompt",
    "merge_candidate_groups_prompt",
    "merge_pages_prompt",
    "repair_exemplars_profile_prompt",
    "review_taggable_concepts_prompt",
    "scan_item_types_prompt",
    "segment_syllabus_prompt",
    "synthesize_content_context_prompt",
    "tag_concepts_prompt",
    "transcribe_page_prompt",
]
