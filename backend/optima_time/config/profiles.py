"""Profile files: one JSON per hall and sport (SPEC 13.3, 14.1).

They live in %APPDATA%\\OptimaTime\\profiles (OPTIMA_TIME_HOME overrides the app folder).
"""

from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

from optima_time.config.models import Profile
from optima_time.config.store import app_dir, load_profile, save_profile


def profiles_dir() -> Path:
    return app_dir() / "profiles"


def safe_name(name: str) -> str:
    """A file-safe profile name: letters (with diacritics), digits, '-' and '_'."""
    name = unicodedata.normalize("NFC", name).strip()
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"[^\w\-]", "", name, flags=re.UNICODE)
    if not name or name in {".", ".."}:
        raise ValueError("neplatný název profilu")
    return name[:64]


def resolve(name_or_path: str | Path) -> Path:
    """A path as given if it looks like one, else profiles_dir()/<name>.json."""
    p = Path(name_or_path)
    if p.suffix.lower() == ".json" or p.parent != Path(".") or p.exists():
        return p
    return profiles_dir() / f"{safe_name(str(name_or_path))}.json"


def list_profiles() -> list[dict]:
    folder = profiles_dir()
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("*.json")):
        if ".broken-" in path.name:
            continue
        out.append(
            {
                "name": path.stem,
                "path": str(path),
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime)),
            }
        )
    return out


def save_as(profile: Profile, name: str) -> Path:
    path = profiles_dir() / f"{safe_name(name)}.json"
    if path.exists():
        raise FileExistsError(f"profil {path.stem!r} už existuje")
    save_profile(profile.model_copy(update={"name": path.stem}), path)
    return path


def load(name: str) -> tuple[Profile, Path]:
    path = resolve(name)
    return load_profile(path), path
