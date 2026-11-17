import functools
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import pytest

from optima_time.config.models import Profile, SourceConfig
from optima_time.runner import make_source
from optima_time.sources.base import SourceState
from optima_time.sources.stream import StreamSource, check_url, safe_url


def test_url_checks() -> None:
    assert check_url("  srt://10.0.0.5:9000?mode=caller ") == "srt://10.0.0.5:9000?mode=caller"
    with pytest.raises(ValueError):
        check_url("C:/video.mp4")
    assert safe_url("rtsp://admin:tajne@10.0.0.9:554/s1") == "rtsp://***@10.0.0.9:554/s1"
    assert safe_url("srt://10.0.0.5:9000") == "srt://10.0.0.5:9000"


def test_profile_builds_a_stream_source() -> None:
    p = Profile(source=SourceConfig(type="stream", url="udp://0.0.0.0:5000"))
    assert isinstance(make_source(p), StreamSource)
    assert make_source(Profile(source=SourceConfig(type="stream"))) is None


def test_reads_frames_from_an_http_stream(tmp_path: Path) -> None:
    video = tmp_path / "board.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter.fourcc(*"mp4v"), 25, (160, 90))
    for i in range(50):
        frame = np.zeros((90, 160, 3), np.uint8)
        cv2.putText(frame, str(i % 10), (60, 70), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
        writer.write(frame)
    writer.release()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    src = StreamSource(f"http://127.0.0.1:{server.server_address[1]}/board.mp4")
    try:
        src.open()
        frame = src.read_latest(timeout=10)
        assert frame is not None and frame.image.shape == (90, 160, 3)
        assert src.state is SourceState.OK
    finally:
        src.close()
        server.shutdown()


def test_unreachable_stream_reports_lost_not_hangs() -> None:
    src = StreamSource("rtsp://127.0.0.1:1/none")
    src.open()
    deadline = time.monotonic() + 15
    while src.state is SourceState.CONNECTING and time.monotonic() < deadline:
        time.sleep(0.1)
    src.close()
    assert src.state is not SourceState.OK
