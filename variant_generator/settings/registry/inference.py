from ..types import Impact, Setting

_IDLE_DOC = """Cuánto puede estar el servidor sin ejecutar un solo trabajo antes de soltar la GPU
(`inference.unload_all()`, que es `ollama stop` de cada modelo residente).

`OLLAMA_KEEP_ALIVE=24h` es lo que mantiene los tres modelos calientes durante una sesión
de trabajo, y eso es lo que se quiere mientras se está trabajando: los 29 GiB residentes
no se pagan dos veces. Lo que no tiene sentido es que sigan ahí toda la noche porque
alguien dejó la pestaña abierta, en una tarjeta que es de todos.

30 minutos porque es la escala de la pausa que NO es una pausa de trabajo: entre dos
etapas de la cadena pasan minutos, no media hora, así que a este umbral no se llega
revisando un grafo — se llega habiéndose ido. Recargar los tres modelos cuesta ~30 s, que
es ruido al lado de cualquier construcción y de sobra tolerable en una generación suelta.
0 lo desactiva."""

_MODELS_MAIN_DOC = """ONE generative model, since 2026-08-17: the three tiers did not fit together on the A40
(~45 GiB) and were evicting each other all day, and `gemma4:e4b-it-q8_0` (10.1 GiB) did not
fit alongside a 30B-class one either, which made every JSON repair inside the extraction
loop cost TWO ~10 s loads. That decision stands; only WHICH model changed.

What stays resident is three models that DO fit at once — measured at 29.05 GiB of ~45 with
the context sizes below — so nothing evicts anything: this one, the guardrail and the
embedder. There is 16 GiB of headroom now, where the previous MoE left 3.5.

The standing measurement against a 30B-class MoE was taggability: over the reference
draft's largest domain (73 non-taggables) `gemma4:31b` returned 75 and `qwen3.6:35b-a3b`
66, i.e. the MoE under-excludes, the direction `review_taggable_concepts_prompt` legislates
against. `qwen3.8:27b` is dense and reasons, so it is expected to do better here — but that
is a PREDICTION, not a measurement, and it is the first thing to re-check on a real build.

`qwen3.8:27b-q4_K_M` since 2026-08-18, replacing `qwen3.6:35b-a3b-q8_0` and reversing the
2026-08-16 revert, by explicit user request. What reopened the question is that Ollama can
now cap how much a reasoning model deliberates: `think` takes an EFFORT LEVEL, not just a
boolean, and `THINK_EFFORT` below pins every reasoning call to the cheapest one.

The revert's reasons were real and are only PARTLY answered, so the numbers are here in
full. All of them on the A40, on the same call — `link_domain_relations_prompt` over the
reference draft's largest domain, 43 concepts, 5 441 characters, temperature 0:

  qwen3.6:35b-a3b-q8_0  think=true    128 s   37 264 car. de razonamiento   92.0 tok/s
  qwen3.8:27b-q4_K_M    think="low"   443 s   40 894                        29.1 tok/s
  qwen3.8:27b-q8_0      think="low"   649 s   38 796                        19.0 tok/s
  qwen3.8:27b-q8_0      think="high"  777 s   58 953        RESPUESTA VACÍA 19.2 tok/s

Three things to read off that table before touching any of this:

1. THE EFFORT LEVEL DOES NOT REDUCE THE DELIBERATION MUCH. `low` still emits ~41 000
   characters, i.e. about what the old MoE emitted with a plain `think=true`. What the
   level moves is the CEILING (58 953 at `high`), not the floor. Anyone hoping to make
   this model cheap by lowering the effort further will find there is nothing below `low`
   except `think=False`, which turns reasoning off altogether.
2. THE COST IS THE DENSE DECODE, and it is the price of this decision: 29.1 tok/s against
   the MoE's 92.0, so a curation call goes 128 s → 443 s and a build lengthens ~3.5x.
   Accepted knowingly on 2026-08-18.
3. THE QUANTISATION IS NOT INTERCHANGEABLE HERE. The q4_K_M is 53 % faster than the q8_0
   (29.1 vs 19.0 tok/s) and 16.5 GB against 27.9, and it obeys the effort level exactly
   the same — measured, not assumed, in the token table under `THINK_EFFORT`. Unlike
   `qwen3.6:35b-a3b-q4_K_M`, which is broken on this box above ~4 490 characters, this q4
   answered the 5 441-character prompt with valid JSON. Do not "upgrade" it to the q8."""

