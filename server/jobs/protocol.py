"""The one token the build subprocess and its parent share.

It lives apart from both: importing `server.jobs` reaches the handlers and through them the
parent side of the build, so a marker kept in the worker would be imported before runpy runs
that module as `__main__` — and every build would open with runpy's "found in sys.modules"
warning on the event pipe.
"""

MARKER = "@@EVT@@"
