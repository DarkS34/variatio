import json
import random

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError

from . import config, guardrail, inference, progress
from .embedder import Embedder
from .exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile, ItemType
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


def _public_fields(item: dict) -> dict:
    return {name: value for name, value in item.items() if not name.startswith("_")}


def clean_fixed(fixed: dict[str, object] | None) -> dict[str, object]:
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
        logger.warning(f"Campos fijados sin valor, se ignoran: {', '.join(dropped)}")
    return kept


def parse_item(response: str, fixed: dict[str, object], item_type: ItemType) -> tuple[BaseModel | None, str | None]:
    """The best schema-conforming object in the reply, not merely the first one.

    Candidates are scored by how much of the schema they cover and, on a tie, the
    last one wins: models write their drafts before their answer.

    Module level rather than a method because the evaluation arms have to parse with
    EXACTLY this tolerance: a comparison where one arm loses to a crooked JSON that
    another would have had repaired measures parsing, not content.
    """
    schema_fields = set(item_type.field_specs)
    candidates = json_objects(response) or [response]
    best: BaseModel | None = None
    best_score = -1
    error = "no JSON object in the model output"

    for candidate in candidates:
        raw = _as_object(candidate, schema_fields)
        if raw is None:
            continue
        raw = {k: v for k, v in raw.items() if k != ITEM_TYPE_KEY}
        score = len(schema_fields.intersection(raw))
        if best is not None and score < best_score:
            continue
        try:
            item = item_type.content_item(**{**raw, **fixed})
        except (ValidationError, ValueError, TypeError) as e:
            error = f"{type(e).__name__}: {e!s}"
            continue
        best, best_score = item, score

    if best is None:
        return None, error
    return best, None


def build_few_shot_block(item_type: ItemType, few_shot: list[dict]) -> str:
    """How an exemplar is shown to the model.

    Module level for the same reason as `parse_item`: the evaluation's RAG arm has to
    present its retrieved exemplars EXACTLY like this. Otherwise the comparison would
    also be measuring how the examples were laid out, and the isolated variable stops
    being the graph.

    Branching on the Python type is deliberate: list-valued fields never reach the LLM
    as raw JSON and enum-ish strings are rendered as full text blocks.
    """
    if not few_shot:
        return ""
    primary = item_type.primary_field
    properties = item_type.stripped_schema().get("properties", {})
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
            elif isinstance(value, list) and value:
                text_blocks.append((name, "\n".join(f"- {entry}" for entry in value)))
        header = f" ({', '.join(scalar_meta)})" if scalar_meta else ""
        lines = ["---", f"ITEM{header}:", primary_text]
        for name, value in text_blocks:
            lines.append(f"{name.upper()}:")
            lines.append(value)
        parts.append("\n".join(lines))
    return "\n".join(parts)


# The two operations are NOT the same, and confusing them inverts the meaning:
#   forbidden     = "it is downstream AND has NOT been covered" -> subtraction
#   assumed known = "it is a prerequisite AND HAS been covered" -> intersection
# Subtracting on the permissive side would mark as known exactly the prerequisites
# the student has not seen.
def assumed_known(closure: list[str], curriculum: list[str] | None) -> list[str]:
    if not curriculum:
        return sorted(closure)
    return sorted(set(closure) & set(curriculum))


def forbidden(closure: list[str], curriculum: list[str] | None) -> list[str]:
    if not curriculum:
        return sorted(closure)
    return sorted(set(closure) - set(curriculum))


def _as_object(candidate: str, schema_fields: set[str]) -> dict | None:
    """One repaired JSON object, picking the richest element if it came as a list."""
    try:
        raw = repair_json(candidate.strip(), return_objects=True)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    if isinstance(raw, list):
        objects = [element for element in raw if isinstance(element, dict)]
        if not objects:
            return None
        raw = max(objects, key=lambda o: len(schema_fields.intersection(o)))
    return raw if isinstance(raw, dict) else None


class GeneratedContent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    item: BaseModel
    item_type: str
    thinking: str | None = None


