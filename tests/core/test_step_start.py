"""The two bars of a build count the unit in flight the same way: as not done."""

from variatio.core import progress


class _Recorder:
    """An emitter that keeps every event it is handed."""

    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))

    def should_cancel(self):
        return False


def _progress(recorder):
    return [p for k, p in recorder.events if k == "step.progress"]


def test_start_reports_the_units_before_the_one_in_flight():
    recorder = _Recorder()
    with progress.emitting(recorder):
        with progress.step("loop", "x", 3) as reporter:
            for index in range(1, 4):
                reporter.start(index, detail=f"unit {index}")
    assert [p["current"] for p in _progress(recorder)] == [0, 1, 2]
    assert [p["detail"] for p in _progress(recorder)] == ["unit 1", "unit 2", "unit 3"]


def test_start_agrees_with_the_phase_bar_on_the_first_unit():
    """Before the first unit is done, both bars read zero."""
    recorder = _Recorder()
    plan = (("only", "Only", 1),)
    with progress.emitting(recorder), progress.overall(plan):
        progress.phase("only")
        with progress.step("loop", "x", 4) as reporter:
            reporter.start(1)
            progress.advance(0 / 4)
    steps = _progress(recorder)
    builds = [p for k, p in recorder.events if k == "build.progress" and p["key"] == "only"]
    assert steps[-1]["current"] == 0
    assert builds[-1]["percent"] == 0


def test_start_never_goes_below_zero_and_tick_still_counts_done():
    recorder = _Recorder()
    with progress.emitting(recorder):
        with progress.step("loop", "x", 2) as reporter:
            reporter.start(0)
            reporter.tick(2)
    assert [p["current"] for p in _progress(recorder)] == [0, 2]
