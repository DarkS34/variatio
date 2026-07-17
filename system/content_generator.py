import json
import random
import re

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError

from system import config, inference
from system.embedder import Embedder
from system.knowledge_graph import KnowledgeGraph
from system.content_profile import ContentProfile
from system.prompts import generate_content_prompt, json_repair_prompt


THINK_TAG_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)


class GeneratedContent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    item: BaseModel
    thinking: str | None = None


class ContentGenerator:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        exemplars_bank: dict,
        embedder: Embedder,
        content_profile: ContentProfile,
        generator_model: str,
    ):
        self.knowledge_graph = knowledge_graph
        self.exemplars_bank = exemplars_bank
        self.embedder = embedder
        self.content_profile = content_profile
        self.item_model = content_profile.content_item
        self.context = content_profile.content_context
        self.generator_model = generator_model
        self.general_generation_rules: list[str] = content_profile.general_generation_rules
        self.generation_field_guidance: dict[str, str] = content_profile.field_guidance("generation")

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.max_few_shot = config.MAX_FEW_SHOT_EXAMPLES
        self.schema_dict = content_profile.stripped_schema()
        self.schema_str = json.dumps(self.schema_dict, indent=2, ensure_ascii=False)
        self.schema_fields = set(self.schema_dict.get("properties", {}))
        self.taggable_concepts = set(knowledge_graph.taggable_concepts)
        self.primary_field = content_profile.primary_field

    def generate(
        self,
        concepts: list[str],
        n: int = 1,
        fixed: dict[str, object] | None = None,
        curriculum: list[str] | None = None,
    ) -> list[GeneratedContent]:
        fixed = dict(fixed or {})
        self._validate_input(concepts, fixed, n, curriculum)

        few_shot = self._select_few_shot(concepts, fixed)
        if not few_shot:
            logger.warning(
                f"No few-shot examples found for concepts={concepts}, fixed={fixed} — falling back to zero-shot"
            )

        target_block = self._format_target_concepts(concepts)
        curriculum_block = self._format_curriculum(curriculum)
        rules_block = "\n".join(f"- {r}" for r in self.general_generation_rules)
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
                curriculum_block=curriculum_block,
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

    def _validate_input(
        self,
        concepts: list[str],
        fixed: dict[str, object],
        n: int,
        curriculum: list[str] | None,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if not concepts:
            raise ValueError("concepts must be a non-empty list")
        unknown_concepts = [c for c in concepts if c not in self.taggable_concepts]
        if unknown_concepts:
            raise ValueError(f"Unknown concepts (not in KG taggable set): {unknown_concepts}")
        unknown_fields = [k for k in fixed if k not in self.schema_fields]
        if unknown_fields:
            raise ValueError(
                f"Unknown fixed fields (not in content_profile schema): {unknown_fields}"
            )
        if curriculum is not None:
            unknown_curriculum = [c for c in curriculum if c not in self.taggable_concepts]
            if unknown_curriculum:
                raise ValueError(
                    f"Unknown curriculum concepts (not in KG taggable set): {unknown_curriculum}"
                )
            outside = [c for c in concepts if c not in set(curriculum)]
            if outside:
                raise ValueError(
                    f"Target concepts not contained in curriculum: {outside}"
                )

    def _select_few_shot(self, concepts: list[str], fixed: dict[str, object]) -> list[dict]:
        target = set(concepts)
        candidates = [
            item
            for item in self.exemplars_bank.values()
            if target.intersection(item.get("concepts") or [])
        ]
        if not candidates:
            return []

        if fixed:
            matching = [
                c for c in candidates if all(c.get(k) == v for k, v in fixed.items())
            ]
            if len(matching) >= self.max_few_shot:
                candidates = matching

        if len(candidates) > self.max_few_shot:
            candidates = random.sample(candidates, self.max_few_shot)
        return candidates

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

    def _format_curriculum(self, curriculum: list[str] | None) -> str:
        if not curriculum:
            return ""
        return "\n".join(f"- {c}" for c in curriculum)

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
        resp = inference.generate(model=self.generator_model, prompt=prompt, think=True)
        body, thinking = self._split_thinking(resp.response, getattr(resp, "thinking", None))

        item, err = self._parse_and_validate(body, fixed)
        for attempt in range(1, self.max_repair_attempts + 1):
            if item is not None:
                break
            logger.warning(f"repair {attempt}/{self.max_repair_attempts}: {err}")
            repair_prompt = json_repair_prompt(
                broken_output=body, error_msg=err or "invalid JSON"
            )
            resp = inference.generate(model=config.REPAIR_LLM, prompt=repair_prompt)
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
