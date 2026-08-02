import json

from json_repair import repair_json
from loguru import logger

from . import config, inference
from .embedder import Embedder
from .prompts import tag_concepts_prompt
from .utils import parse_with_repair


class ConceptTagger:
    def __init__(
        self,
        embedder: Embedder,
        concept_tagger_model: str,
        primary_field: str,
        context: dict | None = None,
        top_k_candidates: int = config.TAGGER_TOP_K_CANDIDATES,
    ):
        self.concept_tagger_model = concept_tagger_model
        self.embedder = embedder
        self.primary_field = primary_field
        self.context = context
        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.top_k_candidates = top_k_candidates

    def tag(self, statement: str) -> dict:
        empty = {"concepts": [], "primary_concept": None}

        candidates = self.embedder.top_k_concepts(statement, self.top_k_candidates)
        if not candidates:
            logger.warning(f"No embedder candidates for statement: {statement[:80]}...")
            return empty

        if len(candidates) == 1:
            concept, score = candidates[0]
            logger.info(f"Single dominant candidate '{concept}' ({score:.3f}) — skipping LLM verification")
            return {"concepts": [concept], "primary_concept": concept}

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
                result = escalated

        if result is None:
            logger.error("Failed to tag statement after repairs, returning empty annotation")
            return empty

        if result["primary_concept"] is None:
            candidates_log = ", ".join(f"{c} ({s:.3f})" for c, s in candidates)
            logger.warning(
                f"LLM rejected all candidates for statement: {statement[:40]}...\n"
                f"  Candidates were: {candidates_log}"
            )
            return empty

        return result

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

    def tag_all(self, exemplars_bank: dict) -> dict:
        pending = self.pending_ids(exemplars_bank)
        annotated = dict(exemplars_bank)
        total = len(pending)

        already_tagged = len(exemplars_bank) - total
        if already_tagged:
            logger.info(f"Reusing {already_tagged} existing annotation(s)")

        for idx, c_id in enumerate(pending, 1):
            logger.info(f"[{idx}/{total}] Tagging content {c_id}")
            content = exemplars_bank[c_id]
            annotation = self.tag(content[self.primary_field])
            annotated[c_id] = {**content, **annotation}

        logger.success(f"Tagged {total} item(s)")

        return annotated
