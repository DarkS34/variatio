import json

import pytest

from server import settings as server_settings
from server import tunnel
from server.auth.rate_limit import RateLimiter
from variant_generator import config
from variant_generator import settings as vg_settings
from variant_generator.core.workspace import Workspace
from variant_generator.settings import store


# THE TUNNEL ------------------------------------------------------------------------------


@pytest.fixture
def tunnel_config(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    monkeypatch.setattr(config, "OLLAMA_SSH_HOST", "yo@gpu")
    monkeypatch.setattr(config, "OLLAMA_SSH_REMOTE_PORT", 11434)
    monkeypatch.setattr(config, "OLLAMA_SSH_KEY_PATH", "")
    monkeypatch.setattr(tunnel.shutil, "which", lambda name: "/usr/bin/ssh")


def test_the_local_port_comes_from_the_ollama_host(tunnel_config):
    assert tunnel.local_port() == 13434


def test_the_command_forwards_the_local_port_to_the_remote_one(tunnel_config):
    command = tunnel.ssh_command()
    assert command[0] == "/usr/bin/ssh"
    assert "-N" in command
    assert command[command.index("-L") + 1] == "13434:localhost:11434"
    assert command[-1] == "yo@gpu"
    assert "BatchMode=yes" in command
    assert "-i" not in command


def test_a_key_path_is_passed_with_dash_i(tunnel_config, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_SSH_KEY_PATH", "/home/yo/.ssh/gpu")
    command = tunnel.ssh_command()
    assert command[command.index("-i") + 1] == "/home/yo/.ssh/gpu"


def test_an_empty_host_means_no_tunnel(tunnel_config, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_SSH_HOST", "   ")
    assert not tunnel.SshTunnel().configured()
    with pytest.raises(tunnel.TunnelError, match="OLLAMA_SSH_HOST"):
        tunnel.ssh_command()


def test_a_missing_ssh_client_is_a_named_error(tunnel_config, monkeypatch):
    monkeypatch.setattr(tunnel.shutil, "which", lambda name: None)
    with pytest.raises(tunnel.TunnelError, match="ssh"):
        tunnel.ssh_command()


def test_status_before_any_start_reports_nothing_running(tunnel_config):
    status = tunnel.SshTunnel().status()
    assert status["configured"] is True
    assert status["running"] is False
    assert status["wanted"] is False
    assert status["local_port"] == 13434


# THE LOCK-OUT ----------------------------------------------------------------------------


def test_wait_for_reads_the_lock_without_counting_an_attempt():
    limiter = RateLimiter()
    for _ in range(3):
        assert limiter.check("login", "ana", limit=3, window=300.0) == 0.0
    assert limiter.wait_for("login", "ana", limit=3, window=300.0) > 0.0
    assert limiter.wait_for("login", "ana", limit=3, window=300.0) > 0.0
    assert limiter.wait_for("login", "nadie", limit=3, window=300.0) == 0.0


def test_clear_unlocks_the_account():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("login", "ana", limit=3, window=300.0)
    limiter.clear("login", "ana")
    assert limiter.wait_for("login", "ana", limit=3, window=300.0) == 0.0


# RESET TO DEFAULT ------------------------------------------------------------------------


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(store, "CONFIG_PATH", path)
    namespace: dict = {}
    vg_settings.apply(namespace)
    yield path, namespace
    vg_settings.apply(namespace)


def test_reset_removes_the_key_from_the_file_and_restores_the_default(config_file):
    path, namespace = config_file
    vg_settings.update({"engine.idle_unload_seconds": 42})
    assert namespace["IDLE_UNLOAD_SECONDS"] == 42
    assert json.loads(path.read_text(encoding="utf-8"))["engine"]["idle_unload_seconds"] == 42

    vg_settings.reset(["engine.idle_unload_seconds"])
    written = json.loads(path.read_text(encoding="utf-8"))
    assert "idle_unload_seconds" not in written.get("engine", {})
    assert namespace["IDLE_UNLOAD_SECONDS"] == 1800
    assert vg_settings.sources()["engine.idle_unload_seconds"] == "default"


def test_reset_refuses_an_unknown_key(config_file):
    with pytest.raises(vg_settings.SettingError, match="no.existe"):
        vg_settings.reset(["no.existe"])


# DISK ------------------------------------------------------------------------------------


def test_disk_usage_splits_the_tree_by_role(tmp_path):
    ws = Workspace(tmp_path / "w", slug="w")
    (ws.raw_corpus_dir).mkdir(parents=True)
    (ws.raw_corpus_dir / "a.pdf").write_bytes(b"x" * 10)
    ws.instance_dir.mkdir(parents=True)
    ws.kg_path.write_bytes(b"x" * 20)
    ws.history_dir.mkdir()
    (ws.history_dir / "old.json").write_bytes(b"x" * 5)
    (ws.cache_dir / "embeddings").mkdir(parents=True)
    (ws.cache_dir / "embeddings" / "c.npz").write_bytes(b"x" * 7)

    usage = server_settings.disk_usage(ws)
    assert usage == {"raw": 10, "instance": 20, "cache": 7, "history": 5, "total": 42}


def test_clear_cache_removes_vectors_and_markdown_but_keeps_descriptions(tmp_path):
    ws = Workspace(tmp_path / "w", slug="w")
    (ws.cache_dir / "embeddings").mkdir(parents=True)
    (ws.cache_dir / "embeddings" / "c.npz").write_bytes(b"x" * 7)
    ws.markdown_cache_dir.mkdir()
    (ws.markdown_cache_dir / "doc.md").write_text("hola", encoding="utf-8")
    ws.concept_descriptions_path.write_text("{}", encoding="utf-8")

    result = server_settings.clear_cache(ws)
    assert result == {"files_removed": 2, "bytes_freed": 11}
    assert not (ws.cache_dir / "embeddings").exists()
    assert not ws.markdown_cache_dir.exists()
    assert ws.concept_descriptions_path.is_file()
