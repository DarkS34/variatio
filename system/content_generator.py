import json
import random
import re

import ollama
from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError

from system import config
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph
from system.prompts import generate_content_prompt, json_repair_prompt


THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


class GeneratedContent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    item: BaseModel
    thinking: str | None = None


class ContentGenerator:
    VALID_DIFFICULTIES = (1, 2, 3, 4)

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        content_bank: dict,
        embedder: Embedder,
        item_model: type[BaseModel],
        context: dict,
        generation_rules: list[str],
        generator_model: str,
    ):
        self.knowledge_graph = knowledge_graph
        self.content_bank = content_bank
        self.embedder = embedder
        self.item_model = item_model
        self.context = context
        self.generation_rules = generation_rules
        self.generator_model = generator_model

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.max_few_shot = config.MAX_FEW_SHOT_EXAMPLES
        self.schema_str = json.dumps(item_model.model_json_schema(), indent=2, ensure_ascii=False)
        self.taggable_concepts = set(knowledge_graph.taggable_concepts)

    def generate(self, concepts: list[str], difficulty: int, n: int) -> list[GeneratedContent]:
        self._validate_input(concepts, difficulty, n)

        few_shot = self._select_few_shot(concepts, difficulty)
        if not few_shot:
            logger.warning(
                f"No few-shot examples found for concepts={concepts}, difficulty={difficulty} — falling back to zero-shot"
            )

        target_block = self._format_target_concepts(concepts)
        rubric = self.item_model.model_fields["difficulty"].description
        rules_block = "\n".join(f"- {r}" for r in self.generation_rules)

        accepted: list[GeneratedContent] = []
        for i in range(n):
            already = [r.item.statement for r in accepted]
            prompt = generate_content_prompt(
                context=self.context,
                target_concepts_block=target_block,
                difficulty=difficulty,
                difficulty_rubric=rubric,
                rules_block=rules_block,
                few_shot=few_shot,
                already_generated=already,
                schema=self.schema_str,
            )

            logger.info(f"[{i + 1}/{n}] generating item")
            result = self._generate_one(prompt, difficulty)
            if result is None:
                logger.warning(f"[{i + 1}/{n}] generation failed; skipping")
                continue
            accepted.append(result)
            logger.success(f"[{i + 1}/{n}] item accepted")

        if len(accepted) < n:
            logger.warning(f"Generated {len(accepted)}/{n} items")
        else:
            logger.success(f"Generated {len(accepted)}/{n} items")

        return accepted

    def _validate_input(self, concepts: list[str], difficulty: int, n: int) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if difficulty not in self.VALID_DIFFICULTIES:
            raise ValueError(f"difficulty must be in {self.VALID_DIFFICULTIES}, got {difficulty}")
        if not concepts:
            raise ValueError("concepts must be a non-empty list")
        unknown = [c for c in concepts if c not in self.taggable_concepts]
        if unknown:
            raise ValueError(f"Unknown concepts (not in KG taggable set): {unknown}")

    def _select_few_shot(self, concepts: list[str], difficulty: int) -> list[dict]:
        target = set(concepts)
        candidates = [
            item
            for item in self.content_bank.values()
            if target.intersection(item.get("concepts") or [])
        ]
        if not candidates:
            return []

        same_diff = [c for c in candidates if c.get("difficulty") == difficulty]
        if len(same_diff) >= self.max_few_shot:
            pool = same_diff
        else:
            pool = [
                c
                for c in candidates
                if isinstance(c.get("difficulty"), int) and abs(c["difficulty"] - difficulty) <= 1
            ]

        if len(pool) > self.max_few_shot:
            pool = random.sample(pool, self.max_few_shot)
        return pool

    def _format_target_concepts(self, concepts: list[str]) -> str:
        descriptions = self.embedder.concept_descriptions
        lines = []
        for c in concepts:
            desc = (descriptions.get(c) or "").strip()
            if desc:
                lines.append(f"- **{c}**: {desc}")
            else:
                lines.append(f"- **{c}**")
        return "\n".join(lines)

    def _generate_one(self, prompt: str, difficulty: int) -> GeneratedContent | None:
        resp = ollama.generate(model=self.generator_model, prompt=prompt, think=True)
        body, thinking = self._split_thinking(resp.response, getattr(resp, "thinking", None))

        item, err = self._parse_and_validate(body, difficulty)
        for attempt in range(1, self.max_repair_attempts + 1):
            if item is not None:
                break
            logger.warning(f"repair {attempt}/{self.max_repair_attempts}: {err}")
            repair_prompt = json_repair_prompt(
                broken_output=body, error_msg=err or "invalid JSON"
            )
            resp = ollama.generate(model=config.REPAIR_LLM, prompt=repair_prompt)
            body, _ = self._split_thinking(resp.response, getattr(resp, "thinking", None))
            item, err = self._parse_and_validate(body, difficulty)

        if item is None:
            return None
        return GeneratedContent(item=item, thinking=thinking)

    @staticmethod
    def _split_thinking(text: str, sdk_thinking: str | None) -> tuple[str, str | None]:
        inline = [m.strip() for m in THINK_TAG_RE.findall(text or "")]
        body = THINK_TAG_RE.sub("", text or "").strip()
        parts = []
        if sdk_thinking and sdk_thinking.strip():
            parts.append(sdk_thinking.strip())
        if inline:
            parts.extend(inline)
        thinking = "\n\n".join(parts) if parts else None
        return body, thinking

    def _parse_and_validate(
        self, response: str, difficulty: int
    ) -> tuple[BaseModel | None, str | None]:
        try:
            cleaned = response.strip()
            raw = repair_json(cleaned, return_objects=True)
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            if not isinstance(raw, dict):
                return None, "top-level JSON is not an object"
            raw["difficulty"] = difficulty
            return self.item_model(**raw), None
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"
