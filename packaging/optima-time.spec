# PyInstaller spec: one folder with two programs (SPEC 7.1, 14.2).
#   OptimaTime.exe   no console window, tray icon; double-click starts the last profile
#   optima-time.exe  with a console: command line, --self-test
# Build: scripts/build_windows.ps1 (Windows) or
#   uv run pyinstaller packaging/optima-time.spec --noconfirm --distpath build/dist --workpath build/work
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (defined by PyInstaller)
MODELS = ROOT / "models" / "ppocr"
UI = ROOT / "frontend" / "dist"
if not (MODELS / "tiny" / "inference.onnx").exists():
    raise SystemExit("models missing: uv run python scripts/fetch_models.py")
if not (UI / "index.html").exists():
    raise SystemExit("UI not built: cd frontend; npm ci; npm run build")

datas = [(str(UI), "frontend/dist")]
for model in ("tiny", "small"):
    for name in ("inference.onnx", "characters.txt", "config.json"):
        f = MODELS / model / name
        if f.exists():
            datas.append((str(f), f"models/ppocr/{model}"))
binaries = []
hiddenimports = collect_submodules("optima_time") + collect_submodules("uvicorn")
for package in ("cyndilib", "onnxruntime", "cv2_enumerate_cameras"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
if sys.platform == "win32":
    hiddenimports += ["pystray._win32"]

a = Analysis(  # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest", "tools", "spikes", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

gui = EXE(  # noqa: F821
    pyz, a.scripts, [], exclude_binaries=True, name="OptimaTime", console=False,
)
cli = EXE(  # noqa: F821
    pyz, a.scripts, [], exclude_binaries=True, name="optima-time", console=True,
)
COLLECT(gui, cli, a.binaries, a.datas, name="OptimaTime")  # noqa: F821
