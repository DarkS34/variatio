import pytest

from variatio.settings import REGISTRY, SettingError
from variatio.settings.registry import BY_KEY
from variatio.settings.store import resolve, validate_patch

# The two settings that name WHERE this process sends its model traffic. Both used to be
# hot-editable from «Administración → Configuración», which made `PUT /api/admin/config` a
# way to redirect it: the Cerebras client is built with the base URL AND the
# `Authorization: Bearer CEREBRAS_API_KEY` header, so moving the URL delivers the key that
# `engine.cerebras_api_key` is `secret=True, editable=False` to protect; and `OLLAMA_HOST`
# is every engine call this process makes, whose answer comes back on screen.
ENDPOINTS = ("engine.cerebras_base_url", "engine.ollama_host")


@pytest.mark.parametrize("key", ENDPOINTS)
def test_the_engine_endpoints_are_environment_only(key):
    setting = BY_KEY[key]
    assert not setting.editable, f"{key} vuelve a ser editable en caliente"
    assert setting.env, f"{key} no declara variable de entorno, que es su única vía"


@pytest.mark.parametrize("key", ENDPOINTS)
def test_a_patch_that_moves_an_endpoint_is_refused(key):
    with pytest.raises(SettingError):
        validate_patch(list(REGISTRY), {key: "http://attacker.example/v1"})


def test_the_refusal_survives_being_hidden_among_editable_keys():
    with pytest.raises(SettingError):
        validate_patch(
            list(REGISTRY),
            {
                "sampling.temperature_generation": 0.3,
                "engine.cerebras_base_url": "http://attacker.example/v1",
            },
        )


# Non-editable is not «unreachable»: pointing at a proxy, at a mock in tests, or at the port
# the tunnel opens is the documented purpose, and the environment is where that is done —
# the environment wins over `config.json` for every setting, which is what already made the
# panel's control inert on an installation whose `.env` sets these.
@pytest.mark.parametrize(
    "key, env, value",
    [
        ("engine.cerebras_base_url", "CEREBRAS_BASE_URL", "http://localhost:9999/v1"),
        ("engine.ollama_host", "OLLAMA_HOST", "gpu.interno:11434"),
    ],
)
def test_the_environment_still_points_the_endpoint_wherever_it_likes(key, env, value):
    values, sources = resolve(list(REGISTRY), {key: "http://del-fichero"}, {env: value})
    assert values[key] == value
    assert sources[key] == "env"


@pytest.mark.parametrize(
    "key, env",
    [
        ("engine.cerebras_base_url", "CEREBRAS_BASE_URL"),
        ("engine.ollama_host", "OLLAMA_HOST"),
    ],
)
def test_without_the_variable_the_file_value_still_resolves(key, env):
    values, sources = resolve(list(REGISTRY), {key: "http://del-fichero"}, {})
    assert values[key] == "http://del-fichero"
    assert sources[key] == "file"
