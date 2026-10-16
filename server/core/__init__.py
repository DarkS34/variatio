"""What the server needs and that knows no area: the process's pieces beneath every screen.

    process.py       the process's live pieces: the bus, the queue, the idle unloader, the
                     tunnel and the model downloads
    contexts.py      the warm pipeline contexts, an LRU of `RuntimeContext`s by slug
    installation.py  resolving a subject's slug (`workspace_for`, `slug_error`)
    environment.py   the environment's switches: production, cookies, sessions, mail, limits
    tunnel.py        the SSH tunnel to the GPU host, and its watchdog
    model_pulls.py   model downloads started from the panel or by a build
    maintenance.py   the installation's door: open, or closed for maintenance
    middleware.py    the origin check (CSRF) and the security headers
    daily.py         days and ISO weeks, in UTC
    csv_safe.py      spreadsheet-safe CSV cells
    routes/          `/api/health`, `/api/maintenance` and the WebSocket stream

Nothing here imports an area of the server (`auth/`, `pipeline/`, `bank/`, …): they import it.
The queue's machinery (`jobs/`) is below the core, which assembles the live queue from it.
"""
