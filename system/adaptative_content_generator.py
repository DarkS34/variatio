import json
import random
import re

from langchain_ollama import OllamaLLM
from loguru import logger

from .embedder import Embedder
from .knowledge_graph import KnowledgeGraph
from .utils import load_prompt

FIELD_KEYS = ("statement", "solution", "concepts", "hints")


class AdaptativeContentGenerator:
    def __init__(
        self,
        llm: OllamaLLM,
        embedder: Embedder,
        bank: dict,
        knowledge_graph: KnowledgeGraph,
        n_few_shots: int = 3,
        max_repair_attempts: int = 1,
    ):
        self.llm = llm
        self.embedder = embedder
        self.bank = bank
        self.knowledge_graph = knowledge_graph
        self.n_few_shots = n_few_shots
        self.max_repair_attempts = max_repair_attempts

    def generate(self, concept: str, fields: set[str]) -> dict:
        fields = {f for f in fields if f in FIELD_KEYS} | {"statement"}
        domain = self.knowledge_graph.concept_domain.get(concept, "desconocido")
        few_shots = self._collect_few_shots(concept)
        logger.debug(f"Generating exercise for '{concept}' with {len(few_shots)} few-shot(s)")

        prompt = load_prompt(
            "generation/exercise",
            concept=concept,
            domain=domain,
            few_shots=self._format_few_shots(few_shots),
            fields=", ".join(sorted(fields)),
        )

        response = self.llm.invoke(prompt)
        result = self._parse_and_validate(response, fields)

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
            result = self._parse_and_validate(response, fields)

        if result is None:
            logger.error("Generation failed; returning placeholder")
            return {"statement": "(no se pudo generar el ejercicio, vuelve a intentarlo)"}

        return result

    def _collect_few_shots(self, concept: str) -> list[dict]:
        matching = [
            ex for ex in self.bank.values()
            if ex.get("primary_concept") == concept
        ]
        if len(matching) >= self.n_few_shots:
            return random.sample(matching, self.n_few_shots)

        seen_ids = {id(ex) for ex in matching}
        similar = self.embedder.find_similar_exercises(concept, n=self.n_few_shots * 2)
        for ex_id, _ in similar:
            ex = self.bank.get(ex_id)
            if ex and id(ex) not in seen_ids:
                matching.append(ex)
                seen_ids.add(id(ex))
                if len(matching) >= self.n_few_shots:
                    break
        return matching[: self.n_few_shots]

    @staticmethod
    def _format_few_shots(few_shots: list[dict]) -> str:
        if not few_shots:
            return "(no hay ejemplos del banco para este concepto)"
        return "\n\n".join(
            f"Ejemplo {i + 1}:\n{ex['statement']}"
            for i, ex in enumerate(few_shots)
        )

    @staticmethod
    def _parse_and_validate(response: str, fields: set[str]) -> dict | None:
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
            data = json.loads(cleaned)
            if not isinstance(data, dict) or "statement" not in data:
                return None
            if not isinstance(data["statement"], str) or not data["statement"].strip():
                return None
            return {k: v for k, v in data.items() if k in fields}
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Parse error: {e}")
            return None