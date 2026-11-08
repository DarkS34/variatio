"""What one process holds: no engine before it is asked for, one Ollama per host, none unused."""

import contextvars
import fcntl
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from variatio import config, inference, settings
from variatio.inference import InferenceError
from variatio.inference.cerebras_ollama.budget import Budget
from variatio.inference.engines import EngineSet


@pytest.fixture
def engines(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_HOST", "http://localhost:13434")
    engines = EngineSet()
    yield engines
    engines.close_all()


# THE SET ----------------------------------------------------------------------------------


def test_nothing_is_built_until_somebody_asks(engines):
    assert engines.names() == []
    assert engines.existing("ollama") is None
    assert engines.local_engines() == []


def test_an_unknown_engine_is_refused(engines):
    with pytest.raises(InferenceError, match="Unknown inference engine"):
        engines.get("vllm")


def test_the_hybrid_shares_the_ollama_engine_of_its_host(engines):
    local = engines.get("ollama")
    hybrid = engines.get("cerebras+ollama")
    assert hybrid._ollama is local
    assert engines.local_engines() == [local]


def test_the_local_half_outlives_the_ollama_engine_while_the_hybrid_uses_it(engines):
    local = engines.get("ollama")
    engines.get("cerebras+ollama")
    engines.close("ollama")
    assert engines.existing("ollama") is None
    assert engines.local_engines() == [local]
    engines.close("cerebras+ollama")
    assert engines.local_engines() == []


def test_keep_builds_the_wanted_engines_and_closes_the_rest(engines):
    engines.get("cerebras+ollama")
    engines.keep({"ollama"})
    assert engines.names() == ["ollama"]


def test_a_held_engine_outlives_its_last_account_until_its_job_ends(engines):
    engines.keep({"cerebras+ollama"})
    engines.hold("cerebras+ollama")
    engines.keep({"ollama"})
    assert engines.existing("cerebras+ollama") is not None
    engines.release("cerebras+ollama")
    assert engines.existing("cerebras+ollama") is None


# THE CONTEXT ------------------------------------------------------------------------------


def test_with_no_engine_fixed_a_call_raises():
    with pytest.raises(InferenceError, match="No hay motor"):
        contextvars.Context().run(inference.engine)


def test_a_deferred_engine_is_built_only_when_a_call_asks(engines):
    built = []

    def build():
        built.append(1)
        return engines.get("ollama")

    with inference.using_deferred(build):
        assert built == []
        assert inference.engine_name() == "ollama"
        assert settings.engine_profile().engine == "ollama"
    assert built == [1]


def test_two_threads_on_two_engines_do_not_mix(engines):
    seen: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def run(name: str) -> None:
        with inference.using(engines.get(name)):
            barrier.wait()
            seen[name] = f"{inference.engine_name()}|{settings.engine_profile().engine}"

    threads = [threading.Thread(target=run, args=(name,)) for name in ("ollama", "cerebras+ollama")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert seen == {
        "ollama": "ollama|ollama",
        "cerebras+ollama": "cerebras+ollama|cerebras+ollama",
    }


def test_a_pool_thread_sees_the_engine_only_with_the_context_copied(engines):
    with inference.using(engines.get("cerebras+ollama")), ThreadPoolExecutor(1) as pool:
        assert pool.submit(contextvars.copy_context().run, inference.engine_name).result() == (
            "cerebras+ollama"
        )
        with pytest.raises(InferenceError):
            pool.submit(inference.engine).result()


# THE LEDGER -------------------------------------------------------------------------------


def test_two_ledgers_over_one_file_exclude_each_other_in_one_process(tmp_path):
    first = Budget(tmp_path / "ledger.json")
    second = Budget(tmp_path / "ledger.json")
    with first._flock():
        handle = open(second._lock_path, "a+")
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            handle.close()


def test_what_one_ledger_records_the_other_reads(tmp_path):
    first = Budget(tmp_path / "ledger.json")
    second = Budget(tmp_path / "ledger.json")
    first.record("gemma-4-31b", "fase", prompt_tokens=10, completion_tokens=5, headers={})
    [model] = second.snapshot()["models"]
    assert model["windows"]["day"]["requests_used"] == 1