_THINK_EFFORT_DOC = """HOW HARD A REASONING CALL THINKS. `think` stays a BOOLEAN everywhere above this line —
at the call sites, in the study's `Commission`, in the `generations.think` column and in
the UI switch — and `inference` translates the `True` into this level at the very last
hop. That split is the decision of 2026-08-18: the effort is a property of the engine, not
a second axis for a call site or an evaluator to choose, and making it one would have
meant a migration plus a study whose older sessions sat on a different scale.

`low` and not something higher, measured on the A40 with `/api/generate`:

    modelo                prompt_eval_count con think = true / low / medium / high
    qwen3.8:27b-q4_K_M                          15 /  45 /  15 /  57
    qwen3.8:27b-q8_0                            15 /  45 /  15 /  57
    qwen3.6:35b-a3b-q8_0                        15 /  15 /  15 /  15

Read it in three parts. `medium` IS the default — same token count as `true`, so it is not
a rung, it is the absence of one. `high` costs 58 953 characters of deliberation on the
real curation prompt and came back with an EMPTY response, which is the failure this
model was reverted for in the first place. And the old MoE ignored the parameter outright:
all four values produced a byte-identical answer, so the level is implemented per model by
Ollama's renderer and CANNOT be assumed to exist — which is exactly why it is one constant
here and not thirteen strings spread over the call sites.

Ollama 0.32.13 accepts `high`, `medium`, `low`, `max`, `true`, `false` and 400s on anything
else. `xhigh` does NOT exist. `max` is deliberately unused: it over-reasons."""

_TEMPERATURE_DOC = """HOW FAR THE SAMPLER MAY WANDER. Ollama's own default is 0.8, and a handful of Modelfiles
declare 1.0 — a WRITING temperature, applied indiscriminately to calls that are not writing
anything: reading the concepts out of a chunk, deciding whether two names are the same
concept, answering yes/no. Left at that default those calls redraw a different graph from
the same corpus on every build, and the difference between two runs is not evidence of
anything. Every generative call in the project now names one of these three.

1. DETERMINISTIC — the answer is a reading of the input and there is one right one:
   extraction, the domain names and their assignment, the bank and profile scans, the
   guardrail's verdict, the concept descriptions that get embedded and cached. Greedy, so a
   rebuild is a rebuild and not a redraw. What makes 0 safe at every one of these sites and
   not at the ones below is that they are all `think=False` AND grammar-constrained: the
   answer starts at `{` and the schema bounds how long it can go on for.
2. REASONING — the `think=True` judgements over an inventory that is already fixed: merging
   aliases, dropping what does not name a concept, ordering prerequisites, taggability.
   Deliberately NOT 0, and it is the one value here chosen against determinism. Greedy
   decoding inside a reasoning channel is where deliberation degenerates into a repetition
   loop, and it degenerates SILENTLY on this stack — `KG_DOMAINS_MODEL` records one call
   that reasoned for 36 929 characters, hit its stop token and returned an empty response
   that nothing upstream could tell from a real answer. This is enough entropy to leave
   such a loop and far below the 0.6 the model card suggests for open-ended thinking,
   because none of these calls is open-ended: the inventory they judge is closed.
3. GENERATION — the end of the pipeline, and the only call in the project that is genuinely
   writing. It stays low all the same, because what makes a variant worth keeping is that
   it obeys its commission — the target concepts, the pinned fields, the curriculum, the
   instructions — and temperature is exactly what buys drift away from all four. The
   variety between the `n` items of one run is paid for in the PROMPT, which shows the
   model the statements it has already written, and in the random few-shot sample; it is
   not the sampler's job here."""

