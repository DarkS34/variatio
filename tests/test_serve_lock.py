import pytest

from server.cli.lock import LockHeld, acquire, release


def test_a_second_acquire_reports_the_conflict(tmp_path):
    path = tmp_path / ".serve.lock"
    first = acquire(path)
    try:
        with pytest.raises(LockHeld) as info:
            acquire(path)
        assert info.value.path == path
    finally:
        release(first)


def test_release_lets_the_lock_be_taken_again(tmp_path):
    path = tmp_path / ".serve.lock"
    first = acquire(path)
    release(first)
    second = acquire(path)
    release(second)


def test_release_is_idempotent(tmp_path):
    handle = acquire(tmp_path / ".serve.lock")
    release(handle)
    release(handle)
    release(None)


def test_the_serve_guard_names_the_lock_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    from server.cli import serve as serve_mod

    path = tmp_path / ".serve.lock"
    monkeypatch.setattr(serve_mod, "serve_lock_path", lambda: path)
    held = acquire(path)
    try:
        code = serve_mod.serve(None)
    finally:
        release(held)
    out = capsys.readouterr().out
    assert code == 1
    assert str(path) in out
    assert "serve" in out
