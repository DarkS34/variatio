"""Entry point for `python -m server`, delegating to the `system` CLI."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
