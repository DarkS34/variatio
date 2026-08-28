import httpx
import ollama
import pytest

from variatio import config
from variatio.core import inference
from variatio.core.cerebras import CerebrasEngine
from variatio.core.inference import InferenceError, OllamaEngine

# Lo que un motor contesta es SUYO, no nuestro: `ollama.ResponseError` lleva dentro el
# cuerpo crudo de la respuesta y esos mensajes acaban en el panel, así que cualquier cosa
# que conteste el host al que apunta OLLAMA_HOST se leería en la pantalla de quien mira.
BODY = "<html>traza del motor con lo que haya dentro</html>"


@pytest.fixture
def engine(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    return OllamaEngine()


class _Client:
    def __init__(self, exc):
        self._exc = exc

    def __getattr__(self, name):
        def call(*args, **kwargs):
            raise self._exc

        return call


def test_the_helper_keeps_the_status_and_drops_the_body(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    message = inference._upstream_error("Falló algo", ollama.ResponseError(BODY, 404))
    assert "404" in message
    assert "localhost:13434" in message
    assert BODY not in message


def test_the_helper_says_it_could_not_reach_the_engine_when_there_is_no_status(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    message = inference._upstream_error("Falló algo", httpx.ConnectError(BODY))
    assert "ConnectError" in message
    assert BODY not in message


# Cada sitio que hablaba con Ollama reflejaba el `{e}` entero. La lista es la de verdad: el
# listado y el borrado llegan al panel de «Motor», la descarga a través de `PullTracker`, la
# residencia a `/api/health` y los dos de embedding al error de un trabajo.
@pytest.mark.parametrize(
    "call",
    [
        lambda e: e.installed_models_detail(),
        lambda e: e.running_models(),
        lambda e: e.pull("qwen3.8:27b-q4_K_M"),
        lambda e: e.delete("qwen3.8:27b-q4_K_M"),
        lambda e: e.embed("qwen3-embedding:4b", "texto"),
        lambda e: e.embed_batch("qwen3-embedding:4b", ["texto"]),
    ],
)
def test_no_ollama_call_reflects_the_engines_own_body(engine, call):
    engine._client = _Client(ollama.ResponseError(BODY, 500))
    with pytest.raises(InferenceError) as error:
        call(engine)
    assert BODY not in str(error.value)
    assert "500" in str(error.value)


def test_a_failed_pull_reaches_the_panel_without_the_body(engine):
    from server.model_pulls import PullTracker

    engine._client = _Client(ollama.ResponseError(BODY, 500))
    tracker = PullTracker()
    tracker._pulls["m"] = {
        "model": "m",
        "status": "running",
        "completed": 0,
        "total": 0,
        "started_at": 0.0,
        "finished_at": None,
        "error": None,
        "user": None,
    }
    tracker._run("m")
    entry = tracker._pulls["m"]
    assert entry["status"] == "failed"
    assert BODY not in (entry["error"] or "")


# La mitad remota tiene la misma regla, y la ruta que transmite es la que menos se prueba:
# un no-200 en `stream` se leía entero con `response.read()` y se metía en el error.
def test_the_streaming_path_names_the_status_but_not_the_body(monkeypatch):
    monkeypatch.setattr(config, "CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
    engine = CerebrasEngine()
    engine._client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(413, text=BODY)),
        base_url="https://api.cerebras.ai/v1",
    )
    with pytest.raises(InferenceError) as error:
        engine.generate_stream(
            "gemma-4-31b", "hola", on_token=lambda text, channel: None
        )
    assert "413" in str(error.value)
    assert BODY not in str(error.value)
