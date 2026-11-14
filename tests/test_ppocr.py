import cv2
import numpy as np
import pytest

from optima_time.recognizers.base import Crop
from optima_time.recognizers.ppocr import (
    PPOCRRecognizer,
    class_groups,
    ctc_greedy,
    models_dir,
    padded_width,
    resize_normalize,
)

LABELS = ["", "1", "2", ":", "a"]


def onehot(seq: list[int], classes: int = 5) -> np.ndarray:
    probs = np.full((len(seq), classes), 0.01, np.float32)
    for t, c in enumerate(seq):
        probs[t, c] = 0.96
    return probs


def test_ctc_merges_repeats_and_drops_blanks() -> None:
    text, confs = ctc_greedy(onehot([0, 1, 1, 0, 1, 3, 3, 2, 0]), LABELS)
    assert text == "11:2"
    assert len(confs) == 4


def test_ctc_empty() -> None:
    assert ctc_greedy(onehot([0, 0, 0]), LABELS) == ("", [])


def test_whitelist_removes_disallowed_class() -> None:
    probs = onehot([0, 4, 0])  # "a" wins without a whitelist
    probs[1, 1] = 0.5  # "1" is second
    groups = class_groups(LABELS, "12:")
    text, _ = ctc_greedy(groups.reduce(probs), groups.labels)
    assert text == "1"


def test_whitelist_groups_nfkc_equivalents() -> None:
    labels = ["", "1", "１", "2"]  # noqa: RUF001 - "1" and full-width "1"
    groups = class_groups(labels, "12")
    assert groups.labels == ["", "1", "2"]
    probs = np.array([[0.1, 0.3, 0.3, 0.3]], np.float32)  # "1" variants sum to 0.6
    assert ctc_greedy(groups.reduce(probs), groups.labels)[0] == "1"


def test_class_groups_without_allowed_chars_fails() -> None:
    with pytest.raises(ValueError):
        class_groups(LABELS, "xyz")


def test_resize_normalize_range_and_padding() -> None:
    img = np.full((24, 24, 3), 255, np.uint8)
    out = resize_normalize(img, 48, 160)
    assert out.shape == (3, 48, 160)
    assert np.allclose(out[:, :, :48], 1.0)
    assert np.allclose(out[:, :, 48:], 0.0)


def test_padded_width() -> None:
    assert padded_width(48, 48, 48, 160) == 160
    assert padded_width(48, 400, 48, 160) == 400


needs_models = pytest.mark.skipif(
    not (models_dir() / "tiny" / "inference.onnx").exists(),
    reason="models not fetched (scripts/fetch_models.py)",
)


def text_crop(text: str, color: tuple[int, int, int], width: int) -> np.ndarray:
    img = np.zeros((70, width, 3), np.uint8)
    cv2.putText(img, text, (8, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.8, color, 5)
    return img


@needs_models
def test_reads_clock_and_single_digit() -> None:
    rec = PPOCRRecognizer("tiny", threads=1)
    readings = rec.read(
        [
            Crop(text_crop("12:45", (40, 255, 40), 240), "0123456789:.", 160),
            Crop(text_crop("7", (255, 230, 20), 60), "0123456789", 160),
            Crop(np.zeros((70, 60, 3), np.uint8), "0123456789", 160),
        ]
    )
    assert [r.text for r in readings] == ["12:45", "7", ""]
    assert readings[0].confidence > 0.9
    assert readings[2].confidence == 0.0


@needs_models
def test_reading_does_not_depend_on_batch() -> None:
    rec = PPOCRRecognizer("tiny", threads=1)
    crop = Crop(text_crop("3", (255, 230, 20), 60), "0123456789", 160)
    other = Crop(text_crop("88:88", (40, 255, 40), 260), "0123456789:", 160)
    alone = rec.read([crop])[0]
    together = rec.read([other, crop])[1]
    assert (alone.text, round(alone.confidence, 5)) == (
        together.text,
        round(together.confidence, 5),
    )
