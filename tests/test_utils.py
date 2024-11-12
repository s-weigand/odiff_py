"""Tests for ``odiff_py.utils``."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from odiff_py.utils import APNG
from odiff_py.utils import load_image
from odiff_py.utils import png_images_to_apng_bytes
from odiff_py.utils import run_odiff
from tests import TEST_DATA

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="session")
def diff_images() -> list[Image.Image]:
    """List of images to create an APN for testing."""
    return [
        Image.open(TEST_DATA / "tiger-1.jpg"),
        Image.open(TEST_DATA / "tiger-2.jpg"),
        Image.open(TEST_DATA / "tiger-diff-mask.png"),
    ]


def test_run_odiff():
    """Happy path getting version."""
    returncode, stdout, stderr = run_odiff("--version")
    assert returncode == 0
    assert stdout.rstrip() == "3.1.1"
    assert stderr == ""


def test_run_odiff_bad_option():
    """Get error message if command fails."""
    returncode, stdout, stderr = run_odiff("--unknown")
    assert returncode == 124
    assert stdout.rstrip() == ""
    assert stderr.startswith("odiff: unknown option '--unknown'")


def test_png_images_to_apng_bytes(tmp_path: Path, diff_images: list[Image.Image]):
    """Create expected ``apng`` file content."""
    apng_bytes = png_images_to_apng_bytes(diff_images)
    expected = (TEST_DATA / "tiger-compare.apng").read_bytes()
    assert apng_bytes == expected

    out_file = tmp_path / "animated.apng"
    png_images_to_apng_bytes([*diff_images, None], out_file=out_file)
    assert out_file.read_bytes() == expected


def test_apng_from_images(diff_images: list[Image.Image]):
    """Create APNG instance from PIL images."""
    expected = (TEST_DATA / "tiger-compare.apng").read_bytes()
    assert APNG.from_images(diff_images).data == expected


def test_apng_from_images_with_overlay(diff_images: list[Image.Image]):
    """Creating APNG with overlay is the same as creating from an image with overlay."""
    overlay = load_image(TEST_DATA / "overlay_red.png")
    diff_image = copy(diff_images[0])
    diff_image.paste(overlay, (0, 0), overlay)

    expected = png_images_to_apng_bytes([diff_image])

    assert APNG.from_images([diff_images[0], None], overlay_image=overlay).data == expected


def test_apng_from_file():
    """Load APNG instance from apng file."""
    expected_file = TEST_DATA / "tiger-compare.apng"
    assert APNG.from_file(expected_file).data == expected_file.read_bytes()


def test_apng_save(tmp_path: Path):
    """Roundtrip existing apng file."""
    test_file = tmp_path / "animated.apng"
    expected_file = TEST_DATA / "tiger-compare.apng"
    APNG.from_file(expected_file).save(test_file)
    assert test_file.read_bytes() == expected_file.read_bytes()


def test_apng_repr():
    """Test both the string and jupter repr."""
    _, _, expected = (TEST_DATA / "diff-result.md").read_text().partition("<br>")
    diff_apng = APNG.from_file(TEST_DATA / "tiger-compare.apng")
    assert f"{diff_apng}" == expected.rstrip()
    assert diff_apng._repr_markdown_() == expected.rstrip()
