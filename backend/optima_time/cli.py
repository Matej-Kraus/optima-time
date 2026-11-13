"""Command-line entry point. Only a placeholder until Milestone 1."""

import sys

from optima_time import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--version"]:
        print(f"optima-time {__version__}")
        return 0
    print("optima-time: nothing to run yet (Milestone 0)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
