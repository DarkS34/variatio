from variatio import settings
from variatio.settings.registry import BY_KEY, PIPELINE, REGISTRY, STAGES
from variatio.settings.types import STAGES as PIPELINE_STAGES

# What belongs to the engine or the process and not to a stage: drawn in «Administración →
# Motor», or not drawn at all.
STAGELESS_GROUPS = {"Motor", "Túnel SSH", "Registro"}

LANE_OF = {phase.key: lane.key for lane in PIPELINE for phase in lane.phases}


def test_every_lane_is_a_stage_and_in_the_stages_order():
    assert [lane.key for lane in PIPELINE] == list(STAGES)


def test_the_pipeline_stages_lead_and_keep_their_order():
    assert STAGES[: len(PIPELINE_STAGES)] == PIPELINE_STAGES


def test_every_setting_outside_the_engine_names_a_stage():
    missing = [
        setting.key
        for setting in REGISTRY
        if setting.group not in STAGELESS_GROUPS and not setting.stages
    ]
    assert not missing, f"sin etapa: {missing}"


def test_the_engine_and_the_process_belong_to_no_stage():
    staged = [
        setting.key for setting in REGISTRY if setting.group in STAGELESS_GROUPS and setting.stages
    ]
    assert not staged, f"del motor y con etapa: {staged}"


def test_every_declared_stage_exists():
    unknown = {
        setting.key: setting.stages for setting in REGISTRY if set(setting.stages) - set(STAGES)
    }
    assert not unknown, unknown


def test_a_setting_s_phase_is_a_call_of_its_own_stage():
    wrong = {
        setting.key: (setting.phase, setting.stages[0])
        for setting in REGISTRY
        if setting.phase is not None and LANE_OF.get(setting.phase) != setting.stages[0]
    }
    assert not wrong, wrong


def test_a_phase_s_own_settings_are_drawn_under_it():
    for lane in PIPELINE:
        for phase in lane.phases:
            for key in (phase.setting, phase.effort):
                if key is None:
                    continue
                assert BY_KEY[key].phase == phase.key, key
                assert BY_KEY[key].stages[0] == lane.key, key
            if phase.model == f"models.phases.{phase.key}":
                assert BY_KEY[phase.model].phase == phase.key, phase.model


def test_a_call_made_by_several_stages_carries_them_all():
    # The tagger runs inside the bank build and again in every generation's checks; the
    # repair answers whoever's JSON came back broken.
    assert set(BY_KEY["models.phases.concept_tagger"].stages) >= {"bank", "generation"}
    assert set(BY_KEY["models.phases.repair"].stages) >= {"profile", "graph", "bank", "generation"}


def test_the_snapshot_carries_stages_and_phase():
    rows = {row["key"]: row for row in settings.snapshot()}
    assert rows["builders.transcribe_max_output_tokens"]["stages"] == ["transcription"]
    assert rows["builders.transcribe_max_output_tokens"]["phase"] == "transcribe"
    assert rows["engine.name"]["stages"] == []
    assert rows["engine.name"]["phase"] is None
