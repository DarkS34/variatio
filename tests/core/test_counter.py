"""A counter spans loops of its own: nested work advances it one unit at a time."""

from variatio.core import progress

from .test_step_start import _progress, _Recorder


def test_nested_work_advances_the_enclosing_counter():
    recorder = _Recorder()
    with progress.emitting(recorder), progress.counter("pages", "x", 5):
        for document in ("a", "b"):
            with progress.step("document", document, 2):
                progress.count()
                progress.count()
    counted = [p["current"] for p in _progress(recorder) if p["id"] == "pages"]
    assert counted == [1, 2, 3, 4]


def test_count_outside_a_counter_is_a_no_op():
    recorder = _Recorder()
    with progress.emitting(recorder):
        progress.count()
    assert recorder.events == []
