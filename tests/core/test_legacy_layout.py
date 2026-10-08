"""A workspace still laid out the old way is brought up to date the first time it opens.

The artifacts' directory was `instance/` until 2026-10-08 and is `artifacts/` since. Nobody
moves anything by hand: `paths.workspace`, the one door every workspace is opened through,
renames it. Both present is a state only a person can sort out, so nothing is touched.
"""

import json
import threading

import pytest

from variatio.core import paths
from variatio.core.workspace import ARTIFACTS_DIRNAME, LEGACY_ARTIFACTS_DIRNAME


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACES_DIR", tmp_path)
    monkeypatch.setattr(paths, "_ADOPTED", set())
    return tmp_path


def _legacy_tree(root, slug="aula"):
    legacy = root / slug / LEGACY_ARTIFACTS_DIRNAME
    (legacy / ".history").mkdir(parents=True)
    (legacy / "knowledge_graph.json").write_text(json.dumps({"concepts_by_domains": {}}))
    (legacy / ".review_state.json").write_text("{}")
    (legacy / ".history" / "old.json").write_text("{}")
    return legacy


def test_an_old_tree_opens_with_its_files_under_the_new_name(root):
    _legacy_tree(root)

    ws = paths.workspace("aula")

    assert ws.artifacts_dir == root / "aula" / ARTIFACTS_DIRNAME
    assert ws.kg_path.is_file()
    assert ws.review_state_path.is_file()
    assert (ws.history_dir / "old.json").is_file()
    assert not (root / "aula" / LEGACY_ARTIFACTS_DIRNAME).exists()


def test_a_tree_with_both_names_is_left_alone(root):
    _legacy_tree(root)
    (root / "aula" / ARTIFACTS_DIRNAME).mkdir()

    ws = paths.workspace("aula")

    assert (root / "aula" / LEGACY_ARTIFACTS_DIRNAME / "knowledge_graph.json").is_file()
    assert not ws.kg_path.exists()


def test_a_new_tree_and_one_already_renamed_are_not_touched(root):
    (root / "nueva").mkdir()
    (root / "hecha" / ARTIFACTS_DIRNAME).mkdir(parents=True)

    assert paths.workspace("nueva").artifacts_dir == root / "nueva" / ARTIFACTS_DIRNAME
    assert not (root / "nueva" / ARTIFACTS_DIRNAME).exists()
    assert paths.workspace("hecha").artifacts_dir.is_dir()


def test_two_threads_opening_one_old_tree_at_once_both_succeed(root):
    _legacy_tree(root)
    errors: list[BaseException] = []
    start = threading.Barrier(4)

    def open_it():
        try:
            start.wait()
            paths.adopt_legacy_layout(root / "aula")
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [threading.Thread(target=open_it) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert (root / "aula" / ARTIFACTS_DIRNAME / "knowledge_graph.json").is_file()
