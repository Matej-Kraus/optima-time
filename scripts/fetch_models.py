"""Download the PP-OCRv6 rec ONNX models at pinned revisions (build time only, SPEC 10.2).

Writes models/ppocr/<tiny|small>/:
  inference.onnx   the model, checked against its pinned SHA-256
  characters.txt   the model's character list, one per line (from inference.yml)
  config.json      the input the model expects (height, minimum width, channel order)

So the app needs no YAML parser and never downloads anything at run time.
Pinned revisions: docs/DECISIONS.md D3.

Usage: uv run python scripts/fetch_models.py [--dest models/ppocr]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

MODELS = {
    "tiny": {
        "repo": "PaddlePaddle/PP-OCRv6_tiny_rec_onnx",
        "revision": "2612ab37152ae0a677521bae4e1e3d4fb4cf7c30",
        "inference.onnx": "9ef676d6ed3c88256a2d92c640c44f25b0c40947e111b14b8be8f594091563e6",
        "inference.yml": "66170210bad538e83fff3c4a3867e547d6bf20b50d64b20347c4b913f3034ea1",
        "characters": 6904,
    },
    "small": {
        "repo": "PaddlePaddle/PP-OCRv6_small_rec_onnx",
        "revision": "b8f84f0b80c529de40b4fbb3544b84fa7233a513",
        "inference.onnx": "5435fd747c9e0efe15a96d0b378d5bd157e9492ed8fd80edf08f30d02fa24634",
        "inference.yml": "ab078671bb49f06228eadccd34f1bb501e157f7a047095ffb943ba81512c77d1",
        "characters": 18708,
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path, sha256: str) -> None:
    if target.exists() and sha256_of(target) == sha256:
        return
    print(f"downloading {url}")
    partial = target.with_suffix(target.suffix + ".part")
    urllib.request.urlretrieve(url, partial)
    actual = sha256_of(partial)
    if actual != sha256:
        partial.unlink()
        raise SystemExit(f"{target}: SHA-256 mismatch {actual} != {sha256}")
    partial.replace(target)


def convert(yml: Path, folder: Path, expected_chars: int) -> None:
    with yml.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    characters = config["PostProcess"]["character_dict"]
    if len(characters) != expected_chars or not all(isinstance(c, str) and c for c in characters):
        raise SystemExit(f"{yml}: unexpected character list ({len(characters)} entries)")
    if any("\n" in c for c in characters):
        raise SystemExit(f"{yml}: a character contains a newline")
    shape, mode = [3, 48, 320], "BGR"
    for op in config["PreProcess"]["transform_ops"]:
        if "RecResizeImg" in op:
            shape = op["RecResizeImg"]["image_shape"]
        if "DecodeImage" in op:
            mode = op["DecodeImage"].get("img_mode", "BGR")
    (folder / "characters.txt").write_bytes(("\n".join(characters) + "\n").encode("utf-8"))
    meta = {
        "model_name": config["Global"]["model_name"],
        "image_height": int(shape[1]),
        "min_width": int(shape[2]),
        "channel_order": mode,
    }
    (folder / "config.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")


def fetch(name: str, dest: Path) -> Path:
    spec = MODELS[name]
    folder = dest / name
    folder.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}"
    for filename in ("inference.onnx", "inference.yml"):
        download(f"{base}/{filename}", folder / filename, str(spec[filename]))
    convert(folder / "inference.yml", folder, int(spec["characters"]))
    return folder


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=ROOT / "models" / "ppocr")
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    args = parser.parse_args()
    for name in args.models:
        print(f"{name}: ok -> {fetch(name, args.dest)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
