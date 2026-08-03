"""FastAPI backend for the variant generator.

It wraps `variant_generator` without forking it: the CLI keeps working exactly as
before, and everything the UI needs (progress, cancellation, streaming) arrives
through additive hooks in the core.
"""

__all__ = ["create_app"]


def create_app():
    from .app import create_app as _create_app

    return _create_app()
