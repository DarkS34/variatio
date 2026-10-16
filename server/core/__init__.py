"""What the server needs and that knows no area: the process's pieces beneath every screen.

    contexts.py      the warm pipeline contexts, an LRU of `RuntimeContext`s by slug
    installation.py  resolving a subject (`workspace_for`, `slug_error`) and its trees on disk
    environment.py   the environment's switches: production, cookies, sessions, mail, limits
    tunnel.py        the SSH tunnel to the GPU host, and its watchdog
    model_pulls.py   model downloads started from the panel or by a build
    maintenance.py   the installation's door: open, or closed for maintenance
    middleware.py    the origin check (CSRF) and the security headers
    daily.py         days and ISO weeks, in UTC
    csv_safe.py      spreadsheet-safe CSV cells
    routes/          `/api/health`, `/api/maintenance` and the WebSocket stream

Nothing here imports an area of the server (`auth/`, `pipeline/`, `bank/`, …): they import it.
"""
