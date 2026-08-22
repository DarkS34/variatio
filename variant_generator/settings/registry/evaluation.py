from ..types import Impact, Setting

SETTINGS: list[Setting] = [
    Setting(
        key="evaluation.providers",
        name="EVAL_EXTERNAL_PROVIDERS",
        kind="list[str]",
        default=["gemini", "groq"],
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_EXTERNAL_PROVIDER",
        doc="""Only the Evaluation mode reads this block; the pipeline never imports `evaluation/`.

The `*_MODEL_ID` names deliberately end in neither `_MODEL` nor `_LLM`:
`inference.required_models()` collects both suffixes by introspection and `/api/health`
demands them from Ollama, so either name would surface in the UI as a model that is
never installed — these are served by an external provider and never pulled.

`EVAL_EXTERNAL_PROVIDER` is a CHAIN in preference order, not a single name. The free tiers
this arm runs on answer 429 halfway through a data-collection session, and a provider that
stops answering hands over to the next one instead of costing the session its commercial
proposal. Each provider brings its own key and its own model id, so the two can never be
crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible. `none` (or an
empty value) disables the arm.

The keys come from the environment (or the gitignored `.env`) and default to empty: with
no key at all the naive arm records itself `unavailable` and the session runs with two.""",
    ),
    Setting(
        key="evaluation.models.gemini",
        name="",
        kind="str",
        default="gemini-3.6-flash",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GEMINI_MODEL_ID",
        doc="""The `*_MODEL_ID` names deliberately end in neither `_MODEL` nor `_LLM`:
`inference.required_models()` collects both suffixes by introspection and `/api/health`
demands them from Ollama, so either name would surface in the UI as a model that is
never installed — these are served by an external provider and never pulled.

Each provider brings its own key and its own model id, so the two can never be
crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible.""",
    ),
    Setting(
        key="evaluation.models.groq",
        name="",
        kind="str",
        default="llama-3.3-70b-versatile",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GROQ_MODEL_ID",
        doc="""The `*_MODEL_ID` names deliberately end in neither `_MODEL` nor `_LLM`:
`inference.required_models()` collects both suffixes by introspection and `/api/health`
demands them from Ollama, so either name would surface in the UI as a model that is
never installed — these are served by an external provider and never pulled.

Each provider brings its own key and its own model id, so the two can never be
crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible.""",
    ),
    Setting(
        key="evaluation.keys.gemini",
        name="",
        kind="str",
        default="",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GEMINI_API_KEY",
        secret=True,
        editable=False,
        doc="""Each provider brings its own key and its own model id, so the two can never be
crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible. `none` (or an
empty value) disables the arm.

The keys come from the environment (or the gitignored `.env`) and default to empty: with
no key at all the naive arm records itself `unavailable` and the session runs with two.

They are never serialised into `config.json` and never leave the API — they live only in
the gitignored `.env`.""",
    ),
    Setting(
        key="evaluation.keys.groq",
        name="",
        kind="str",
        default="",
        group="Evaluación",
        impact=Impact.NONE,
        env="EVAL_GROQ_API_KEY",
        secret=True,
        editable=False,
        doc="""Each provider brings its own key and its own model id, so the two can never be
crossed — which is what the single `EVAL_EXTERNAL_API_KEY` made impossible. `none` (or an
empty value) disables the arm.

The keys come from the environment (or the gitignored `.env`) and default to empty: with
no key at all the naive arm records itself `unavailable` and the session runs with two.

They are never serialised into `config.json` and never leave the API — they live only in
the gitignored `.env`.""",
    ),
    Setting(
        key="evaluation.timeout",
        name="EVAL_EXTERNAL_TIMEOUT",
        kind="float",
        default=60.0,
        group="Evaluación",
        impact=Impact.NONE,
        minimum=1.0,
        doc="""Per attempt, so a chain of two waits for this twice in the worst case. The arm runs on
a thread alongside the two local ones, which take minutes, so it is not the wall clock.""",
    ),
]
