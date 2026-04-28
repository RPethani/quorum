"""Entry for `python -m quorum_conductor`. Mirrors the `quorum` console script."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
