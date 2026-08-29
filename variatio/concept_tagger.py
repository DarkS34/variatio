"""Tagging an item with the concepts of the knowledge graph.

A candidate band from the embedder, then an LLM verification pass. The prompt shows each
candidate with its description and with the graph relations AMONG the candidates, never
bare names: judging by name would contradict the index the band came from, and without
the relations the model cannot tell a concept from its parent.
"""

import json
from collections.abc import Callable

from json_repair import repair_json
from loguru import logger

from . import config
from .core import inference, progress
from .core.repair import parse_with_repair
from .embedder import Embedder
from .instance.content_context import ContentContext

TRACE_KEY = "_tagging"


def tagging_schema(candidate_names: list[str]) -> dict:
    """The grammar for one tagging call, with the candidates as an `enum`.

    The prompt already demands that only candidates be used; this states the same rule
    where the decoder can enforce it. `_parse_and_validate` still filters, because the
    escalated pass runs unconstrained and an invented name can arrive from there.
    """
    return {
        "type": "object",
        "properties": {
            "concepts": {"type": "array", "items": {"enum": list(candidate_names)}},
            "primary_concept": {"enum": [*candidate_names, None]},
        },
        "required": ["concepts", "primary_concept"],
    }


class ConceptTagger:
    """Assign graph concepts to an item and name the one it PRACTISES as primary."""

    def __init__(
        self,
        embedder: Embedder,
        concept_tagger_model: str,
        embed_text: Callable[[dict], str],
        prompts,
        primary_text: Callable[[dict], str] | None = None,
        context: ContentContext | None = None,
        top_k_candidates: int | None = None,
        fallback_top_k: int | None = None,
    ):
        """Wire the tagger to an embedder, a model and its workspace's prompt set."""
        self.concept_tagger_model = concept_tagger_model
        self.prompts = prompts
        self.embedder = embedder
        self.embed_text = embed_text
        # What the tagger READS is every indexed field; what the live feed shows is the
        # statement alone. A caller naming neither keeps the old single-renderer behaviour.
        self.primary_text = primary_text or embed_text
        self.context = context if context is not None else ContentContext()
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.top_k_candidates = (
            config.TAGGER_TOP_K_CANDIDATES if top_k_candidates is None else top_k_candidates
        )
        self.fallback_top_k = (
            config.TAGGER_FALLBACK_TOP_K if fallback_top_k is None else fallback_top_k
        )

    def _trace(self, candidates: list[tuple[str, float]], method: str) -> dict:
        """Record how the annotation was reached: candidates, scores, model and method.

        Every annotation carries one; without it a reviewer sees a tag and no way to
        judge it.
        """
        return {
            TRACE_KEY: {
                "candidates": [[c, round(float(s), 4)] for c, s in candidates],
                "method": method,
                "model": self.concept_tagger_model,
                "threshold": self.embedder.similarity_threshold,
            }
        }

    def tag(self, statement: str) -> dict:
        """Annotate one statement with its concepts and its primary concept.

        On a rejection it retries once over `fallback_top_k` candidates: the prefilter's
        band is the ceiling of the whole tagging — what it drops the LLM can never
        recover — so widening it is worth the extra call only where nothing was found.
        """
        candidates = self.embedder.top_k_concepts(statement, self.top_k_candidates)
        progress.emit(
            "retrieval",
            query=statement[:200],
            candidates=[[c, round(float(s), 4)] for c, s in candidates],
        )

        def empty(method: str) -> dict:
            """An annotation with nothing decided, carrying its trace."""
            return {"concepts": [], "primary_concept": None, **self._trace(candidates, method)}

        if not candidates:
            logger.warning(f"No candidate from the index for: {statement[:60]}…")
            return empty("no_candidates")

        # With a fixed k, one candidate is a statement about how small the index is.
        if len(candidates) == 1:
            concept, _ = candidates[0]
            return {
                "concepts": [concept],
                "primary_concept": concept,
                **self._trace(candidates, "single_dominant"),
            }

        result, method = self._resolve(statement, candidates, "llm")

        if self._is_inconclusive(result) and self.fallback_top_k > len(candidates):
            wide = self.embedder.top_k_concepts(statement, self.fallback_top_k)
            if len(wide) > len(candidates):
                logger.debug(
                    f"No candidate accepted; retrying with {len(wide)}: {statement[:40]}…"
                )
                escalated, escalated_method = self._resolve(statement, wide, "llm_wide")
                if not self._is_inconclusive(escalated):
                    result, method, candidates = escalated, escalated_method, wide

        if result is None:
            logger.error(f"Left untagged after the repairs: {statement[:60]}…")
            return empty("failed")

        if result["primary_concept"] is None:
            logger.warning(f"The model rejected every candidate: {statement[:60]}…")
            return empty("rejected")

        return {**result, **self._trace(candidates, method)}

    def _resolve(
        self, statement: str, candidates: list[tuple[str, float]], method: str
    ) -> tuple[dict | None, str]:
        """Verify one candidate band, escalating to a reasoning pass if it is inconclusive."""
        candidate_names = [c for c, _ in candidates]
        prompt = self.prompts.tag_concepts_prompt(
            statement=statement,
            candidates=self._candidates_block(candidates),
            relations=self._relations_block(candidate_names),
            context_block=self.context.prompt_block(),
        )

        result = self._verify(prompt, candidate_names, think=False)
        if (
            self._is_inconclusive(result)
            and config.THINK_CONCEPT_TAGGER
            and inference.supports_thinking(self.concept_tagger_model)
        ):
            logger.debug(f"Tagging inconclusive; retrying with reasoning: {statement[:40]}…")
            escalated = self._verify(prompt, candidate_names, think=config.THINK_CONCEPT_TAGGER)
            if not self._is_inconclusive(escalated):
                return escalated, f"{method}_thinking"
        return result, method

    @staticmethod
    def _is_inconclusive(result: dict | None) -> bool:
        """True when the pass produced nothing, or named no primary concept."""
        return result is None or result["primary_concept"] is None

    def _verify(self, prompt: str, candidate_names: list[str], think: bool | str) -> dict | None:
        """Run one tagging call and parse its reply, repairing it if need be.

        The reasoning pass drops the grammar: it exists to buy deliberation on an item
        the first pass could not place, and a grammar would take exactly that away.
        """
        schema = tagging_schema(candidate_names)
        response = inference.generate(
            model=self.concept_tagger_model,
            prompt=prompt,
            think=think,
            format=None if think else schema,
            temperature=inference.judgement_temperature(think),
        ).response

        def parse(text: str) -> tuple[dict | None, str | None]:
            """Parse one reply, reporting why it failed when it does."""
            parsed = self._parse_and_validate(text, candidate_names)
            return parsed, None if parsed is not None else "invalid JSON or schema"

        result, _ = parse_with_repair(
            response,
            parse,
            repair_model=self.concept_tagger_model,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            format=schema,
            prompts=self.prompts,
        )
        return result

    def _candidates_block(self, candidates: list[tuple[str, float]]) -> str:
        """Render the numbered candidates, each with its description."""
        descriptions = self.embedder.concept_descriptions
        lines = []
        for i, (concept, _) in enumerate(candidates, 1):
            lines.append(f"{i}. {concept}")
            description = " ".join((descriptions.get(concept) or "").split())
            if description:
                lines.append(f"   {description}")
        return "\n".join(lines)

    def _relations_block(self, candidate_names: list[str]) -> str:
        """Render the graph relations holding BETWEEN the candidates, each stated once.

        An undirected relation is keyed on the sorted pair, so it is not listed twice.
        """
        kg = self.embedder.knowledge_graph
        names = set(candidate_names)
        lines: list[str] = []
        seen: set[tuple] = set()

        for verb, graph in kg.graphs.items():
            directed = graph.is_directed()
            for concept in candidate_names:
                if concept not in graph:
                    continue
                neighbors = (
                    kg.neighbors(concept, verb, direction="out")
                    if directed
                    else kg.neighbors(concept, verb)
                )
                for neighbor in neighbors:
                    if neighbor == concept or neighbor not in names:
                        continue
                    key = (
                        (verb, concept, neighbor)
                        if directed
                        else (verb, *sorted((concept, neighbor)))
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append(f"- {concept} {verb} {neighbor}")

        return "\n".join(lines)

    def _parse_and_validate(self, response: str, candidate_names: list[str]) -> dict | None:
        """Return an annotation restricted to the candidates, or None if unusable.

        An answer that names nothing at all is a legitimate «none of these» and comes
        back as an empty annotation rather than as a parse failure.
        """
        try:
            data = repair_json(response, return_objects=True)

            if not isinstance(data, dict):
                return None
            if "concepts" not in data or "primary_concept" not in data:
                return None
            if not isinstance(data["concepts"], list):
                return None

            if not data["concepts"] and data["primary_concept"] in (None, ""):
                return {"concepts": [], "primary_concept": None}

            valid_concepts = [c for c in data["concepts"] if c in candidate_names]
            primary = data["primary_concept"]
            if primary not in candidate_names:
                primary = valid_concepts[0] if valid_concepts else None
            if not primary:
                return None

            return {"concepts": valid_concepts or [primary], "primary_concept": primary}

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    def pending_ids(exemplars_bank: dict) -> list[str]:
        """The bank ids still without concepts.

        An empty `concepts` list counts as untagged, so an item the LLM rejected is
        retried on every later run: the index improves across runs, which makes a
        rejection provisional.
        """
        return [c_id for c_id, content in exemplars_bank.items() if not content.get("concepts")]

    def tag_all(
        self,
        exemplars_bank: dict,
        ids: list[str] | None = None,
        on_item: "Callable[[str, dict], None] | None" = None,
    ) -> dict:
        """Tag the pending items of the bank, or the given ids, and return the whole bank."""
        pending = (
            [i for i in ids if i in exemplars_bank]
            if ids is not None
            else self.pending_ids(exemplars_bank)
        )
        annotated = dict(exemplars_bank)
        total = len(pending)

        self.embedder.prefetch_queries(
            [self.embed_text(exemplars_bank[c_id]) for c_id in pending]
        )

        with progress.step("tagging", "Etiquetando el banco con conceptos del grafo", total) as reporter:
            for idx, c_id in enumerate(pending, 1):
                progress.checkpoint()
                content = exemplars_bank[c_id]
                statement = self.embed_text(content)
                reporter.tick(idx, detail=c_id)
                annotation = self.tag(statement)
                annotated[c_id] = {**content, **annotation}
                progress.emit(
                    "item.tagged",
                    id=c_id,
                    text=self.primary_text(content)[:200],
                    concepts=annotation["concepts"],
                    primary_concept=annotation["primary_concept"],
                    method=annotation[TRACE_KEY]["method"],
                )
                if on_item is not None:
                    on_item(c_id, annotated[c_id])

        return annotated
