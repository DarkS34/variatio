"""The administration panel: one module per tab or section, every route behind `require_admin`.

    accounts.py     the front page (`/overview`), the accounts and their memberships
    invites.py      the administrator's invitations
    class_links.py  every subject's class links
    workspaces.py   the installation's subjects: renaming, deleting, ending a course, exports
    queue.py        what holds each lane, and cancelling a job
    features.py     who the optional functions are for
    maintenance.py  closing the installation's door
    engine.py       the machine and the process: GPU, models, tunnel, contexts, history
    settings.py     the installation's settings, rewritten without a restart
    shared.py       what two of the route modules share

Every module but `shared.py` is a route module: only `server/routing.py` imports it. They call
the services of every area; nothing below imports them.
"""
