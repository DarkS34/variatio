import pytest

from server import settings
from variatio.core import paths
from variatio.core.workspace import Workspace


@pytest.mark.parametrize(
    "slug, valid",
    [
        ("aula", True),
        ("aula-2026", True),
        ("aula\n", False),
        ("aula\r", False),
        ("aula\n\n", False),
        ("Aula", False),
        ("..", False),
        ("a/b", False),
        ("-aula", False),
    ],
)
def test_slug_pattern_rejects_a_trailing_newline(slug, valid):
    assert (settings.slug_error(slug) is None) is valid


# `paths.workspace` strips, so a slug the pattern let through with a trailing newline
# resolved to the SAME directory as its clean twin: two rows, one tree.
def test_a_stripped_slug_no_longer_reaches_the_same_directory_as_its_twin():
    assert settings.slug_error("aula") is None
    assert settings.slug_error("aula\n") is not None
    assert paths.workspace("aula").root == paths.workspace("aula\n").root


def _outside(tmp_path) -> Workspace:
    return Workspace(root=tmp_path / "fuera", slug="fuera")


def test_destroy_refuses_a_root_outside_the_workspaces_directory(tmp_path):
    ws = _outside(tmp_path)
    ws.root.mkdir(parents=True)
    with pytest.raises(ValueError):
        settings.destroy(ws)
    assert ws.root.is_dir()


def test_clear_cache_refuses_a_root_outside_the_workspaces_directory(tmp_path):
    ws = _outside(tmp_path)
    target = ws.cache_dir / "embeddings"
    target.mkdir(parents=True)
    (target / "vectores.npz").write_bytes(b"x")
    with pytest.raises(ValueError):
        settings.clear_cache(ws)
    assert (target / "vectores.npz").exists()
