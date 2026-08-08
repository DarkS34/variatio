"""The one token the build subprocess and its parent share.

It lives apart from both on purpose: importing `server.jobs` pulls in the handlers,
and through them the parent side of the build. If the marker lived in the worker,
that chain would import `server.jobs.build_worker` before runpy ran it as
`__main__`, and every build would start with runpy's "found in sys.modules"
RuntimeWarning on the event pipe.
"""

MARKER = "@@EVT@@"
