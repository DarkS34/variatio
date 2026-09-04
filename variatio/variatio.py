"""Generating a new item: few-shot from the bank, the curriculum, and the checks.

The prompt is built around the knowledge frontier — the target concepts, the
prerequisites the item may lean on, and what comes after the targets — forbidden outright
when a curriculum says it is untaught, merely not the thing to practise when nobody said
where the class stands. `parse_item` and `build_few_shot_block` live at module level rather than on
the generator because the study's evaluation arms have to present and parse EXACTLY as
this does; otherwise the comparison measures the layout and the parsing, not the graph.
"""

import json
import random
from collections.abc import Callable

from json_repair import repair_json
from loguru import logger
from pydantic import BaseModel, ConfigDict, ValidationError

from . import admissibility, checks, config, guardrail
from .concept_tagger import ConceptTagger
from .core import inference, progress
from .core.repair import parse_with_repair
from .embedder import Embedder
from .instance.content_context import ContentContext
from .instance.exemplars_profile import ITEM_TYPE_KEY, ExemplarsProfile, ItemType
from .instance.knowledge_graph import KnowledgeGraph


def json_objects(text: str) -> list[str]:
    """Return every balanced `{…}` span in `text`, in the order they were written.

    A model told to answer with one JSON object still writes drafts, examples and code
    around it, and `repair_json` over the whole reply picks the first blob it finds —
    the draft. Slicing the candidates out first lets the caller pick the one that fits.
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
    """Drop the underscore-prefixed bookkeeping keys before an item goes to the UI."""
    return {name: value for name, value in item.items() if not name.startswith("_")}


def _sentence_case(text: str) -> str:
    """Upper-case the first letter and leave the rest alone.

    NOT `str.capitalize()`, which lowercases everything after it: an owner's `where`
    quotes a screen control by name, and capitalising it names one nobody can find.
    """
    return text[:1].upper() + text[1:]


def clean_fixed(fixed: dict[str, object] | None) -> dict[str, object]:
    """Drop blank pins.

    Pinning a field to `""` makes the prompt demand an empty value and then overwrites
    whatever the model wrote with it. An empty box in the UI means "not pinned".
    """
    kept = {
        name: value
        for name, value in (fixed or {}).items()
        if not (value is None or (isinstance(value, str) and not value.strip()))
    }
    dropped = sorted(set(fixed or {}) - set(kept))
    if dropped:
        logger.warning(f"Pinned fields with no value, ignored: {', '.join(dropped)}")
    return kept


def parse_item(response: str, fixed: dict[str, object], item_type: ItemType) -> tuple[BaseModel | None, str | None]:
    """Return the best schema-conforming object in the reply, not merely the first one.

    Candidates are scored by how much of the schema they cover and, on a tie, the last
    one wins: models write their drafts before their answer. Module level rather than a
    method because the evaluation arms must parse with exactly this tolerance — an arm
    losing to a crooked JSON another would have had repaired measures parsing, not
    content.
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
        floor = checks.content_floor(item, item_type)
        if floor:
            error = floor
            continue
        ignored = [k for k, v in fixed.items() if k in raw and raw[k] != v]
        if ignored:
            logger.warning(f"The model ignored pinned value(s), overwriting them: {', '.join(ignored)}")
        best, best_score = item, score

    if best is None:
        return None, error
    return best, None


NEIGHBOUR = "neighbour"


def _split_exemplar_fields(
    ex: dict, properties: dict, primary: str
) -> tuple[str, list[tuple[str, str]], list[str]]:
    """Sort one exemplar's fields into primary text, text blocks and scalar metadata.

    Branching on the Python type is deliberate: list-valued fields never reach the LLM
    as raw JSON, and enum-ish strings are rendered as full text blocks.
    """
    scalar_meta: list[str] = []
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
    return primary_text, text_blocks, scalar_meta


