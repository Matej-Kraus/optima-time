import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from optima_time.imageio import read_image, write_image
from optima_time.sources.base import SourceState
from optima_time.sources.file import FileSource


def write_video(path: Path, frames: int = 20, fps: int = 25) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), fps, (64, 48))
    for i in range(frames):
        img = np.full((48, 64, 3), i * 10, np.uint8)  # brightness encodes the frame number
        writer.write(img)
    writer.release()


@pytest.fixture
def video(tmp_path: Path) -> Path:
    path = tmp_path / "v.mp4"
    write_video(path)
    return path


def test_fast_mode_reads_every_frame_then_ends(video: Path) -> None:
    with FileSource(video, loop=False, speed=0) as src:
        frames = []
        while (f := src.read_latest()) is not None:
            frames.append(f)
        assert len(frames) == 20
        assert [f.seq for f in frames] == list(range(1, 21))
        assert frames[5].pts == pytest.approx(5 / 25)
        assert src.state is SourceState.ENDED
        assert src.info.width == 64 and src.info.height == 48
        assert src.stats.dropped == 0


def test_fast_mode_loops(video: Path) -> None:
    with FileSource(video, loop=True, speed=0) as src:
        frames = [src.read_latest() for _ in range(45)]
        assert all(f is not None for f in frames)
        assert frames[20] is not None and frames[20].pts == 0.0


def test_seek(video: Path) -> None:
    with FileSource(video, loop=False, speed=0) as src:
        src.seek(0.4)  # frame 10
        f = src.read_latest()
        assert f is not None
        assert abs(int(f.image.mean()) - 100) < 8


def test_realtime_mode_latest_wins(video: Path) -> None:
    with FileSource(video, loop=True, speed=4.0) as src:  # 100 fps
        first = src.read_latest(timeout=2)
        assert first is not None
        time.sleep(0.2)  # ~20 frames come in, we read none
        second = src.read_latest(timeout=2)
        assert second is not None and second.seq > first.seq  # skipped ahead, not next in line
        assert src.stats.dropped > 0


def test_image_source(tmp_path: Path) -> None:
    path = tmp_path / "board.png"
    write_image(str(path), np.full((30, 40, 3), 77, np.uint8))
    with FileSource(path, speed=0) as src:
        f1, f2 = src.read_latest(), src.read_latest()
        assert f1 is not None and f2 is not None
        assert f2.seq == f1.seq + 1 and f1.image.shape == (30, 40, 3)


def test_image_source_non_ascii_path(tmp_path: Path) -> None:
    # cv2.imread / imwrite fail on such paths on Windows (e.g. C:\Users\Matěj\...)
    folder = tmp_path / "Matěj žluťoučký"
    folder.mkdir()
    path = folder / "tabule.png"
    assert write_image(path, np.full((30, 40, 3), 77, np.uint8))
    with FileSource(path, speed=0) as src:
        frame = src.read_latest()
        assert frame is not None and frame.image.shape == (30, 40, 3)
        assert int(frame.image[0, 0, 0]) == 77


def test_read_image_missing_or_not_an_image(tmp_path: Path) -> None:
    assert read_image(tmp_path / "nope.png") is None
    (tmp_path / "bad.png").write_bytes(b"not an image")
    assert read_image(tmp_path / "bad.png") is None


def test_missing_file(tmp_path: Path) -> None:
    src = FileSource(tmp_path / "nope.mp4")
    with pytest.raises(FileNotFoundError):
        src.open()
    assert src.state is SourceState.LOST
