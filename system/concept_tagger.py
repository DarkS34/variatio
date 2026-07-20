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
        top_k_candidates: int = 10,
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

        candidates_str = "\n".join(
            f"{i + 1}. {concept} (score: {score:.3f})"
            for i, (concept, score) in enumerate(candidates)
        )
        candidate_names = [c for c, _ in candidates]

        prompt = tag_concepts_prompt(
            statement=statement, candidates=candidates_str, context=self.context
        )

        response = inference.generate(
            model=self.concept_tagger_model, prompt=prompt, think=False
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

    def tag_all(self, exemplars_bank: dict) -> dict:
        annotated: dict[str, dict] = {}
        total = len(exemplars_bank)

        for idx, (c_id, content) in enumerate(exemplars_bank.items(), 1):
            logger.info(f"[{idx}/{total}] Tagging content {c_id}")
            annotation = self.tag(content[self.primary_field])
            annotated[c_id] = {**content, **annotation}

        logger.success(f"Tagged {len(annotated)} item(s)")

        return annotated
