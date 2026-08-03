"""Process-wide singletons: one bus, one queue, one review state."""

from .jobs import HANDLERS, EventBus, JobRunner
from .review import ReviewState

bus = EventBus()
runner = JobRunner(bus, HANDLERS)
review_state = ReviewState()


def building() -> set[str]:
    return runner.building_artifacts()


def pipeline_snapshot() -> list[dict]:
    return review_state.snapshot(building())
