import json
from collections.abc import Callable

from json_repair import repair_json
from loguru import logger

from . import config, inference, progress
from .embedder import Embedder
from .prompts import tag_concepts_prompt
from .utils import parse_with_repair

TRACE_KEY = "_tagging"


class ConceptTagger:
    def __init__(
        self,
        embedder: Embedder,
        concept_tagger_model: str,
        embed_text: Callable[[dict], str],
        context: dict | None = None,
        top_k_candidates: int = config.TAGGER_TOP_K_CANDIDATES,
        fallback_top_k: int = config.TAGGER_FALLBACK_TOP_K,
    ):
        self.concept_tagger_model = concept_tagger_model
        self.embedder = embedder
        self.embed_text = embed_text
        self.context = context
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.top_k_candidates = top_k_candidates
        self.fallback_top_k = fallback_top_k

    # Every annotation carries how it was reached: which concepts were in play, with what
    # scores, and who decided. Without it a reviewer sees a tag and no way to judge it.
    def _trace(self, candidates: list[tuple[str, float]], method: str) -> dict:
        return {
            TRACE_KEY: {
                "candidates": [[c, round(float(s), 4)] for c, s in candidates],
                "method": method,
                "model": self.concept_tagger_model,
                "threshold": self.embedder.similarity_threshold,
            }
        }

    def tag(self, statement: str) -> dict:
        candidates = self.embedder.top_k_concepts(statement, self.top_k_candidates)
        progress.emit(
            "retrieval",
            query=statement[:200],
            candidates=[[c, round(float(s), 4)] for c, s in candidates],
        )

        def empty(method: str) -> dict:
            return {"concepts": [], "primary_concept": None, **self._trace(candidates, method)}

        if not candidates:
            logger.warning(f"No embedder candidates for statement: {statement[:80]}...")
            return empty("no_candidates")

        if len(candidates) == 1:
            concept, score = candidates[0]
            logger.info(f"Single dominant candidate '{concept}' ({score:.3f}) — skipping LLM verification")
            return {
                "concepts": [concept],
                "primary_concept": concept,
                **self._trace(candidates, "single_dominant"),
            }

        result, method = self._resolve(statement, candidates, "llm")

        # A rejection means the objective was not among the candidates, and the band is the
        # ceiling of the whole tagging: what the prefilter drops, the LLM can never recover.
        # Widening it is only worth its cost for the few items that got nothing, so it runs
        # here and not by default.
        if self._is_inconclusive(result) and self.fallback_top_k > len(candidates):
            wide = self.embedder.top_k_concepts(statement, self.fallback_top_k)
            if len(wide) > len(candidates):
                logger.info(
                    f"No candidate accepted — retrying with {len(wide)} candidates: {statement[:40]}..."
                )
                escalated, escalated_method = self._resolve(statement, wide, "llm_wide")
                if not self._is_inconclusive(escalated):
                    result, method, candidates = escalated, escalated_method, wide

        if result is None:
            logger.error("Failed to tag statement after repairs, returning empty annotation")
            return empty("failed")

        if result["primary_concept"] is None:
            candidates_log = ", ".join(f"{c} ({s:.3f})" for c, s in candidates)
            logger.warning(
                f"LLM rejected all candidates for statement: {statement[:40]}...\n"
                f"  Candidates were: {candidates_log}"
            )
            return empty("rejected")

        return {**result, **self._trace(candidates, method)}

    def _resolve(
        self, statement: str, candidates: list[tuple[str, float]], method: str
    ) -> tuple[dict | None, str]:
        candidate_names = [c for c, _ in candidates]
        prompt = tag_concepts_prompt(
            statement=statement,
            candidates=self._candidates_block(candidates),
            relations=self._relations_block(candidate_names),
            context=self.context,
        )

        result = self._verify(prompt, candidate_names, think=False)
        if self._is_inconclusive(result) and inference.supports_thinking(self.concept_tagger_model):
            logger.info(f"Inconclusive tagging — retrying with thinking: {statement[:40]}...")
            escalated = self._verify(prompt, candidate_names, think=True)
            if not self._is_inconclusive(escalated):
                return escalated, f"{method}_thinking"
        return result, method

    @staticmethod
    def _is_inconclusive(result: dict | None) -> bool:
        return result is None or result["primary_concept"] is None

    def _verify(self, prompt: str, candidate_names: list[str], think: bool) -> dict | None:
        response = inference.generate(
            model=self.concept_tagger_model, prompt=prompt, think=think
        ).response

        def parse(text: str) -> tuple[dict | None, str | None]:
            parsed = self._parse_and_validate(text, candidate_names)
            return parsed, None if parsed is not None else "invalid JSON or schema"

        result, _ = parse_with_repair(
            response,
            parse,
            repair_model=self.concept_tagger_model,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
        )
        return result

    def _candidates_block(self, candidates: list[tuple[str, float]]) -> str:
        descriptions = self.embedder.concept_descriptions
        lines = []
        for i, (concept, _) in enumerate(candidates, 1):
            lines.append(f"{i}. {concept}")
            description = " ".join((descriptions.get(concept) or "").split())
            if description:
                lines.append(f"   {description}")
        return "\n".join(lines)

    def _relations_block(self, candidate_names: list[str]) -> str:
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

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Parse error: {e}")
            return None

    @staticmethod
    def pending_ids(exemplars_bank: dict) -> list[str]:
        return [c_id for c_id, content in exemplars_bank.items() if not content.get("concepts")]

    def tag_all(
        self,
        exemplars_bank: dict,
        ids: list[str] | None = None,
        on_item: "Callable[[str, dict], None] | None" = None,
    ) -> dict:
        pending = (
            [i for i in ids if i in exemplars_bank]
            if ids is not None
            else self.pending_ids(exemplars_bank)
        )
        annotated = dict(exemplars_bank)
        total = len(pending)

        already_tagged = len(exemplars_bank) - total
        if already_tagged:
            logger.info(f"Reusing {already_tagged} existing annotation(s)")

        self.embedder.prefetch_queries(
            [self.embed_text(exemplars_bank[c_id]) for c_id in pending]
        )

        with progress.step("tagging", "Etiquetando el banco con conceptos del grafo", total) as reporter:
            for idx, c_id in enumerate(pending, 1):
                progress.checkpoint()
                logger.info(f"[{idx}/{total}] Tagging content {c_id}")
                content = exemplars_bank[c_id]
                reporter.tick(idx, detail=c_id)
                annotation = self.tag(self.embed_text(content))
                annotated[c_id] = {**content, **annotation}
                progress.emit(
                    "item.tagged",
                    id=c_id,
                    concepts=annotation["concepts"],
                    primary_concept=annotation["primary_concept"],
                    method=annotation[TRACE_KEY]["method"],
                )
                if on_item is not None:
                    on_item(c_id, annotated[c_id])

        logger.success(f"Tagged {total} item(s)")

        return annotated
