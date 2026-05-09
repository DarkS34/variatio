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
from system.manifest import Manifest
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
        manifest: Manifest,
        generator_model: str,
    ):
        self.knowledge_graph = knowledge_graph
        self.content_bank = content_bank
        self.embedder = embedder
        self.manifest = manifest
        self.item_model = manifest.content_item
        self.context = manifest.content_context
        self.generator_model = generator_model
        self.generation_rules: list[str] = manifest.generation_rules
        self.generation_field_guidance: dict[str, str] = manifest.field_guidance("generation")

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.max_few_shot = config.MAX_FEW_SHOT_EXAMPLES
        self.schema_dict = manifest.stripped_schema()
        self.schema_str = json.dumps(self.schema_dict, indent=2, ensure_ascii=False)
        self.taggable_concepts = set(knowledge_graph.taggable_concepts)
        self.primary_field = manifest.primary_field

    def generate(self, concepts: list[str], difficulty: int, n: int = 1) -> list[GeneratedContent]:
        self._validate_input(concepts, difficulty, n)

        few_shot = self._select_few_shot(concepts, difficulty)
        if not few_shot:
            logger.warning(
                f"No few-shot examples found for concepts={concepts}, difficulty={difficulty} — falling back to zero-shot"
            )

        fixed: dict[str, object] = {"difficulty": difficulty}

        target_block = self._format_target_concepts(concepts)
        rules_block = "\n".join(f"- {r}" for r in self.generation_rules)
        few_shot_block = self._build_few_shot_block(few_shot)
        instance_template = self._build_instance_template(fixed)
        field_guidance_block = self._build_field_guidance_block(fixed)
        fixed_values_block = self._build_fixed_values_block(fixed)

        accepted: list[GeneratedContent] = []
        for i in range(n):
            already = self._collect_already_generated(accepted)
            prompt = generate_content_prompt(
                context=self.context,
                target_concepts_block=target_block,
                rules_block=rules_block,
                few_shot_block=few_shot_block,
                already_generated=already,
                instance_template=instance_template,
                field_guidance_block=field_guidance_block,
                fixed_values_block=fixed_values_block,
                schema=self.schema_str,
            )

            logger.info(f"[{i + 1}/{n}] generating item")
            result = self._generate_one(prompt, fixed)
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

    def _build_few_shot_block(self, few_shot: list[dict]) -> str:
        if not few_shot:
            return ""
        primary = self.primary_field
        properties = self.schema_dict.get("properties", {})
        parts = []
        for ex in few_shot:
            scalar_meta = []
            text_blocks: list[tuple[str, str]] = []
            primary_text = ""
            for name in properties:
                if name not in ex:
                    continue
                value = ex.get(name)
                if value is None:
                    continue
                if name == primary:
                    if isinstance(value, str) and value.strip():
                        primary_text = value.strip()
                elif isinstance(value, str) and value.strip():
                    text_blocks.append((name, value.strip()))
                elif isinstance(value, (int, float, bool)):
                    scalar_meta.append(f"{name}={value}")
            header = f" ({', '.join(scalar_meta)})" if scalar_meta else ""
            lines = ["---", f"ITEM{header}:", primary_text]
            for name, value in text_blocks:
                lines.append(f"{name.upper()}:")
                lines.append(value)
            parts.append("\n".join(lines))
        return "\n".join(parts)

    def _collect_already_generated(self, accepted: list[GeneratedContent]) -> list[str]:
        if not self.primary_field:
            return []
        out = []
        for r in accepted:
            value = getattr(r.item, self.primary_field, None)
            if isinstance(value, str) and value.strip():
                out.append(value)
        return out

    def _build_instance_template(self, fixed: dict[str, object]) -> str:
        properties = self.schema_dict.get("properties", {})
        lines = ["{"]
        items = list(properties.keys())
        for idx, name in enumerate(items):
            comma = "," if idx < len(items) - 1 else ""
            if name in fixed:
                value_repr = json.dumps(fixed[name], ensure_ascii=False)
                lines.append(f'  "{name}": {value_repr}{comma}')
            else:
                lines.append(f'  "{name}": <valor concreto para {name}>{comma}')
        lines.append("}")
        return "\n".join(lines)

    def _build_field_guidance_block(self, fixed: dict[str, object]) -> str:
        lines = [
            f"- `{name}`: {guidance}"
            for name, guidance in self.generation_field_guidance.items()
            if name not in fixed
        ]
        if not lines:
            return "(ningún campo con guía específica adicional; sigue las descripciones del schema)"
        return "\n".join(lines)

    def _build_fixed_values_block(self, fixed: dict[str, object]) -> str:
        properties = self.schema_dict.get("properties", {})
        lines = []
        for name, value in fixed.items():
            value_repr = json.dumps(value, ensure_ascii=False)
            desc = (properties.get(name, {}).get("description") or "").strip()
            entry = f"- `{name}`: debe ser exactamente {value_repr}."
            if desc:
                entry += f"\n  Descripción del schema: {desc}"
            lines.append(entry)
        return "\n".join(lines) if lines else "(no hay valores fijos)"

    def _generate_one(
        self, prompt: str, fixed: dict[str, object]
    ) -> GeneratedContent | None:
        resp = ollama.generate(model=self.generator_model, prompt=prompt, think=True)
        body, thinking = self._split_thinking(resp.response, getattr(resp, "thinking", None))

        item, err = self._parse_and_validate(body, fixed)
        for attempt in range(1, self.max_repair_attempts + 1):
            if item is not None:
                break
            logger.warning(f"repair {attempt}/{self.max_repair_attempts}: {err}")
            repair_prompt = json_repair_prompt(
                broken_output=body, error_msg=err or "invalid JSON"
            )
            resp = ollama.generate(model=config.REPAIR_LLM, prompt=repair_prompt)
            body, _ = self._split_thinking(resp.response, getattr(resp, "thinking", None))
            item, err = self._parse_and_validate(body, fixed)

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
        self, response: str, fixed: dict[str, object]
    ) -> tuple[BaseModel | None, str | None]:
        try:
            cleaned = response.strip()
            raw = repair_json(cleaned, return_objects=True)
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            if not isinstance(raw, dict):
                return None, "top-level JSON is not an object"
            raw.update(fixed)
            return self.item_model(**raw), None
        except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as e:
            return None, f"{type(e).__name__}: {str(e)}"
