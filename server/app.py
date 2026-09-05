"""The composition root: the FastAPI app, its middleware stack and the built front-end.

Nothing inside `server` may import this module. It is also the only place the evaluation is
mounted, because `evaluation.api` imports `server.auth` and `server.routers.jobs` back and
mounting it from the router package would close a cycle.
"""

import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from variatio import config

from . import installation, jobs, middleware, singletons
from .routers import ROUTERS

try:
    from evaluation import api as evaluation_api
except ImportError:
    evaluation_api = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the bus, tunnel, queue and idle unloader, and let go of the GPU on the way out.

    With `OLLAMA_KEEP_ALIVE=24h` the process that loaded the models is the only one that
    can release them, so shutdown does it best-effort in a thread — a slow engine must not
    hold the event loop past uvicorn's own shutdown timeout.
    """
    singletons.bus.attach_loop(asyncio.get_running_loop())
    _autostart_tunnel()
    singletons.runner.start()
    singletons.idle_unloader.start()
    try:
        yield
    finally:
        singletons.idle_unloader.stop()
        singletons.runner.shutdown()
        try:
            await asyncio.wait_for(asyncio.to_thread(jobs.release_gpu, "al apagar la API"), 20)
        except Exception as e:  # noqa: BLE001 - shutdown must finish whatever the engine does
            logger.warning(f"No se pudieron descargar los modelos de la GPU al apagar: {e}")
        singletons.tunnel.stop()


def _autostart_tunnel() -> None:
    """Open the SSH tunnel when the installation asks for it; a failure is a panel message."""
    if not (config.OLLAMA_SSH_AUTOSTART and singletons.tunnel.configured()):
        return
    try:
        singletons.tunnel.start()
    except Exception as e:  # noqa: BLE001 - a dead tunnel is a panel message, not a crash
        logger.warning(f"No se pudo abrir el túnel SSH al arrancar: {e}")


def create_app() -> FastAPI:
    """Assemble the whole application: middleware, routers, the evaluation and the bundle."""
    app = FastAPI(
        title="Graph-Guided Variant Generator",
        description="Pipeline por etapas con revisión humana en cada eslabón.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # `add_middleware` inserts at the front, so the LAST call is the OUTERMOST layer.
    # `SecurityHeaders` goes last or `OriginCheck`'s own 403 leaves without a CSP.
    app.add_middleware(middleware.OriginCheck)
    app.add_middleware(middleware.SecurityHeaders)

    # Off by default: with a session cookie, a permissive CORS policy turns another
    # origin's page into a logged-in client. Vite proxies `/api` and `/ws` in development.
    origins = installation.dev_cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    for router in ROUTERS:
        app.include_router(router)

    # The evaluation registers its own routers and job handler here, and only here: importing
    # it from the router package would close a cycle.
    if evaluation_api is not None:
        evaluation_api.install(app)

    _mount_web(app)
    return app


# The two halves of the bundle are cached in opposite ways, and getting it wrong breaks the
# app outright. `/assets` is content-hashed by Vite, so a URL's bytes can never change.
# `index.html` and the unhashed files beside it have stable URLs whose content changes every
# build, and a browser heuristic there serves an index naming chunks the deploy deleted —
# every lazy route then fails with «Failed to fetch dynamically imported module».
# `no-cache` is revalidate-before-use, so the ETag still answers 304 on the common path.
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class _Assets(StaticFiles):
    """Static files served under `/assets`, cacheable for a year because Vite hashes them."""

    def file_response(self, *args, **kwargs):
        """Serve one file, stamping the immutable cache policy on it."""
        response = super().file_response(*args, **kwargs)
        response.headers["cache-control"] = IMMUTABLE
        return response


def _mount_web(app: FastAPI) -> None:
    """Serve the built front-end when it exists, so `uvicorn` alone is the whole app."""
    dist = installation.WEB_DIST_DIR
    if not dist.is_dir():
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _Assets(directory=assets), name="assets")

    root = dist.resolve()
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        """Serve a file of the bundle, or `index.html` so the client router owns the URL."""
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate, headers={"cache-control": REVALIDATE})
        return FileResponse(index, headers={"cache-control": REVALIDATE})


app = create_app()