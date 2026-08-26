import os
from pathlib import Path

from variatio.core import paths
from variatio.core.dotenv import load_dotenv


def test_load_dotenv_does_not_override_a_real_export(tmp_path, monkeypatch):
    monkeypatch.setenv("VARIATIO_TEST_KEY", "del entorno")
    env = tmp_path / ".env"
    env.write_text('VARIATIO_TEST_KEY="del fichero"\nVARIATIO_TEST_OTHER=libre\n', encoding="utf-8")

    load_dotenv(env)

    assert os.environ["VARIATIO_TEST_KEY"] == "del entorno"
    assert os.environ["VARIATIO_TEST_OTHER"] == "libre"


def test_load_dotenv_ignores_comments_and_blanks(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comentario\n\nVARIATIO_TEST_THIRD=3\nsin_igual\n", encoding="utf-8")

    load_dotenv(env)

    assert os.environ["VARIATIO_TEST_THIRD"] == "3"


def test_load_dotenv_on_a_missing_file_is_silent(tmp_path):
    load_dotenv(tmp_path / "no-existe")


def test_default_workspace_is_the_default_slug():
    assert paths.default_workspace().slug == "default"
    assert paths.default_workspace().root == (paths.WORKSPACES_DIR / "default").resolve()


def test_workspace_resolves_under_workspaces_dir():
    ws = paths.workspace("otro")
    assert ws.slug == "otro"
    assert ws.root.parent == paths.WORKSPACES_DIR.resolve()


def test_project_root_is_the_repository():
    assert (paths.PROJECT_ROOT / "pyproject.toml").is_file()
    package_dir = Path(paths.__file__).resolve().parents[1]
    assert paths.PROJECT_ROOT == package_dir.parent
