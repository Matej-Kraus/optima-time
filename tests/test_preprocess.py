import cv2
import numpy as np

from optima_time.config.models import Deinterlace
from optima_time.preprocess import contrast, deinterlace, gray_max


def test_gray_max_keeps_red_and_blue_leds_bright() -> None:
    img = np.zeros((2, 2, 3), np.uint8)
    img[0, 0] = (0, 0, 255)  # red
    img[0, 1] = (255, 0, 0)  # blue
    gray = gray_max(img)
    assert gray[0, 0] == 255 and gray[0, 1] == 255
    luma = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    assert luma[0, 1] < 40  # what luma would do to a blue LED


def lit_digits() -> np.ndarray:
    img = np.zeros((60, 120, 3), np.uint8)
    cv2.putText(img, "12", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (40, 255, 40), 5)
    return img


def test_contrast_lit_vs_unlit_vs_blown() -> None:
    assert contrast(lit_digits()) > 150
    unlit = np.random.default_rng(0).integers(5, 25, (60, 120, 3)).astype(np.uint8)
    assert contrast(unlit) < 40
    blown = np.full((60, 120, 3), 250, np.uint8)
    assert contrast(blown) < 10


def test_contrast_on_large_crop_is_downscaled_but_similar() -> None:
    big = np.asarray(
        cv2.resize(lit_digits(), (1200, 600), interpolation=cv2.INTER_NEAREST), np.uint8
    )
    assert abs(contrast(big) - contrast(lit_digits())) < 40


def combed() -> np.ndarray:
    frame = np.zeros((8, 4, 3), np.uint8)
    frame[::2] = 200  # even field lit, odd field dark: maximal combing
    return frame


def test_deinterlace_none_is_identity() -> None:
    f = combed()
    assert deinterlace(f, Deinterlace.NONE) is f


def test_deinterlace_blend_and_bob_remove_combing() -> None:
    for mode in (Deinterlace.BLEND, Deinterlace.BOB):
        out = deinterlace(combed(), mode)
        assert out.shape == combed().shape
        rows = out[:-1, 0, 0].astype(int)
        assert np.abs(np.diff(rows)).max() < 120, mode


def test_frame_blender_max_keeps_flickering_leds_lit() -> None:
    from optima_time.config.models import BlendMode
    from optima_time.preprocess import FrameBlender

    lit = np.full((4, 4, 3), 200, np.uint8)
    dark = np.full((4, 4, 3), 20, np.uint8)
    blend = FrameBlender(3, BlendMode.MAX)
    outs = [blend(f) for f in (lit, dark, dark, dark, lit)]
    assert outs[1].min() == 200 and outs[2].min() == 200  # the lit frame is still in the window
    assert outs[3].max() == 20  # three dark frames in a row
    assert outs[4].min() == 200


def test_frame_blender_mean_and_off() -> None:
    from optima_time.config.models import BlendMode
    from optima_time.preprocess import FrameBlender

    a, b = np.full((2, 2, 3), 100, np.uint8), np.full((2, 2, 3), 200, np.uint8)
    blend = FrameBlender(2, BlendMode.MEAN)
    blend(a)
    assert int(blend(b)[0, 0, 0]) == 150
    off = FrameBlender(1, BlendMode.MAX)
    assert off(a) is a
    blend(np.zeros((3, 3, 3), np.uint8))  # a new size resets the window without errors
