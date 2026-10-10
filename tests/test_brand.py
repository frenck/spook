"""Tests for the brand images Spook and its helpers carry along."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from homeassistant.components.brands.const import ALLOWED_IMAGES

SPOOK = Path(__file__).parents[1] / "custom_components" / "spook"

# Spook itself, and every helper that shows up as an integration of its own.
BRAND_DIRECTORIES = [
    SPOOK / "brand",
    *(
        SPOOK / "integrations" / helper / "brand"
        for helper in ("spook_calibration", "spook_inverse", "spook_time_in_state")
    ),
]

# What Home Assistant's brands guidelines ask for: a square icon, and a logo
# whose shortest side is the size the name says, both twice for @2x.
_ICON_SIZES = {"icon.png": 256, "icon@2x.png": 512}
_LOGO_HEIGHTS = {"logo.png": 128, "logo@2x.png": 256}


@pytest.mark.parametrize(
    "directory", BRAND_DIRECTORIES, ids=lambda path: path.parent.name
)
def test_every_image_is_there_in_both_themes(directory: Path) -> None:
    """Test a full set, light and dark, of names Home Assistant serves."""
    names = {path.name for path in directory.iterdir()}

    assert names == set(ALLOWED_IMAGES)


@pytest.mark.parametrize("theme", ["", "dark_"])
def test_icons_are_square_and_sized(theme: str) -> None:
    """Test the icons are the size the guidelines ask for."""
    for name, size in _ICON_SIZES.items():
        with Image.open(SPOOK / "brand" / f"{theme}{name}") as image:
            assert image.size == (size, size), name
            assert image.mode == "RGBA", name


@pytest.mark.parametrize("theme", ["", "dark_"])
def test_logos_are_sized(theme: str) -> None:
    """Test the logos are as tall as the guidelines ask for."""
    for name, height in _LOGO_HEIGHTS.items():
        with Image.open(SPOOK / "brand" / f"{theme}{name}") as image:
            assert image.height == height, name
            assert image.width > height, name
            assert image.mode == "RGBA", name


@pytest.mark.parametrize("theme", ["", "dark_"])
def test_the_background_is_see_through(theme: str) -> None:
    """Test no image brings a background of its own to either theme."""
    for name in (*_ICON_SIZES, *_LOGO_HEIGHTS):
        with Image.open(SPOOK / "brand" / f"{theme}{name}") as image:
            assert image.getpixel((0, 0))[3] == 0, name
