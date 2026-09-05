"""The CLI's `transcribe` subcommand: which slots it reads, and what it refuses to become."""

import pytest

from variatio import cli, stages


@pytest.fixture
def read(monkeypatch):
    """Record what the subcommand asks the stage for, without transcribing anything."""
    seen: list[str] = []
    monkeypatch.setattr(cli.inference, "require_engine", lambda: seen.append("engine"))

    def transcribe_slot(ws, slot, failed=0):
        seen.append(slot)
        return {"failed_pages": failed}

    monkeypatch.setattr(stages, "transcribe_slot", transcribe_slot)
    return seen


def test_it_reads_both_origins_by_default(read):
    assert cli.main(["transcribe", "--workspace", "w"]) == 0
    assert read == ["engine", *stages.SLOTS]


def test_one_origin_can_be_asked_for_alone(read):
    assert cli.main(["transcribe", "--workspace", "w", "--slot", "corpus"]) == 0
    assert read[1:] == [stages.CORPUS]


def test_it_demands_a_live_engine(monkeypatch):
    """It calls the model page by page, so it is not in `restamp-descriptions`' exception."""

    def down():
        raise RuntimeError("engine is down")

    monkeypatch.setattr(cli.inference, "require_engine", down)
    monkeypatch.setattr(stages, "transcribe_slot", lambda ws, slot: pytest.fail("no engine"))
    assert cli.main(["transcribe", "--workspace", "w"]) == 1


def test_a_page_nobody_could_read_is_a_warning_and_not_a_failure(monkeypatch):
    """A failed page is marked inside its document and corrected by hand; the run stands."""
    monkeypatch.setattr(cli.inference, "require_engine", lambda: None)
    monkeypatch.setattr(stages, "transcribe_slot", lambda ws, slot: {"failed_pages": 3})
    assert cli.main(["transcribe", "--workspace", "w"]) == 0