def build_few_shot_block(
    item_type: ItemType, few_shot: list[dict], origins: list[str] | None = None
) -> str:
    """Render the few-shot exemplars the way the model is shown them.

    Module level for the same reason as `parse_item`: the evaluation's RAG arm has to
    present its retrieved exemplars exactly like this, or the comparison also measures
    how the examples were laid out and the isolated variable stops being the graph.
    """
    if not few_shot:
        return ""
    primary = item_type.primary_field
    properties = item_type.stripped_schema().get("properties", {})
    parts = []
    for position, ex in enumerate(few_shot):
        primary_text, text_blocks, scalar_meta = _split_exemplar_fields(ex, properties, primary)
        header = f" ({', '.join(scalar_meta)})" if scalar_meta else ""
        lines = ["---"]
        if origins and position < len(origins) and origins[position] == NEIGHBOUR:
            prior = ex.get("primary_concept") or "concepto previo"
            lines.append(
                f"(Ejemplo de un concepto previo: «{prior}». Referencia de forma, no del objetivo.)"
            )
        lines += [f"{primary.upper()}{header}:", primary_text]
        for name, value in text_blocks:
            lines.append(f"{name.upper()}:")
            lines.append(value)
        parts.append("\n".join(lines))
    return "\n".join(parts)


# The asymmetry below is deliberate; symmetry here would be a bug. Assumed known is an
# INTERSECTION ("a prerequisite AND covered"), forbidden a SUBTRACTION ("downstream AND
# not covered"): subtracting on the permissive side would mark as known exactly the
# prerequisites the student has not seen.
def assumed_known(closure: list[str], curriculum: list[str] | None) -> list[str]:
    """Intersect a prerequisite closure with the curriculum; no curriculum keeps it whole."""
    if not curriculum:
        return list(closure)
    covered = set(curriculum)
    return [name for name in closure if name in covered]


def forbidden(closure: list[str], curriculum: list[str] | None) -> list[str]:
    """Subtract the curriculum from a dependent closure; no curriculum keeps it whole.

    What the whole closure MEANS differs by that condition, and the prompt and the checks
    both read it: with a curriculum it is «no impartido», without one it is «viene
    después» — usable as scaffolding, never the thing practised (`checks.closure_rule`).
    """
    if not curriculum:
        return list(closure)
    covered = set(curriculum)
    return [name for name in closure if name not in covered]


def _as_object(candidate: str, schema_fields: set[str]) -> dict | None:
    """Return one repaired JSON object, picking the richest element if it came as a list."""
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


