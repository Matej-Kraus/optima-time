"""SPEC 15.4 in short: a vMix-like reader never sees broken or incomplete XML, and the writer
finishes after collisions (Windows locking emulated)."""

import subprocess
import sys
from pathlib import Path


def test_reader_never_sees_broken_xml(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "tools.xml_reader_sim",
        "--with-writer",
        "--emulate-lock",
        "--minutes",
        "0.06",
        "--hold",
        "40",
        "--rate",
        "20",
        "--path",
        str(tmp_path / "t.xml"),
    ]
    run = subprocess.run(
        cmd, capture_output=True, text=True, timeout=60, cwd=Path(__file__).resolve().parents[1]
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert '"failures": 0' in run.stdout and '"final_file_is_last_values": true' in run.stdout
