import json
import re
from pathlib import Path

from langchain_ollama import OllamaLLM
from loguru import logger

from .embedder import Embedder
from .knowledge_graph import KnowledgeGraph
from .utils import load_prompt


class ConceptTagger:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedder: Embedder,
        model: str = "gemma4:e4b-it-q4_K_M",
        max_repair_attempts: int = 1,
        top_k_candidates: int = 10,
    ):
        self.llm = OllamaLLM(model=model)
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

        prompt = load_prompt(
            "data_prep/concept_tagger",
            statement=statement,
            candidates=candidates_str,
        )
        response = self.llm.invoke(prompt)
        result = self._parse_and_validate(response, candidate_names)

        for attempt in range(self.max_repair_attempts):
            if result is not None:
                break
            logger.warning(f"Repair attempt {attempt + 1}/{self.max_repair_attempts}")
            repair_prompt = load_prompt(
                "data_prep/json_repair",
                broken_output=response,
                error_msg="invalid JSON or schema",
            )
            response = self.llm.invoke(repair_prompt)
            result = self._parse_and_validate(response, candidate_names)
            if result is not None:
                logger.info(f"Repair attempt {attempt + 1} succeeded")

        if result is None:
            logger.error("Failed to tag statement after repairs, returning empty annotation")
            return {"concepts": [], "primary_concept": None, "domain": None, "difficulty": None}

        primary = result["primary_concept"]
        result["domain"] = self.knowledge_graph.concept_domain.get(primary)
        result["difficulty"] = self.knowledge_graph.concept_depth(primary) if primary else None
        return result

    def tag_all(self, exercise_bank: dict, output_path: str) -> dict:
        annotated: dict[str, dict] = {}
        total = len(exercise_bank)

        for idx, (ex_id, exercise) in enumerate(exercise_bank.items(), 1):
            logger.info(f"[{idx}/{total}] Tagging exercise {ex_id}")
            annotation = self.tag(exercise["statement"])
            annotated[ex_id] = {**exercise, **annotation}

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

            # Coerce concepts to only those in the candidate list
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
