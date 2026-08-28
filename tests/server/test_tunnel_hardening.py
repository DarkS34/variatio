import pytest

from server import tunnel
from variatio import config


@pytest.fixture
def tunnel_config(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    monkeypatch.setattr(config, "OLLAMA_SSH_HOST", "yo@gpu")
    monkeypatch.setattr(config, "OLLAMA_SSH_REMOTE_PORT", 11434)
    monkeypatch.setattr(config, "OLLAMA_SSH_KEY_PATH", "")
    monkeypatch.setattr(config, "OLLAMA_SSH_AUTOSTART", False)
    monkeypatch.setattr(tunnel.shutil, "which", lambda name: "/usr/bin/ssh")


# A PORT THAT IS NOT A NUMBER ---------------------------------------------------------------
#
# `urlsplit(...)` splits happily and only converts the port when `.port` is read, where a
# non-numeric one raises `ValueError` — not the `None` the missing-port branch expects. It
# escaped through `status()` and through `ssh_command()`, so the two reads and the start
# answered 500 instead of the refusal the missing-port case already had.


@pytest.mark.parametrize("host", ["localhost:notaport", "http://gpu:puerto", "gpu:-1"])
def test_a_port_that_is_not_a_number_is_a_named_refusal(tunnel_config, monkeypatch, host):
    monkeypatch.setattr(config, "OLLAMA_HOST", host)
    with pytest.raises(tunnel.TunnelError):
        tunnel.local_port()


@pytest.mark.parametrize("host", ["localhost:notaport", "gpu:-1", "localhost"])
def test_status_reports_no_local_port_instead_of_raising(tunnel_config, monkeypatch, host):
    monkeypatch.setattr(config, "OLLAMA_HOST", host)
    status = tunnel.SshTunnel().status()
    assert status["local_port"] is None


def test_starting_with_an_unreadable_port_is_a_tunnel_error_not_a_value_error(
    tunnel_config, monkeypatch
):
    monkeypatch.setattr(config, "OLLAMA_HOST", "localhost:notaport")
    # A `TunnelError` is what the panel turns into a 409 with its explanation; a `ValueError`
    # reaching the route is the 500 this pins against.
    with pytest.raises(tunnel.TunnelError):
        tunnel.ssh_command()
    with pytest.raises(tunnel.TunnelError):
        tunnel.SshTunnel().start()


# THE DESTINATION IS NOT AN OPTION ----------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    ["-oProxyCommand=touch /tmp/pwned", "-E/tmp/log", "--", "-l"],
)
def test_a_destination_that_starts_with_a_dash_is_refused(tunnel_config, monkeypatch, host):
    monkeypatch.setattr(config, "OLLAMA_SSH_HOST", host)
    with pytest.raises(tunnel.TunnelError, match="-"):
        tunnel.ssh_command()


def test_an_ordinary_destination_is_still_the_last_argument(tunnel_config):
    command = tunnel.ssh_command()
    assert command[-1] == "yo@gpu"
    assert command[command.index("-L") + 1] == "13434:localhost:11434"


def test_a_destination_that_merely_contains_a_dash_is_fine(tunnel_config, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_SSH_HOST", "yo@gpu-01.interno")
    assert tunnel.ssh_command()[-1] == "yo@gpu-01.interno"