_TEMPERATURE_REPAIR_DOC = """Its own constant although it happens to equal the reasoning one, because it is not there
for the same reason and would not move with it: repair is a RETRY loop, and a retry at 0 is
not a retry. Attempt N+1's prompt is attempt N's output, so a model that hands back what it
was given rebuilds the identical prompt and, greedy, writes the identical answer — the
whole budget spent on one byte-identical reply, which is the failure `parse_with_repair`
already documents having paid for once."""

_CONTEXT_WINDOW_DOC = """These are what make the three models co-resident, so they are not free to grow: measured
on the A40 through `/api/ps`, `LLM_MAIN` at 65536 + guardrail + embedder come to 29.05 GiB
of ~45 (19.49 + 5.49 + 4.07). The guardrail's used to be 8192, which cost 1 GiB of KV cache
and pushed the old total to 45.17 — just over, and the symptom was that screening one
commission evicted the embedder. It only ever reads `GENERATION_INSTRUCTIONS_MAX_CHARS`
(600 characters, ~200 tokens), so 4096 is still a tenfold margin.

`LLM_MAIN`'s doubled from 32768 on 2026-08-18, with the move to a reasoning model. The rule
changed underneath it: with `think` on, the window is no longer sized by the PROMPT but by
prompt + deliberation, and the deliberation is the big half — the largest prompt in the
pipeline is ~8 000 tokens while one `low` curation call spends ~13 000 on reasoning alone.
The headroom freed by the lighter q4 is what pays for it, so it costs nothing to hold.

What it does NOT fix, measured, is the empty answer `curate_graph_domains_prompt` gave
while it still asked for the whole partition: over 203 concepts that call returned
`response == ""` at 32768 AND at 65536, byte for byte the same (36 929 characters of
reasoning, 11 611 tokens — about 13 200 in total, a fifth of the smaller window). The
window was never the constraint there; see `KG_DOMAINS_MODEL`.

Lowering this truncates silently, as always — and now it truncates the reasoning first, so
the symptom is an empty or half-written answer rather than a missing tail of prompt."""

_EXEMPLARS_TRANSCRIBE_DOC = """Raw exemplars transcription — shared by BOTH builders that read raw_exemplars_bank/,
so there is one constant and not two that could drift and produce two different
markdowns for the same file.

What carries fidelity here is the PROMPT, not the model. Measured on Prog1_PEC1 p.1:
without the character-by-character clause of `transcribe_page_prompt`, gemma4:31b
rewrote `a -= 1` as `a = a - 1`, invented `8 - (n-i)` for `(n-i)`, and turned
`x = x - 1` into `x = x + 1` — which inverts the answer to the very question being
transcribed. With the clause, both 30B-class models come back faithful. Weakening that
instruction silently reintroduces corrupt code into the bank.

The fidelity comparison behind that (accents and a docstring's line break kept where
gemma4:31b lost both, 20s against 31s a page) was measured on `qwen3.6:35b-a3b-q8_0`,
which no longer holds this job — it followed `LLM_MAIN` into `qwen3.8:27b-q4_K_M` on
2026-08-18. The new model has the `vision` capability, checked, so the call works; whether
it transcribes as faithfully is NOT measured yet. This is the cheapest thing in the
pipeline to re-check (one page) and the most damaging to get wrong, since a corrupted
transcription lands in the bank as an exercise whose answer has changed."""

_PHASE_SHARED_DOC = """One constant per model call is still the unit of retuning, and that is the whole reason
they survive a consolidation: pointing them all at `LLM_MAIN` is a decision, not a
collapse, and any single phase can be moved off it without touching the other twelve."""

