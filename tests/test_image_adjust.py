import numpy as np

from optima_time.config.models import ImageConfig, Profile
from optima_time.preprocess import ImageAdjust, adjust_lut


def test_neutral_settings_leave_the_image_alone() -> None:
    img = np.random.default_rng(1).integers(0, 255, (20, 30, 3), dtype=np.uint8)
    assert ImageAdjust(ImageConfig())(img) is img
    assert np.array_equal(adjust_lut(ImageConfig()), np.arange(256))


def test_brightness_contrast_gamma_invert() -> None:
    assert adjust_lut(ImageConfig(brightness=100))[0] == 128  # +half the range
    assert adjust_lut(ImageConfig(brightness=-100))[255] == 128
    lut = adjust_lut(ImageConfig(contrast=2.0))
    assert lut[64] < 64 and lut[192] > 192 and abs(int(lut[128]) - 128) <= 1
    assert adjust_lut(ImageConfig(gamma=2.0))[64] > 64  # brightens dark tones
    inv = adjust_lut(ImageConfig(invert=True))
    assert inv[0] == 255 and inv[255] == 0


def test_net_removal_fills_thin_dark_lines() -> None:
    img = np.full((40, 40, 3), 220, np.uint8)
    img[:, 20] = 10  # a 1-px dark net strand across a lit digit
    out = ImageAdjust(ImageConfig(net_removal=1))(img)
    assert out[:, 20].min() > 200
    assert out.shape == img.shape and out.dtype == np.uint8


def test_sharpen_keeps_shape_and_old_profiles_load() -> None:
    img = np.zeros((30, 30, 3), np.uint8)
    img[10:20, 10:20] = 200
    out = ImageAdjust(ImageConfig(sharpen=1.0))(img)
    assert out.shape == img.shape and out[15, 15, 0] >= 200
    p = Profile.model_validate({"name": "old"})  # a profile from before ImageConfig
    assert p.image == ImageConfig()
