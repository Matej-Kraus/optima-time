"""Command line (SPEC 14.2). Milestone 1: `run` with a profile and an optional video file.

optima-time run --profile PATH [--source VIDEO] [--port 8787] [--no-browser]
optima-time --version
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import webbrowser
from pathlib import Path

from optima_time import __version__


def run(args: argparse.Namespace) -> int:
    import uvicorn

    from optima_time.api.app import create_app
    from optima_time.config.models import Profile
    from optima_time.config.store import load_profile, save_profile
    from optima_time.runner import Runner

    path: Path = args.profile
    profile = load_profile(path) if path.exists() else Profile(name=path.stem)
    if args.source:
        profile = profile.model_copy(
            update={
                "source": profile.source.model_copy(update={"path": str(args.source.resolve())})
            }
        )
    if not path.exists():
        save_profile(profile, path)
    runner = Runner(profile, path, threads=args.threads)
    runner.start()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Optima Time {__version__}: {url}  (profil {path})")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        uvicorn.run(create_app(runner), host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        runner.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="optima-time")
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("run", help="start processing and the UI")
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--source", type=Path, help="video or image file (overrides the profile)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--threads", type=int, default=2, help="ONNX Runtime threads")
    p.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.version:
        print(f"optima-time {__version__}")
        return 0
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if args.command == "run":
        return run(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
