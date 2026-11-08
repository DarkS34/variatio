"""The administration panel: one module per tab or section, every route behind `require_admin`.

    routes/accounts.py     the front page (`/overview`), the accounts and their memberships
    routes/invites.py      the administrator's invitations
    routes/class_links.py  every subject's class links
    routes/workspaces.py   the installation's subjects: renaming, deleting, ending a course, exports
    routes/queue.py        what holds each lane, and cancelling a job
    routes/features.py     who the optional functions are for
    routes/maintenance.py  closing the installation's door
    routes/engine.py       the machine and the process: GPU, models, tunnel, contexts, history
    routes/settings.py     the installation's settings, rewritten without a restart
    shared.py              what two of the route modules share

Every module of `routes/` is a route module: only `server/routing.py` imports it. They call
the services of every area; nothing below imports them.
"""