class ContentGenerator:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        exemplars_bank: dict,
        embedder: Embedder,
        exemplars_profile: ExemplarsProfile,
        generator_model: str,
        repair_model: str = config.REPAIR_LLM,
    ):
        self.knowledge_graph = knowledge_graph
        self.exemplars_bank = exemplars_bank
        self.embedder = embedder
        self.exemplars_profile = exemplars_profile
        self.context = exemplars_profile.content_context
        self.generator_model = generator_model
        self.repair_model = repair_model

        self.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
        self.max_few_shot = config.MAX_FEW_SHOT_EXAMPLES
        self.taggable_concepts = set(knowledge_graph.taggable_concepts)

    def generate(
        self,
        concepts: list[str],
        item_type: str | None = None,
        n: int = 1,
        fixed: dict[str, object] | None = None,
        curriculum: list[str] | None = None,
        instructions: str | None = None,
        think: bool = True,
    ) -> list[GeneratedContent]:
        target_type = self.exemplars_profile.item_type(item_type)
        fixed = self._clean_fixed(fixed)
        instructions = (instructions or "").strip()
        self._validate_input(target_type, concepts, fixed, n, curriculum, instructions)
        self._screen_instructions(instructions)

        few_shot = self._select_few_shot(target_type, concepts, fixed)
        if not few_shot:
            logger.warning(f"Sin ejemplos para «{target_type.key}» y {concepts}; se genera sin few-shot")
        
        progress.emit(
            "few_shot",
            ids=[ex_id for ex_id, _ in few_shot],
            items=[{"id": ex_id, "item": _public_fields(item)} for ex_id, item in few_shot],
            concepts=concepts,
            item_type=target_type.key,
        )

        target_block = self._format_target_concepts(concepts)
        prerequisites_block = self._format_concept_list(
            self._prerequisites(concepts, curriculum)
        )
        excluded_block = self._format_concept_list(self._posteriors(concepts, curriculum))
        curriculum_block = self._format_concept_list(curriculum or [])
        rules_block = "\n".join(f"- {r}" for r in target_type.general_generation_rules)
        few_shot_block = self._build_few_shot_block(target_type, [item for _, item in few_shot])
        instance_template = self._build_instance_template(target_type, fixed)
        field_guidance_block = self._build_field_guidance_block(target_type, fixed)
        fixed_values_block = self._build_fixed_values_block(target_type, fixed)
        item_type_block = self._build_item_type_block(target_type)
        schema_str = target_type.schema_str()

        accepted: list[GeneratedContent] = []
        with progress.step("generate", "Generando variantes", total=n) as reporter:
            for i in range(n):
                progress.checkpoint()
                already = self._collect_already_generated(target_type, accepted)
                prompt = generate_content_prompt(
                    context=self.context,
                    item_type_block=item_type_block,
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
                    schema=schema_str,
                    instructions=instructions,
                )

                reporter.tick(i + 1)
                progress.emit("prompt", index=i + 1, text=prompt)
                result = self._generate_one(prompt, fixed, target_type, think)
                if result is None:
                    logger.warning(f"[{i + 1}/{n}] descartado: no valida contra el perfil")
                    progress.emit("item.rejected", index=i + 1)
                    continue
                
                accepted.append(result)
                progress.emit(
                    "item.produced",
                    index=i + 1,
                    item=result.item.model_dump(mode="json"),
                    item_type=target_type.key,
                    thinking=result.thinking,
                )

        return accepted

    @staticmethod
    def _clean_fixed(fixed: dict[str, object] | None) -> dict[str, object]:
        return clean_fixed(fixed)

    # The instruction is free text from whoever asks for the item and it is concatenated
    # into a prompt whose pedagogical constraints are the whole point, so it is judged
    # before it gets there. Only when there is something to judge: no text, no model call.
    @staticmethod
    def _screen_instructions(instructions: str) -> None:
        if not instructions:
            return
        # The raise stays inside the step so a block marks the step itself failed: a green
        # tick on "reviewing" next to a failed job would read as if something else broke.
        with progress.step("guardrail", "Revisando las instrucciones"):
            verdict = guardrail.check(instructions)
            if verdict.blocked:
                raise ValueError(
                    f"Las instrucciones adicionales no han pasado la revisión: el modelo juez ha detectado {verdict.reason}."
                )

    def _validate_input(
        self,
        item_type: ItemType,
        concepts: list[str],
        fixed: dict[str, object],
        n: int,
        curriculum: list[str] | None,
        instructions: str = "",
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if len(instructions) > config.GENERATION_INSTRUCTIONS_MAX_CHARS:
            raise ValueError(
                f"instructions must be at most {config.GENERATION_INSTRUCTIONS_MAX_CHARS} characters, got {len(instructions)}"
            )
        if not concepts:
            raise ValueError("concepts must be a non-empty list")
        unknown_concepts = [c for c in concepts if c not in self.taggable_concepts]
        if unknown_concepts:
            raise ValueError(f"Unknown concepts (not in KG taggable set): {unknown_concepts}")
        unknown_fields = [k for k in fixed if k not in item_type.field_specs]
        if unknown_fields:
            raise ValueError(
                f"Unknown fixed fields for item type '{item_type.key}': {unknown_fields} "
                f"(it declares {list(item_type.field_specs)})"
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
    # Modality is a hard filter, not a preference: an exemplar of another modality shows
    # the model the wrong anatomy, and the few-shot block is the strongest signal in the
    # prompt. With none of the right type the batch goes zero-shot, which is honest — the
    # warning above says so — and better than teaching it to answer in the wrong shape.
    def _is_type(self, item: dict, key: str) -> bool:
        declared = item.get(ITEM_TYPE_KEY)
        if declared is None:
            return len(self.exemplars_profile.item_types) == 1
        return declared == key

    def _select_few_shot(
        self, item_type: ItemType, concepts: list[str], fixed: dict[str, object]
    ) -> list[tuple[str, dict]]:
        target = set(concepts)
        primary: list[tuple[str, dict]] = []
        secondary: list[tuple[str, dict]] = []
        for ex_id, item in self.exemplars_bank.items():
            if not self._is_type(item, item_type.key):
                continue
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
            lines.append(f"- **{c}**: {desc}" if desc else f"- **{c}**")
        return "\n".join(lines)

    def _closure(self, concepts: list[str], forward: bool) -> list[str]:
        relation = config.KG_PREREQUISITE_RELATION
        if forward:
            return self.knowledge_graph.prerequisite_closure(concepts, relation)
        return self.knowledge_graph.dependent_closure(concepts, relation)

    def _prerequisites(self, concepts: list[str], curriculum: list[str] | None) -> list[str]:
        return assumed_known(self._closure(concepts, forward=True), curriculum)

    def _posteriors(self, concepts: list[str], curriculum: list[str] | None) -> list[str]:
        return forbidden(self._closure(concepts, forward=False), curriculum)

    @staticmethod
    def _format_concept_list(concepts: list[str]) -> str:
        return "\n".join(f"- {c}" for c in concepts)

    def _build_item_type_block(self, item_type: ItemType) -> str:
        lines = [f"- **{item_type.label}** (`{item_type.key}`)"]
        if item_type.description:
            lines.append(item_type.description)
        others = [t for k, t in self.exemplars_profile.item_types.items() if k != item_type.key]
        if others:
            lines.append(
                "Otras modalidades de la asignatura, que NO debes producir aquí: "
                + ", ".join(f"{t.label} (`{t.key}`)" for t in others)
                + "."
            )
        return "\n".join(lines)

    def _build_few_shot_block(self, item_type: ItemType, few_shot: list[dict]) -> str:
        return build_few_shot_block(item_type, few_shot)

    def _collect_already_generated(
        self, item_type: ItemType, accepted: list[GeneratedContent]
    ) -> list[str]:
        out = []
        for r in accepted:
            value = getattr(r.item, item_type.primary_field, None)
            if isinstance(value, str) and value.strip():
                out.append(value)
        return out

    def _build_instance_template(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        properties = item_type.stripped_schema().get("properties", {})
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

    def _build_field_guidance_block(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        lines = [
            f"- `{name}`: {guidance}"
            for name, guidance in item_type.field_guidance("generation").items()
            if name not in fixed
        ]
        if not lines:
            return "(ningún campo con guía específica adicional; sigue las descripciones del schema)"
        return "\n".join(lines)

    def _build_fixed_values_block(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        properties = item_type.stripped_schema().get("properties", {})
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
        self, prompt: str, fixed: dict[str, object], item_type: ItemType, think: bool = True
    ) -> GeneratedContent | None:
        resp = inference.generate_stream(
            model=self.generator_model,
            prompt=prompt,
            think=think,
            on_token=progress.token_sink("item"),
        )
        
        thinking = resp.thinking
        # A model that forgets to close `<think>` leaves the whole reply on the reasoning
        # side; the answer is still in there, at the end.
        body = resp.response or (thinking or "")

        def parse(text: str) -> tuple[BaseModel | None, str | None]:
            return parse_item(inference.split_thinking(text).response, fixed, item_type)

        # The generating call above stays unconstrained EITHER WAY. With `think=True` a
        # grammar would silence the reasoning; with `think=False` it would be tempting to
        # add one, and that is precisely what must not happen: turning the reasoning off
        # has to be the only thing that changes, or a run with it off measures the grammar.
        # The repair does not need to think — it is reformatting text that already carries
        # the whole item — so it is the natural place to put the schema, and it is where
        # the key drift that this loop could never fix gets fixed.
        item, _ = parse_with_repair(
            body,
            parse,
            repair_model=self.repair_model,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            format=item_type.stripped_schema(),
        )

        if item is None:
            return None
        return GeneratedContent(item=item, item_type=item_type.key, thinking=thinking)
