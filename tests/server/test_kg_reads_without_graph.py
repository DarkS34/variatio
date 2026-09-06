"""What the graph's read routes answer in the state every workspace starts in.

A workspace with no knowledge graph is normal — it is the first artifact anybody builds,
so it does not exist yet — and the three reads a screen makes on arrival all have to say
so with a 404. `read` and `graph` did; `read_curriculum` did not, and its `KGError` came
out of the ASGI stack as a 500 with a traceback in the log, once per visit to "Crear
ejercicios" (the generate form reads the curriculum on every mount).
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.routers import kg as route
from variatio.core.workspace import Workspace


def access(tmp_path):
    """An `Access` with nothing built: the workspace directory exists and is empty."""
    ws = Workspace(root=tmp_path, slug="test")
    ws.instance_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(ws=ws, user=None, as_admin=False)


@pytest.mark.parametrize("handler", [route.read, route.graph, route.read_curriculum])
def test_a_missing_graph_is_a_404_and_never_a_500(tmp_path, handler):
    with pytest.raises(HTTPException) as raised:
        handler(access(tmp_path))
    assert raised.value.status_code == 404
    assert "grafo" in str(raised.value.detail)


def test_every_get_of_the_router_answers_the_missing_graph_itself():
    """No read may let `KGError` reach the ASGI layer.

    Structural, because the failure is one route out of several forgetting a `try`, and
    the next one added would forget it the same way. `_handle` is the shared answer for
    the edits (422 there: an editor refusing an edit is not a missing artifact), so a
    handler either goes through it or catches for itself.
    """
    missing = []
    for router_route in route.router.routes:
        if "GET" not in getattr(router_route, "methods", set()):
            continue
        source = inspect.getsource(router_route.endpoint)
        if "except KGError" not in source and "_handle(" not in source:
            missing.append(router_route.path)
    assert missing == [], f"lecturas sin respuesta propia al grafo ausente: {missing}"