class GeneratedVariant(BaseModel):
    """One accepted item, with the reasoning and the checks that produced it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    item: BaseModel
    item_type: str
    thinking: str | None = None
    checks: dict | None = None
    retried: int = 0


def generate_with_retries(
    attempt: Callable[[str | None], GeneratedVariant | None],
    verify: Callable[[GeneratedVariant], dict] | None,
    max_retries: int,
    index: int = 1,
) -> GeneratedVariant | None:
    """Attempt one variant, retrying with a correction while the checks ask for it.

    The last attempt is returned whether or not it satisfied the checks: a flagged item
    is still worth showing, and its `checks` say why it was flagged.
    """
    result = attempt(None)
    if result is None or verify is None:
        return result
    result.checks = verify(result)
    while result.retried < max_retries and checks.needs_retry(result.checks):
        reasons = list(result.checks.get("reasons") or [])
        # `max` travels with the event because the person waiting is told a retry is
        # happening and why, on the run strip itself: «reintento 1 de 2» says how much
        # patience is left, where a bare ordinal says only that something went wrong.
        progress.emit(
            "item.retried",
            index=index,
            attempt=result.retried + 1,
            max=max_retries,
            reasons=reasons,
        )
        logger.info(
            f"[generate] Retry {result.retried + 1}/{max_retries} of variant {index}: "
            f"{'; '.join(reasons)}"
        )
        again = attempt(checks.correction_text(result.checks))
        if again is None:
            break
        again.retried = result.retried + 1
        again.checks = verify(again)
        result = again
    return result


class VariantGenerator:
    """Produce new items for a set of target concepts, grounded in one workspace."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        exemplars_bank: dict,
        embedder: Embedder,
        exemplars_profile: ExemplarsProfile,
        generator_model: str,
        prompts,
        prerequisite_relation: str | None,
        content_context: ContentContext | None = None,
        repair_model: str | None = None,
        tagger: ConceptTagger | None = None,
    ):
        """Wire the generator to one workspace's graph, bank, profile and prompt set."""
        self.knowledge_graph = knowledge_graph
        self.exemplars_bank = exemplars_bank
        self.embedder = embedder
        self.exemplars_profile = exemplars_profile
        self.prompts = prompts
        # The graph's own label for «is a prerequisite of», in the instance's language: a
        # field and not a `config` read, which would be the installation's for every
        # workspace.
        self.prerequisite_relation = prerequisite_relation
        self.content_context = content_context or ContentContext()
        self.generator_model = generator_model
        self.repair_model = config.REPAIR_LLM if repair_model is None else repair_model
        self.tagger = tagger

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
        think: bool | str = True,
        model: str | None = None,
        check: bool = True,
        ruling: object | None = None,
        avoid: list[str] | None = None,
        on_accepted: Callable[[GeneratedVariant, int], None] | None = None,
    ) -> list[GeneratedVariant]:
        """Produce up to `n` items for `concepts`, checking and retrying each one.

        A pre-screened `ruling` is honoured as it arrives, which is how the study pays
        the admissibility judge once for the three arms. `on_accepted` fires per item,
        so a cancelled run keeps whatever had already validated. `model` overrides the
        installation's default writer for this commission alone — the caller checks it
        against what the installation offers (`stages.resolve_generation_model`); nothing
        here does, so the study's arms keep passing none and get the default.
        """
        writer = model or self.generator_model
        target_type = self.exemplars_profile.item_type(item_type)
        fixed = self._clean_fixed(fixed)
        instructions = (instructions or "").strip()
        self._validate_input(target_type, concepts, fixed, n, curriculum, instructions)
        if ruling is None:
            ruling = self._screen_instructions(target_type, concepts, instructions)

        few_shot, origins = self._select_few_shot(target_type, concepts, fixed)
        if not few_shot:
            logger.warning(f"No examples for «{target_type.key}» and {concepts}; generating without few-shot")

        self._emit_few_shot(few_shot, origins, concepts, target_type)

        target_block = self._format_target_concepts(concepts)
        prerequisites_block = self._format_prerequisites(
            self._prerequisites(concepts, curriculum)
        )
        posteriors = self._posteriors(concepts, curriculum)
        excluded_block = self._format_concept_list(posteriors)
        curriculum_block = self._format_concept_list(curriculum or [])
        rules_block = "\n".join(f"- {r}" for r in target_type.general_generation_rules)
        few_shot_block = self._build_few_shot_block(
            target_type, [item for _, item in few_shot], [origins[ex_id] for ex_id, _ in few_shot]
        )
        instance_template = self._build_instance_template(target_type, fixed)
        fields_block = self._build_fields_block(target_type, fixed)
        fixed_values_block = self._build_fixed_values_block(target_type, fixed)
        item_type_block = self._build_item_type_block(target_type)

        accepted: list[GeneratedVariant] = []
        with progress.step("generate", "Generando variantes", total=n) as reporter:
            for i in range(n):
                progress.checkpoint()
                already = list(avoid or []) + self._collect_already_generated(
                    target_type, accepted
                )
                reporter.start(i + 1)

                def attempt(correction: str | None) -> GeneratedVariant | None:
                    """Build the prompt for this slot and generate one candidate item."""
                    prompt = self.prompts.generate_content_prompt(
                        context_block=self.content_context.prompt_block(),
                        item_type_block=item_type_block,
                        target_concepts_block=target_block,
                        prerequisites_block=prerequisites_block,
                        excluded_concepts_block=excluded_block,
                        curriculum_block=curriculum_block,
                        rules_block=rules_block,
                        few_shot_block=few_shot_block,
                        already_generated=already,
                        instance_template=instance_template,
                        fields_block=fields_block,
                        fixed_values_block=fixed_values_block,
                        instructions=instructions,
                        requests=ruling.requests if ruling.checked else None,
                        correction=correction,
                    )
                    progress.emit("prompt", index=i + 1, text=prompt)
                    return self._generate_one(prompt, fixed, target_type, think, writer)

                def verify(result: GeneratedVariant) -> dict:
                    """Run the checks over one candidate, against the batch so far."""
                    with progress.step("check", "Comprobando la variante"):
                        return checks.run(
                            result.item,
                            target_type,
                            targets=concepts,
                            forbidden=posteriors,
                            rule=checks.closure_rule(curriculum),
                            embedder=self.embedder,
                            tagger=self.tagger,
                            few_shot=few_shot,
                            batch=[r.item for r in accepted],
                        )

                result = generate_with_retries(
                    attempt,
                    verify if check else None,
                    config.CHECK_MAX_RETRIES,
                    index=i + 1,
                )
                if result is None:
                    logger.warning(f"[{i + 1}/{n}] discarded: does not validate against the profile")
                    progress.emit("item.rejected", index=i + 1)
                    continue

                accepted.append(result)
                progress.emit(
                    "item.produced",
                    index=i + 1,
                    item=result.item.model_dump(mode="json"),
                    item_type=target_type.key,
                    thinking=result.thinking,
                    checks=result.checks,
                    retried=result.retried,
                )
                if on_accepted is not None:
                    on_accepted(result, i + 1)

        return accepted

    @staticmethod
    def _emit_few_shot(
        few_shot: list[tuple[str, dict]],
        origins: dict[str, str],
        concepts: list[str],
        item_type: ItemType,
    ) -> None:
        """Publish the chosen exemplars to the run feed, without their private keys."""
        progress.emit(
            "few_shot",
            ids=[ex_id for ex_id, _ in few_shot],
            items=[
                {"id": ex_id, "item": _public_fields(item), "origin": origins[ex_id]}
                for ex_id, item in few_shot
            ],
            concepts=concepts,
            item_type=item_type.key,
        )

    @staticmethod
    def _clean_fixed(fixed: dict[str, object] | None) -> dict[str, object]:
        """Drop the pins with no value."""
        return clean_fixed(fixed)

    def _screen_instructions_owners(self, item_type, concepts: list[str]) -> list:
        """Derive the controls that already decide something, for the scope judge."""
        return admissibility.owners(
            self.knowledge_graph,
            item_type,
            self.exemplars_profile,
            self.content_context,
            concepts,
        )

    def _screen_instructions(self, item_type, concepts: list[str], instructions: str):
        """Screen the free text before it is concatenated into the generation prompt.

        The guardrail goes FIRST and the scope judge second, never the other way round:
        the guardrail reads the text alone with a 4096 window, while the scope judge is
        handed the graph's whole concept list, so a text that should reach no model at
        all would otherwise reach the larger of the two. No text, no model call.

        Raises ValueError when either screen blocks the commission.
        """
        if not instructions:
            return admissibility.Ruling(requests=(), checked=True)

        # The raise stays inside the step so a block marks that step failed: a green tick
        # on «revisando» beside a failed job would read as if something else broke.
        with progress.step("guardrail", "Revisando las instrucciones"):
            verdict = guardrail.check(instructions)
            if verdict.blocked:
                raise ValueError(
                    f"Las instrucciones adicionales no han pasado la revisión: se ha detectado {verdict.reason}."
                )

        with progress.step("admissibility", "Revisando el alcance del encargo"):
            ruling = admissibility.screen(
                instructions,
                self._screen_instructions_owners(item_type, concepts),
                concepts,
                self.prompts,
                self.content_context.prompt_block(),
            )
            if not ruling.ok:
                first = ruling.blocked[0]
                raise ValueError(
                    f"«{first.text}» no se pide aquí: lo decide {first.owner.label} "
                    f"(«{first.term}»). {_sentence_case(first.owner.where)}."
                )
        return ruling

    def _validate_input(
        self,
        item_type: ItemType,
        concepts: list[str],
        fixed: dict[str, object],
        n: int,
        curriculum: list[str] | None,
        instructions: str = "",
    ) -> None:
        """Raise ValueError on any commission the instance cannot honour."""
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
        if curriculum:
            known = set(self.knowledge_graph.all_concepts)
            unknown_curriculum = [c for c in curriculum if c not in known]
            if unknown_curriculum:
                raise ValueError(
                    f"Unknown curriculum concepts (not in the knowledge graph): {unknown_curriculum}"
                )
            outside = [c for c in concepts if c not in set(curriculum)]
            if outside:
                raise ValueError(
                    f"Target concepts not contained in curriculum: {outside}"
                )

    def _is_type(self, item: dict, key: str) -> bool:
        """True when the exemplar belongs to this modality.

        An exemplar that declares none counts only where the profile has a single
        modality, there being nothing else it could be.
        """
        declared = item.get(ITEM_TYPE_KEY)
        if declared is None:
            return len(self.exemplars_profile.item_types) == 1
        return declared == key

    def _split_by_target(
        self, item_type: ItemType, target: set[str]
    ) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
        """Split this modality's matching exemplars into primaries and the rest.

        An exemplar whose `primary_concept` is a target PRACTISES it; one that merely
        carries the tag usually only uses it, and a few-shot example has to demonstrate
        the first. Measured over the reference bank, the primary pool is 100 % on-target
        against 78 % for the tag pool.
        """
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
        return primary, secondary

    def _select_few_shot(
        self, item_type: ItemType, concepts: list[str], fixed: dict[str, object]
    ) -> tuple[list[tuple[str, dict]], dict[str, str]]:
        """Choose the exemplars the prompt will show, and say where each one came from.

        Modality is a hard filter and not a preference: an exemplar of another modality
        shows the model the wrong anatomy, and the few-shot block is the strongest signal
        in the prompt. With none of the right type the batch goes zero-shot, which is
        better than teaching it to answer in the wrong shape.
        """
        target = set(concepts)
        primary, secondary = self._split_by_target(item_type, target)

        neighbours: list[tuple[str, dict]] = []
        if len(primary) + len(secondary) < self.max_few_shot:
            neighbours = self._neighbour_exemplars(
                item_type, concepts, {ex_id for ex_id, _ in primary + secondary}
            )

        if not primary and not secondary and not neighbours:
            return [], {}

        origins = {ex_id: "primary" for ex_id, _ in primary}
        origins |= {ex_id: "secondary" for ex_id, _ in secondary}
        origins |= {ex_id: NEIGHBOUR for ex_id, _ in neighbours}
        chosen = self._pick_few_shot(concepts, primary, secondary, neighbours, fixed)
        return chosen, {ex_id: origins[ex_id] for ex_id, _ in chosen}

    def _neighbour_exemplars(
        self, item_type: ItemType, concepts: list[str], taken: set[str]
    ) -> list[tuple[str, dict]]:
        """Return exemplars of the targets' prerequisites, to fill a gap the targets cannot.

        Empty when the instance declares no prerequisite relation, or it is undirected.
        """
        relation = self.prerequisite_relation
        if not relation or not self.knowledge_graph.has_relation(relation):
            return []
        graph = self.knowledge_graph[relation]
        if not graph.is_directed():
            return []
        prior: set[str] = set()
        for concept in concepts:
            if concept in graph:
                prior.update(self.knowledge_graph.neighbors(concept, relation, "out"))
        prior -= set(concepts)
        if not prior:
            return []
        return [
            (ex_id, item)
            for ex_id, item in self.exemplars_bank.items()
            if ex_id not in taken
            and self._is_type(item, item_type.key)
            and item.get("primary_concept") in prior
        ]

    def _pick_few_shot(
        self,
        concepts: list[str],
        primary: list[tuple[str, dict]],
        secondary: list[tuple[str, dict]],
        neighbours: list[tuple[str, dict]],
        fixed: dict[str, object],
    ) -> list[tuple[str, dict]]:
        """Pick up to `max_few_shot` exemplars, primaries first and the rest by similarity.

        The `fixed` filter applies only when at least `max_few_shot` examples survive it:
        below that, more examples beat exact matches. Similarity is the best proxy for
        «closest to what is being asked» among exemplars already off the objective.
        """
        if fixed:

            def pinned(pool: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
                """The pool's exemplars matching every pinned field."""
                return [
                    (ex_id, item)
                    for ex_id, item in pool
                    if all(item.get(k) == v for k, v in fixed.items())
                ]

            if len(pinned(primary)) + len(pinned(secondary)) >= self.max_few_shot:
                primary, secondary = pinned(primary), pinned(secondary)

        if len(primary) >= self.max_few_shot:
            return random.sample(primary, self.max_few_shot)
        if not secondary and not neighbours:
            return primary

        chosen = list(primary)
        for pool in (secondary, neighbours):
            fill = self.max_few_shot - len(chosen)
            if fill <= 0 or not pool:
                continue
            by_id = dict(pool)
            ranked = self.embedder.rank_exemplars(concepts, list(by_id))
            chosen += [(ex_id, by_id[ex_id]) for ex_id in ranked[:fill]]
        return chosen

    def _format_target_concepts(self, concepts: list[str]) -> str:
        """Render the target concepts with their descriptions."""
        descriptions = self.embedder.concept_descriptions
        lines = []
        for c in concepts:
            desc = (descriptions.get(c) or "").strip()
            lines.append(f"- **{c}**: {desc}" if desc else f"- **{c}**")
        return "\n".join(lines)

    def _closure(self, concepts: list[str], forward: bool) -> list[str]:
        """Walk the prerequisite relation, forward to the priors or back to the sequels."""
        relation = self.prerequisite_relation
        if forward:
            return self.knowledge_graph.prerequisite_closure(concepts, relation)
        return self.knowledge_graph.dependent_closure(concepts, relation)

    def _prerequisites(self, concepts: list[str], curriculum: list[str] | None) -> list[str]:
        """The prior knowledge the item may lean on: the closure INTERSECTED with the course."""
        return assumed_known(self._closure(concepts, forward=True), curriculum)

    def _posteriors(self, concepts: list[str], curriculum: list[str] | None) -> list[str]:
        """What is forbidden: the downstream closure MINUS what the course has covered."""
        return forbidden(self._closure(concepts, forward=False), curriculum)

    @staticmethod
    def _format_concept_list(concepts: list[str]) -> str:
        """Render a bare bulleted list of concept names."""
        return "\n".join(f"- {c}" for c in concepts)

    def _format_prerequisites(self, concepts: list[str]) -> str:
        """Render each prerequisite with its description, or with its relations instead.

        A bare name is not prior knowledge the model can reason about.
        """
        descriptions = self.embedder.concept_descriptions
        describer = self.embedder.describer
        lines = []
        for c in concepts:
            text = " ".join((descriptions.get(c) or "").split())
            if not text:
                text = self._relations_sentence(describer.collect_relations(c))
            lines.append(f"- **{c}**: {text}" if text else f"- **{c}**")
        return "\n".join(lines)

    @staticmethod
    def _relations_sentence(relations: dict[str, list[str]]) -> str:
        """Describe an undescribed concept by what the graph says it is related to."""
        parts = [
            f"{verb} {', '.join(neighbors)}" for verb, neighbors in relations.items() if neighbors
        ]
        if not parts:
            return ""
        return "Sin descripción; en el grafo " + "; ".join(parts) + "."

    def _build_item_type_block(self, item_type: ItemType) -> str:
        """Name the modality to produce, and the sibling modalities to stay away from."""
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

    def _build_few_shot_block(
        self, item_type: ItemType, few_shot: list[dict], origins: list[str] | None = None
    ) -> str:
        """Render the few-shot block through the module-level renderer the arms share."""
        return build_few_shot_block(item_type, few_shot, origins)

    def _collect_already_generated(
        self, item_type: ItemType, accepted: list[GeneratedVariant]
    ) -> list[str]:
        """The primary field of every item accepted so far, for the prompt to avoid."""
        out = []
        for r in accepted:
            value = getattr(r.item, item_type.primary_field, None)
            if isinstance(value, str) and value.strip():
                out.append(value)
        return out

    def _build_instance_template(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        """Render the JSON skeleton the model fills in, with the pinned values in place."""
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

    _FIELD_META_KEYS = frozenset(
        {"description", "title", "type", "enum", "guidance", "default", "anyOf", "items", "$ref"}
    )

    def _build_fields_block(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        """Describe every field the model still has to write, with its hand-written guidance.

        A pinned field is left out: `_build_fixed_values_block` states it instead.
        """
        schema = item_type.stripped_schema()
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        guidance = item_type.field_guidance("generation")
        lines = []
        for name, spec in properties.items():
            if name in fixed:
                continue
            facets = [self._field_type(spec)]
            if "enum" in spec:
                facets.append(
                    "uno de: " + " | ".join(json.dumps(v, ensure_ascii=False) for v in spec["enum"])
                )
            facets.extend(
                f"{key}={json.dumps(value, ensure_ascii=False)}"
                for key, value in spec.items()
                if key not in self._FIELD_META_KEYS
            )
            if name not in required:
                facets.append("opcional")
            desc = " ".join((spec.get("description") or "").split())
            line = f"- `{name}` ({', '.join(facets)})"
            if desc:
                line += f": {desc}"
            if name in guidance:
                line += f"\n  Guía anotada a mano para este campo: {guidance[name]}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _field_type(spec: dict) -> str:
        """Name a field's type in the prose the prompt reads."""
        if "type" in spec:
            if spec["type"] == "array":
                inner = (spec.get("items") or {}).get("type")
                return f"lista de {inner}" if inner else "lista"
            return str(spec["type"])
        if "anyOf" in spec:
            return " o ".join(str(v.get("type", "objeto")) for v in spec["anyOf"])
        return "valor"

    def _build_fixed_values_block(self, item_type: ItemType, fixed: dict[str, object]) -> str:
        """State each pinned field and the exact value it must carry."""
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
        self,
        prompt: str,
        fixed: dict[str, object],
        item_type: ItemType,
        think: bool | str = True,
        model: str | None = None,
    ) -> GeneratedVariant | None:
        """Run one generating call and parse an item out of it, or return None.

        The generating call stays unconstrained WHATEVER `think` is: with reasoning on a
        grammar would silence it, and with reasoning off adding one would mean a run
        measures the grammar rather than the reasoning. The schema goes on the repair
        instead, which only reformats text that already carries the whole item.
        """
        resp = inference.generate_stream(
            model=model or self.generator_model,
            prompt=prompt,
            think=think,
            on_token=progress.token_sink("item"),
            temperature=config.TEMPERATURE_GENERATION,
        )

        thinking = resp.thinking
        # A model that forgets to close `<think>` leaves the whole reply on the reasoning
        # side; the answer is still in there, at the end.
        body = resp.response or (thinking or "")

        def parse(text: str) -> tuple[BaseModel | None, str | None]:
            """Parse one reply into an item, stripping any reasoning first."""
            return parse_item(inference.split_thinking(text).response, fixed, item_type)

        item, _ = parse_with_repair(
            body,
            parse,
            repair_model=self.repair_model,
            max_attempts=self.max_repair_attempts,
            shape="objeto",
            format=item_type.stripped_schema(),
            prompts=self.prompts,
        )

        if item is None:
            return None
        return GeneratedVariant(item=item, item_type=item_type.key, thinking=thinking)
