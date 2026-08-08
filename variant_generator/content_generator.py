import json
import random

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError

from . import config, inference, progress
from .content_profile import ContentProfile
from .embedder import Embedder
from .knowledge_graph import KnowledgeGraph
from .prompts import generate_content_prompt
from .utils import parse_with_repair


def json_objects(text: str) -> list[str]:
    """Every balanced `{…}` span in `text`, in the order they were written.

    A model that is told to answer with one JSON object still writes drafts, examples
    and code around it. Handing the whole reply to `repair_json` makes it choose for
    us — and it chooses the first blob it finds, which is the draft. Slicing the
    candidates out first lets the caller pick the one that actually fits the schema.
    """
    spans: list[str] = []
    depth = 0
    start = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0:
                spans.append(text[start : index + 1])

    # A reply cut off mid-object is still worth repairing: it is usually the answer.
    if depth:
        spans.append(text[start:])
    return spans


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
        repair_model: str = config.REPAIR_LLM,
    ):
        self.knowledge_graph = knowledge_graph
        self.exemplars_bank = exemplars_bank
        self.embedder = embedder
        self.content_profile = content_profile
        self.item_model = content_profile.content_item
        self.context = content_profile.content_context
        self.generator_model = generator_model
        self.repair_model = repair_model
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
        fixed = self._clean_fixed(fixed)
        self._validate_input(concepts, fixed, n, curriculum)

        few_shot = self._select_few_shot(concepts, fixed)
        if not few_shot:
            logger.warning(
                f"No few-shot examples found for concepts={concepts}, fixed={fixed} — falling back to zero-shot"
            )
        progress.emit("few_shot", ids=[ex_id for ex_id, _ in few_shot], concepts=concepts)

        target_block = self._format_target_concepts(concepts)
        prerequisites_block = self._format_concept_list(self._prerequisites(concepts))
        excluded_block = self._format_concept_list(self._posteriors(concepts, curriculum))
        curriculum_block = self._format_concept_list(curriculum or [])
        rules_block = "\n".join(f"- {r}" for r in self.general_generation_rules)
        few_shot_block = self._build_few_shot_block([item for _, item in few_shot])
        instance_template = self._build_instance_template(fixed)
        field_guidance_block = self._build_field_guidance_block(fixed)
        fixed_values_block = self._build_fixed_values_block(fixed)

        accepted: list[GeneratedContent] = []
        with progress.step("generate", "Generando ítems", total=n) as reporter:
            for i in range(n):
                progress.checkpoint()
                already = self._collect_already_generated(accepted)
                prompt = generate_content_prompt(
                    context=self.context,
                    target_concepts_block=target_block,
                    prerequisites_block=prerequisites_block,
                    excluded_concepts_block=excluded_block,
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
                reporter.tick(i + 1)
                progress.emit("prompt", index=i + 1, text=prompt)
                result = self._generate_one(prompt, fixed)
                if result is None:
                    logger.warning(f"[{i + 1}/{n}] generation failed; skipping")
                    progress.emit("item.rejected", index=i + 1)
                    continue
                accepted.append(result)
                logger.success(f"[{i + 1}/{n}] item accepted")
                progress.emit(
                    "item.produced",
                    index=i + 1,
                    item=result.item.model_dump(mode="json"),
                    thinking=result.thinking,
                )

        if len(accepted) < n:
            logger.warning(f"Generated {len(accepted)}/{n} items")
        else:
            logger.success(f"Generated {len(accepted)}/{n} items")

        return accepted

    @staticmethod
    def _clean_fixed(fixed: dict[str, object] | None) -> dict[str, object]:
        """Drop blank pins.

        Pinning a field to `""` asks the prompt to demand an empty value and then
        overwrites whatever the model wrote with it, so the item comes back with the
        field empty. Nobody ever means that: an empty box in the UI means "not pinned".
        """
        kept = {
            name: value
            for name, value in (fixed or {}).items()
            if not (value is None or (isinstance(value, str) and not value.strip()))
        }
        dropped = sorted(set(fixed or {}) - set(kept))
        if dropped:
            logger.warning(f"Ignoring fixed fields with no value: {', '.join(dropped)}")
        return kept

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

    # An exemplar that merely carries the tag usually only USES the concept; the one whose
    # `primary_concept` is the target is the one it PRACTISES, which is what a few-shot
    # example has to demonstrate. Measured over the reference bank, the tag pool is 78%
    # on-target and the primary pool 100%, so the primaries go first and the rest only
    # fill the gap — ranked by similarity, because that is the best proxy available for
    # "closest to what we are asking for" among exemplars that are already off-objective.
    def _select_few_shot(
        self, concepts: list[str], fixed: dict[str, object]
    ) -> list[tuple[str, dict]]:
        target = set(concepts)
        primary: list[tuple[str, dict]] = []
        secondary: list[tuple[str, dict]] = []
        for ex_id, item in self.exemplars_bank.items():
            if not target.intersection(item.get("concepts") or []):
                continue
            if item.get("primary_concept") in target:
                primary.append((ex_id, item))
            else:
                secondary.append((ex_id, item))

        if not primary and not secondary:
            return []

        if fixed:

            def pinned(pool: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
                return [
                    (ex_id, item)
                    for ex_id, item in pool
                    if all(item.get(k) == v for k, v in fixed.items())
                ]

            if len(pinned(primary)) + len(pinned(secondary)) >= self.max_few_shot:
                primary, secondary = pinned(primary), pinned(secondary)

        if len(primary) >= self.max_few_shot:
            return random.sample(primary, self.max_few_shot)
        if not secondary:
            return primary

        by_id = dict(secondary)
        ranked = self.embedder.rank_exemplars(concepts, list(by_id))
        fill = self.max_few_shot - len(primary)
        return primary + [(ex_id, by_id[ex_id]) for ex_id in ranked[:fill]]

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

    def _neighbors(self, concepts: list[str], direction: str) -> list[str]:
        relation = config.KG_PREREQUISITE_RELATION
        if not self.knowledge_graph.has_relation(relation):
            return []
        found: set[str] = set()
        for concept in concepts:
            found.update(self.knowledge_graph.neighbors(concept, relation, direction=direction))
        return sorted(found - set(concepts))

    def _prerequisites(self, concepts: list[str]) -> list[str]:
        return self._neighbors(concepts, "out")

    def _posteriors(self, concepts: list[str], curriculum: list[str] | None) -> list[str]:
        posteriors = self._neighbors(concepts, "in")
        if curriculum:
            posteriors = [c for c in posteriors if c not in set(curriculum)]
        return posteriors

    @staticmethod
    def _format_concept_list(concepts: list[str]) -> str:
        return "\n".join(f"- {c}" for c in concepts)

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
        return "\n".join(lines)

    def _generate_one(
        self, prompt: str, fixed: dict[str, object]
    ) -> GeneratedContent | None:
        resp = inference.generate_stream(
            model=self.generator_model,
            prompt=prompt,
            think=True,
            on_token=progress.token_sink("item"),
        )
        thinking = resp.thinking
        # A model that forgets to close `<think>` leaves the whole reply on the reasoning
        # side; the answer is still in there, at the end.
        body = resp.response or (thinking or "")

        def parse(text: str) -> tuple[BaseModel | None, str | None]:
            return self._parse_and_validate(inference.split_thinking(text).response, fixed)

        item, _ = parse_with_repair(
            body,
            parse,
            repair_model=self.repair_model,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
        )

        if item is None:
            return None
        return GeneratedContent(item=item, thinking=thinking)

    def _parse_and_validate(
        self, response: str, fixed: dict[str, object]
    ) -> tuple[BaseModel | None, str | None]:
        """The best schema-conforming object in the reply, not merely the first one.

        Candidates are scored by how much of the schema they cover and, on a tie, the
        last one wins: models write their drafts before their answer.
        """
        candidates = json_objects(response) or [response]
        best: BaseModel | None = None
        best_score = -1
        error = "no JSON object in the model output"

        for candidate in candidates:
            raw = self._as_object(candidate)
            if raw is None:
                continue
            score = len(self.schema_fields.intersection(raw))
            if best is not None and score < best_score:
                continue
            try:
                item = self.item_model(**{**raw, **fixed})
            except (ValidationError, ValueError, TypeError) as e:
                error = f"{type(e).__name__}: {str(e)}"
                continue
            best, best_score = item, score

        if best is None:
            return None, error
        return best, None

    def _as_object(self, candidate: str) -> dict | None:
        """One repaired JSON object, picking the richest element if it came as a list."""
        try:
            raw = repair_json(candidate.strip(), return_objects=True)
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
        if isinstance(raw, list):
            objects = [element for element in raw if isinstance(element, dict)]
            if not objects:
                return None
            raw = max(objects, key=lambda o: len(self.schema_fields.intersection(o)))
        return raw if isinstance(raw, dict) else None
