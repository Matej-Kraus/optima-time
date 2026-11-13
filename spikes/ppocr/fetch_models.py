"""Spike A: download the PP-OCRv6 rec ONNX models at pinned revisions and check SHA-256.

One-off experiment (Milestone 0). The product gets its own scripts/fetch_models.py.
Pinned revisions and hashes: docs/DECISIONS.md (D3); the same ones ScoreSight measured.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"

MODELS = {
    "tiny": {
        "repo": "PaddlePaddle/PP-OCRv6_tiny_rec_onnx",
        "revision": "2612ab37152ae0a677521bae4e1e3d4fb4cf7c30",
        "inference.onnx": "9ef676d6ed3c88256a2d92c640c44f25b0c40947e111b14b8be8f594091563e6",
        "inference.yml": "66170210bad538e83fff3c4a3867e547d6bf20b50d64b20347c4b913f3034ea1",
    },
    "small": {
        "repo": "PaddlePaddle/PP-OCRv6_small_rec_onnx",
        "revision": "b8f84f0b80c529de40b4fbb3544b84fa7233a513",
        "inference.onnx": "5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634",
        "inference.yml": "ab078671bb49f06228eadccd34f1bb501e157f7a047095ffb943ba81512c77d1",
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(name: str) -> Path:
    spec = MODELS[name]
    folder = MODELS_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    for filename in ("inference.onnx", "inference.yml"):
        target = folder / filename
        expected = spec[filename]
        if target.exists() and sha256_of(target) == expected:
            continue
        url = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{filename}"
        print(f"downloading {url}")
        partial = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(url, partial)
        actual = sha256_of(partial)
        if actual != expected:
            partial.unlink()
            raise SystemExit(f"{name}/{filename}: SHA-256 mismatch {actual} != {expected}")
        partial.replace(target)
    return folder


def main() -> int:
    for name in MODELS:
        print(f"{name}: ok -> {fetch(name)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
