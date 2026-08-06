from . import bank, health, jobs, kg, pipeline, profile, raw, ws

ROUTERS = [
    health.router,
    pipeline.router,
    profile.router,
    kg.router,
    bank.router,
    raw.router,
    jobs.router,
    ws.router,
]

__all__ = ["ROUTERS"]
