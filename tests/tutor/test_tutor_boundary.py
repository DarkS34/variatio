"""`tutor` imports `variatio` and never the reverse, and `import tutor` stays a library.

Pinned as the evaluation's boundary was: the registry's optional import of `tutor.settings`
is the one place `variatio` names the tutor, and nothing outside `tutor.api` may pull in the
web framework or the database.
"""

import inspect
import re
import subprocess
import sys
from pathlib import Path

from tutor import prompts
from tutor import settings as tutor_settings
from variatio.settings.registry import BY_KEY, EXTRA_MODEL_KEYS, PIPELINE, STAGES

ROOT = Path(__file__).resolve().parents[2]


def test_variatio_names_the_tutor_only_in_the_registry():
    naming = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "variatio").rglob("*.py")
        if re.search(r"^\s*(from|import) tutor\b", path.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert naming == ["variatio/settings/registry/__init__.py"]


def test_importing_the_tutor_does_not_import_the_server_stack():
    code = (
        "import sys, tutor, tutor.turn, tutor.criteria_builder;"
        "print(sorted(m for m in ('fastapi', 'sqlalchemy', 'tutor.api') if m in sys.modules))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_the_tutor_is_the_last_stage_and_its_lane_is_drawn():
    assert STAGES[-1] == tutor_settings.STAGE
    assert PIPELINE[-1] == tutor_settings.LANE
    assert set(EXTRA_MODEL_KEYS) == set(tutor_settings.MODEL_KEYS)


def test_every_pipeline_setting_a_turn_reads_exists_and_carries_the_tutor_s_stage():
    for key in tutor_settings.READS:
        assert key in BY_KEY, key
        assert tutor_settings.STAGE in BY_KEY[key].stages, key


def test_both_prompt_sets_have_the_same_names_and_signatures():
    es, en = prompts.of("es"), prompts.of("en")
    public = lambda module: {  # noqa: E731
        name: inspect.signature(value) if callable(value) else type(value)
        for name, value in vars(module).items()
        if not name.startswith("_") and name not in ("json",)
    }
    assert public(es) == public(en)
    assert len(es.FIXED_RULES) == len(en.FIXED_RULES)


def test_every_tutor_switch_is_a_bool_with_its_effort_drawn_under_its_call():
    for phase in tutor_settings.LANE.phases:
        if phase.setting is None:
            assert phase.fixed is not None and phase.effort is None, phase.key
            continue
        switch, effort = BY_KEY[phase.setting], BY_KEY[phase.effort]
        assert switch.kind == "bool" and switch.scope == "engine" and not switch.name
        assert effort.choices == ("low", "medium", "high", "max") and effort.default == "low"
        assert switch.phase == effort.phase == phase.key
        assert BY_KEY[phase.model].phase == phase.key
