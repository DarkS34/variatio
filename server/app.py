import asyncio
import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from variatio import config

from . import jobs, middleware, runtime, settings
from .routers import ROUTERS

try:
    from study import api as study_api
except ImportError:
    study_api = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    runtime.bus.attach_loop(asyncio.get_running_loop())
    _autostart_tunnel()
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
        runtime.tunnel.stop()


def _autostart_tunnel() -> None:
    if not (config.OLLAMA_SSH_AUTOSTART and runtime.tunnel.configured()):
        return
    try:
        runtime.tunnel.start()
    except Exception as e:  # noqa: BLE001 - a dead tunnel is a panel message, not a crash
        logger.warning(f"No se pudo abrir el túnel SSH al arrancar: {e}")


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
    # `/ws`, so development is same-origin too and needs nothing here; VARIATIO_DEV_CORS=1 is for
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


# THE TWO HALVES OF THE BUNDLE ARE CACHED IN OPPOSITE WAYS, and getting it wrong is not a
# performance detail — it breaks the app outright.
#
# Everything under `/assets` is content-hashed by Vite, so a given URL's bytes can never
# change: it is cacheable forever, and saying so is what keeps a returning reader from
# re-downloading React on every visit.
#
# `index.html` is the opposite. It is the one file whose URL is stable and whose CONTENT
# changes on every build, because it names the hashed chunks. It used to go out with no
# `Cache-Control` at all, which does not mean «do not cache» — it means the browser applies
# its own heuristic, and it kept an old index.html naming chunks that the next build had
# already deleted. The symptom is the one nobody can debug from inside the app: a tab that
# has been open across a deploy fails to render a lazily-loaded screen with «Failed to fetch
# dynamically imported module», and reloading does not help because the reload is served the
# same stale document. `no-cache` is revalidate-before-use rather than never-store, so the
# ETag still answers 304 on the common path and this costs one conditional request.
#
# The same applies to the handful of unhashed files beside it — `favicon.svg`, `theme.js` —
# which change with a release and are addressed by a stable URL.
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class _Assets(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["cache-control"] = IMMUTABLE
        return response


def _mount_web(app: FastAPI) -> None:
    """Serve the built front-end when it exists, so `uvicorn` alone is the whole app."""
    dist = settings.WEB_DIST_DIR
    if not dist.is_dir():
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", _Assets(directory=assets), name="assets")

    root = dist.resolve()
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (root / path).resolve()
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate, headers={"cache-control": REVALIDATE})
        return FileResponse(index, headers={"cache-control": REVALIDATE})


app = create_app()