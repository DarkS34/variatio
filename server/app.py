import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from . import jobs, middleware, runtime, settings
from .routers import ROUTERS

try:
    from study import api as study_api
except ImportError:
    study_api = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.bus.attach_loop(asyncio.get_running_loop())
    runtime.runner.start()
    runtime.idle_unloader.start()
    try:
        yield
    finally:
        runtime.idle_unloader.stop()
        runtime.runner.shutdown()
        # The process that loaded the models is the one that lets go of them: with
        # `OLLAMA_KEEP_ALIVE=24h` a stopped API would otherwise leave ~29 GiB resident on a
        # shared card until tomorrow. Best-effort, in a thread so a slow engine cannot hold
        # the event loop past uvicorn's own shutdown timeout.
        try:
            await asyncio.wait_for(asyncio.to_thread(jobs.release_gpu, "al apagar la API"), 20)
        except Exception as e:  # noqa: BLE001 - shutdown must finish whatever the engine does
            logger.warning(f"No se pudieron descargar los modelos de la GPU al apagar: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Graph-Guided Variant Generator",
        description="Pipeline por etapas con revisión humana en cada eslabón.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(middleware.SecurityHeaders)
    app.add_middleware(middleware.OriginCheck)

    # Gone from the default configuration: with a session cookie, a permissive CORS policy
    # is what turns another origin's page into a logged-in client. Vite proxies `/api` and
    # `/ws`, so development is same-origin too and needs nothing here; VG_DEV_CORS=1 is for
    # the rare case of pointing the SPA straight at the API, and never applies in
    # production.
    origins = settings.dev_cors_origins()
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

    # The study is an installation of this one, not a part of it: it registers its own
    # routers and its own job handler here, and an installation without it simply serves
    # one job kind fewer.
    if study_api is not None:
        study_api.install(app)

    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Serve the built front-end when it exists, so `uvicorn` alone is the whole app."""
    dist = settings.WEB_DIST_DIR
    if not dist.is_dir():
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = dist / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()