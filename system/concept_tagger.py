import json
import re
from pathlib import Path

import ollama
from loguru import logger

from .embedder import Embedder
from .knowledge_graph import KnowledgeGraph
from .prompts import tag_concepts as _tag_concepts_prompt, json_repair as _json_repair_prompt


class ConceptTagger:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedder: Embedder,
        concept_tagger_model: str,
        max_repair_attempts: int = 1,
        top_k_candidates: int = 10,
    ):
        self.concept_tagger_model = concept_tagger_model
        self.knowledge_graph = knowledge_graph
        self.embedder = embedder
        self.max_repair_attempts = max_repair_attempts
        self.top_k_candidates = top_k_candidates

    def tag(self, statement: str) -> dict:
        candidates = self.embedder.top_k_concepts(statement, self.top_k_candidates)
        candidates_str = "\n".join(
            f"{i + 1}. {concept} (score: {score:.3f})"
            for i, (concept, score) in enumerate(candidates)
        )
        candidate_names = [c for c, _ in candidates]

        prompt = _tag_concepts_prompt(statement=statement, candidates=candidates_str)

        response = ollama.generate(model=self.concept_tagger_model, prompt=prompt).response
        result = self._parse_and_validate(response, candidate_names)

        for attempt in range(self.max_repair_attempts):
            if result is not None:
                break
            logger.warning(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")

            repair_prompt = _json_repair_prompt(broken_output=response, error_msg="invalid JSON or schema")

            response = ollama.generate(model=self.concept_tagger_model, prompt=repair_prompt).response
            result = self._parse_and_validate(response, candidate_names)
            if result is not None:
                logger.info(f"Repair attempt {attempt + 1} succeeded")

        if result is None:
            logger.error("Failed to tag statement after repairs, returning empty annotation")
            return {
                "concepts": [],
                "primary_concept": None,
                "domain": None,
            }

        primary = result["primary_concept"]
        result["domain"] = self.knowledge_graph.concept_domain.get(primary)

        return result

    def tag_all(self, content_bank: dict, output_path: str) -> dict:
        annotated: dict[str, dict] = {}
        total = len(content_bank)

        for idx, (c_id, content) in enumerate(content_bank.items(), 1):
            logger.info(f"[{idx}/{total}] Tagging content {c_id}")
            annotation = self.tag(content["statement"])
            annotated[c_id] = {**content, **annotation}

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as f:
            json.dump(annotated, f, ensure_ascii=False, indent=2)
        
        logger.success(f"Saved {len(annotated)} annotated exercise(s) to {output}")

        return annotated

    def _parse_and_validate(self, response: str, candidate_names: list[str]) -> dict | None:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            data = json.loads(cleaned)

            if not isinstance(data, dict):
                return None
            if "concepts" not in data or "primary_concept" not in data:
                return None
            if not isinstance(data["concepts"], list) or not data["concepts"]:
                return None

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
