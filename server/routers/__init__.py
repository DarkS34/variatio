from . import auth, bank, evaluation, health, jobs, kg, pipeline, profile, raw, ws

ROUTERS = [
    auth.router,
    health.router,
    pipeline.router,
    profile.router,
    kg.router,
    bank.router,
    raw.router,
    jobs.router,
    evaluation.router,
    ws.router,
]

__all__ = ["ROUTERS"]
