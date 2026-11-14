"""Loading and saving profiles: atomic writes, migrations, backup of broken files (SPEC 14.1)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from optima_time.config.models import SCHEMA_VERSION, Profile

log = logging.getLogger(__name__)

APP_DIR_ENV = "OPTIMA_TIME_HOME"

# from_version -> function returning the data in version from_version + 1
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def app_dir() -> Path:
    """%APPDATA%\\OptimaTime on Windows, ~/.optima-time elsewhere; OPTIMA_TIME_HOME overrides."""
    if env := os.environ.get(APP_DIR_ENV):
        return Path(env)
    if appdata := os.environ.get("APPDATA"):
        return Path(appdata) / "OptimaTime"
    return Path.home() / ".optima-time"


def write_atomic(path: Path, data: bytes) -> None:
    """Write to a temp file in the same folder, then replace the target (never half-written)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {version!r}")
    while version < SCHEMA_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
        data["schema_version"] = version
    return data


def parse_profile(data: dict[str, Any]) -> Profile:
    return Profile.model_validate(migrate(data))


def save_profile(profile: Profile, path: Path) -> None:
    text = profile.model_dump_json(indent=2) + "\n"
    write_atomic(path, text.encode("utf-8"))


def load_profile(path: Path) -> Profile:
    """Load a profile. A broken file is moved aside (…broken-<time>.json) and a default
    profile is returned, so the app always starts."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("profile is not a JSON object")
        return parse_profile(data)
    except FileNotFoundError:
        raise
    except (ValueError, ValidationError) as error:
        backup = path.with_name(f"{path.stem}.broken-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
        path.replace(backup)
        log.error(
            "profile %s is broken (%s); moved to %s, starting with defaults", path, error, backup
        )
        return Profile(name=path.stem)
