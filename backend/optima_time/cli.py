"""Command line (SPEC 14.2).

  optima-time run --profile NAME|PATH [--source VIDEO] [--port 8787] [--no-browser]
                  [--log-dir DIR] [--host 127.0.0.1] [--pin PIN] [--threads 2]
  optima-time --version
  optima-time --self-test

Started without arguments as the packaged app: the last profile, with a tray icon.

NAME is looked up in %APPDATA%\\OptimaTime\\profiles; a missing profile is created. Several
instances may run side by side with different profiles and ports.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import logging.handlers
import sys
import threading
import webbrowser
from pathlib import Path

from optima_time import __version__

LOCAL = {"127.0.0.1", "localhost", "::1"}


def setup_logging(log_dir: Path) -> None:
    """Console + rotating application log (SPEC 14.3)."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file = logging.handlers.RotatingFileHandler(
            log_dir / "app.log", maxBytes=5 * 2**20, backupCount=5, encoding="utf-8"
        )
        file.setFormatter(fmt)
        root.addHandler(file)
    except OSError as error:
        logging.warning("can't write the application log in %s: %s", log_dir, error)


def run(args: argparse.Namespace) -> int:
    import uvicorn

    from optima_time.api.app import create_app
    from optima_time.config import profiles
    from optima_time.config.models import Profile
    from optima_time.config.store import app_dir, load_profile, save_profile
    from optima_time.runner import Runner

    if args.host not in LOCAL and not args.pin:
        print("Přístup ze sítě (--host) jde zapnout jen s PINem (--pin).", file=sys.stderr)
        return 2
    log_dir = args.log_dir or app_dir() / "logs"
    setup_logging(log_dir)
    path = profiles.resolve(args.profile)
    profile = load_profile(path) if path.exists() else Profile(name=path.stem)
    if args.source:
        source = profile.source.model_copy(
            update={"type": "file", "path": str(args.source.resolve())}
        )
        profile = profile.model_copy(update={"source": source})
    if not path.exists() or args.source:
        save_profile(profile, path)
    remember_profile(path)
    runner = Runner(profile, path, threads=args.threads, log_dir=log_dir)
    runner.start()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Optima Time {__version__}: {url}  (profil {path})")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    config = uvicorn.Config(
        create_app(runner, pin=args.pin), host=args.host, port=args.port, log_level="warning"
    )
    server = uvicorn.Server(config)
    remove_tray = None
    if args.tray:
        from optima_time.tray import start_tray

        remove_tray = start_tray(url, lambda: setattr(server, "should_exit", True))
    try:
        server.run()  # Ctrl+C or "Ukončit" in the tray menu ends it
    finally:
        if remove_tray:
            remove_tray()
        runner.stop()
    return 0


def remember_profile(path: Path) -> None:
    """settings.json: the last profile, for starting the packaged app without arguments."""
    from optima_time.config.store import app_dir, write_atomic

    try:
        data = json.dumps({"last_profile": str(path)}, ensure_ascii=False).encode("utf-8")
        write_atomic(app_dir() / "settings.json", data)
    except OSError as error:
        logging.warning("can't save settings.json: %s", error)


def last_profile() -> str:
    from optima_time.config.store import app_dir

    try:
        data = json.loads((app_dir() / "settings.json").read_text(encoding="utf-8"))
        return str(data.get("last_profile") or "default")
    except (OSError, ValueError):
        return "default"


def utf8_console() -> None:
    """Czech messages must not crash a Windows console in cp1252 (found by CI on Windows)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    utf8_console()
    parser = argparse.ArgumentParser(prog="optima-time")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="check the installation, no UI")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("run", help="start processing and the UI")
    p.add_argument("--profile", required=True, help="profile name or path to a .json")
    p.add_argument("--source", type=Path, help="video or image file (overrides the profile)")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--host", default="127.0.0.1", help="0.0.0.0 = reachable from the network")
    p.add_argument("--pin", help="PIN required for access from other devices")
    p.add_argument("--threads", type=int, default=2, help="ONNX Runtime threads")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--log-dir", type=Path, help="logs (default: app folder/logs)")
    p.add_argument("--tray", action="store_true", help="icon in the notification area (Windows)")
    argv = sys.argv[1:] if argv is None else argv
    if not argv and getattr(sys, "frozen", False):
        # the packaged app started by double-click: last profile, tray icon, browser
        argv = ["run", "--profile", last_profile(), "--tray"]
    args = parser.parse_args(argv)

    if args.version:
        print(f"optima-time {__version__}")
        return 0
    if args.self_test:
        from optima_time.selftest import run_self_test

        return run_self_test()
    if args.command == "run":
        return run(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