_KG_DOMAINS_DOC = """The one phase whose call had to give up reasoning outright when `LLM_MAIN` became a
reasoning model: asked to partition the whole inventory it answered inside the reasoning
channel and returned nothing. It only names the domains now — `assign_round` places the
concepts, batch by batch — and both calls stay constrained by a grammar and therefore
without thinking. The measurement is at the call site, in
`knowledge_graph_builder/curation.py:curate_domains`. It is not the model that was wrong
here, so this still points at `LLM_MAIN`; it was the thinking."""

_REPAIR_DOC = """Repair is the one call that fires from INSIDE a per-element loop, so it is also the one
that must never be a model of its own: a separate small model does not fit next to
`LLM_MAIN` on this box, and each repair would evict it and pay two ~10 s loads in the
middle of a corpus. Whatever else moves off `LLM_MAIN`, this follows it."""

_VACIO_SENTINEL = "Vacío significa que sigue al modelo principal."


def _phase_doc(sentence: str) -> str:
    return _PHASE_SHARED_DOC + "\n\n" + sentence + "\n\n" + _VACIO_SENTINEL


SETTINGS: list[Setting] = [
    Setting(
        key="engine.name",
        name="INFERENCE_ENGINE",
        kind="str",
        default="ollama",
        group="Motor",
        impact=Impact.ENGINE,
        choices=("ollama",),
        doc="""Qué implementación de motor de inferencia respalda generate()/embed()/embed_batch().
Solo 'ollama' está implementado; `config.INFERENCE_ENGINE` lo selecciona y la lógica de
negocio nunca llama a un SDK directamente — todo pasa por `variant_generator.core.inference`.""",
    ),
    Setting(
        key="engine.ollama_host",
        name="OLLAMA_HOST",
        kind="str",
        default="localhost:13434",
        group="Motor",
        impact=Impact.ENGINE,
        env="OLLAMA_HOST",
        doc="""El host de Ollama como `host:puerto` (o una URL `http(s)://` completa). `config.py` lo
lee de la variable de entorno `OLLAMA_HOST` y normaliza un `host:puerto` desnudo
anteponiéndole `http://`; el registro guarda el valor desnudo y ese prefijo se añade en
otro sitio, no aquí.""",
    ),
    Setting(
        key="engine.idle_unload_seconds",
        name="IDLE_UNLOAD_SECONDS",
        kind="int",
        default=1800,
        group="Motor",
        impact=Impact.NONE,
        env="VG_IDLE_UNLOAD_SECONDS",
        minimum=0,
        doc=_IDLE_DOC,
    ),
    Setting(
        key="engine.idle_unload_poll_seconds",
        name="IDLE_UNLOAD_POLL_SECONDS",
        kind="int",
        default=60,
        group="Motor",
        impact=Impact.NONE,
        minimum=1,
        doc=_IDLE_DOC,
    ),
    Setting(
        key="models.main",
        name="LLM_MAIN",
        kind="str",
        default="qwen3.8:27b-q4_K_M",
        group="Modelos",
        impact=Impact.CONTEXTS,
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="models.guardrail",
        name="GUARDRAIL_LLM",
        kind="str",
        default="granite4.1-guardian:8b-q4_K_M",
        group="Modelos",
        impact=Impact.CONTEXTS,
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="models.embedding",
        name="EMBEDDING_LLM",
        kind="str",
        default="qwen3-embedding:4b",
        group="Modelos",
        impact=Impact.REINDEX,
        doc=_MODELS_MAIN_DOC,
    ),
    Setting(
        key="sampling.think_effort",
        name="THINK_EFFORT",
        kind="str",
        default="low",
        group="Muestreo",
        impact=Impact.NONE,
        choices=("low", "medium", "high", "max"),
        doc=_THINK_EFFORT_DOC,
    ),
    Setting(
        key="sampling.temperature_deterministic",
        name="TEMPERATURE_DETERMINISTIC",
        kind="float",
        default=0.0,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_reasoning",
        name="TEMPERATURE_REASONING",
        kind="float",
        default=0.2,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_generation",
        name="TEMPERATURE_GENERATION",
        kind="float",
        default=0.3,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_DOC,
    ),
    Setting(
        key="sampling.temperature_repair",
        name="TEMPERATURE_REPAIR",
        kind="float",
        default=0.2,
        group="Muestreo",
        impact=Impact.NONE,
        minimum=0.0,
        maximum=2.0,
        doc=_TEMPERATURE_REPAIR_DOC,
    ),
    Setting(
        key="context_window.main",
        name="",
        kind="int",
        default=65536,
        group="Ventana de contexto",
        impact=Impact.CONTEXTS,
        minimum=2048,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="context_window.guardrail",
        name="",
        kind="int",
        default=4096,
        group="Ventana de contexto",
        impact=Impact.CONTEXTS,
        minimum=2048,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="context_window.embedding",
        name="",
        kind="int",
        default=4096,
        group="Ventana de contexto",
        impact=Impact.REINDEX,
        minimum=512,
        doc=_CONTEXT_WINDOW_DOC,
    ),
    Setting(
        key="models.phases.exemplars_transcribe",
        name="EXEMPLARS_TRANSCRIBE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_EXEMPLARS_TRANSCRIBE_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
    Setting(
        key="models.phases.ep_scan",
        name="EP_SCAN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de escaneo del generador de perfil de ejemplares (exemplars_profile_builder)."
        ),
    ),
    Setting(
        key="models.phases.ep_consolidate",
        name="EP_CONSOLIDATE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de consolidación del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.ep_context",
        name="EP_CONTEXT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de contexto del generador de perfil de ejemplares."),
    ),
    Setting(
        key="models.phases.eb_extract",
        name="EB_EXTRACT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de extracción del generador del banco de ejemplares."),
    ),
    Setting(
        key="models.phases.kg_extract",
        name="KG_EXTRACT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de extracción del constructor del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_merge",
        name="KG_CLEAN_MERGE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de fusión de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_clean_drop",
        name="KG_CLEAN_DROP_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc("Fase de descarte de la limpieza del grafo de conocimiento."),
    ),
    Setting(
        key="models.phases.kg_domains",
        name="KG_DOMAINS_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_KG_DOMAINS_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
    Setting(
        key="models.phases.kg_domains_leftovers",
        name="KG_DOMAINS_LEFTOVERS_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de colocación de los conceptos sobrantes de la asignación de dominios "
            "del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_domain",
        name="KG_LINK_DOMAIN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de enlace de relaciones dentro de un mismo dominio del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_link_cross_domain",
        name="KG_LINK_CROSS_DOMAIN_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de enlace de relaciones entre dominios distintos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_taggable",
        name="KG_TAGGABLE_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de revisión de etiquetabilidad de los conceptos del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.kg_context",
        name="KG_CONTEXT_MODEL",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de síntesis del contexto de la materia a partir del grafo de conocimiento."
        ),
    ),
    Setting(
        key="models.phases.description_generation",
        name="DESCRIPTION_GENERATION_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de generación de descripciones de conceptos, en el pipeline en tiempo de "
            "ejecución (no en un build)."
        ),
    ),
    Setting(
        key="models.phases.concept_tagger",
        name="CONCEPT_TAGGER_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de etiquetado de conceptos sobre el banco de ejemplares, en el pipeline en "
            "tiempo de ejecución."
        ),
    ),
    Setting(
        key="models.phases.variant_generation",
        name="VARIANT_GENERATION_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_phase_doc(
            "Fase de generación de variantes de contenido, en el pipeline en tiempo de "
            "ejecución."
        ),
    ),
    Setting(
        key="models.phases.repair",
        name="REPAIR_LLM",
        kind="str",
        default=None,
        group="Modelos",
        impact=Impact.CONTEXTS,
        nullable=True,
        doc=_REPAIR_DOC + "\n\n" + _VACIO_SENTINEL,
    ),
]
