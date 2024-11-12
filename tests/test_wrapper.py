"""Tests for ``odiff_py.wrapper``."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import cast

import numpy as np
import pytest
from PIL import Image

from odiff_py.utils import APNG
from odiff_py.utils import CHECKER_TRANSPARENCY_CSS
from odiff_py.utils import load_image
from odiff_py.wrapper import CompareStatus
from odiff_py.wrapper import DiffResult
from odiff_py.wrapper import IgnoreArea
from odiff_py.wrapper import create_ignore_areas_overlay
from odiff_py.wrapper import odiff
from tests import TEST_DATA

if TYPE_CHECKING:
    from pathlib import Path


class DefaultTestArgs(TypedDict):
    """Shape of default test args."""

    base: Path
    comparing: Path


@pytest.fixture
def default_test_args():
    """Return default test args to compare `tiger-1.jpg` and `tiger-2.jpg`."""
    return {"base": TEST_DATA / "tiger-1.jpg", "comparing": TEST_DATA / "tiger-2.jpg"}


def same_image_array(result: Image.Image, expected: Image.Image) -> bool:
    """Check for equality using numpy all close, to be independent of format."""
    return np.allclose(np.asarray(result), np.asarray(expected))


def check_default_result(result: DiffResult):
    """Check default result when comparing `tiger-1.jpg` and `tiger-2.jpg`."""
    assert same_image_array(result.base_image, Image.open(TEST_DATA / "tiger-1.jpg"))
    assert same_image_array(result.comparing_image, Image.open(TEST_DATA / "tiger-2.jpg"))
    assert result.status == CompareStatus.PIXEL_DIFFERENCE
    assert result.diff_pixel_count == 7789
    assert result.diff_percentage == pytest.approx(1.167766)


def test_default(default_test_args: DefaultTestArgs):
    """Using only defaults gives the same result as calling the odiff CLI without extra options."""
    result = odiff(**default_test_args)
    check_default_result(result)
    assert result.diff_lines == []
    assert result.diff_image is not None
    assert same_image_array(result.diff_image, Image.open(TEST_DATA / "tiger-diff.png"))


def test_image_object_input(default_test_args: DefaultTestArgs):
    """Using ``PIL.Image.Image`` for base and comparing image works."""
    result = odiff(
        base=Image.open(default_test_args["base"]),
        comparing=Image.open(default_test_args["comparing"]),
    )
    check_default_result(result)
    assert result.diff_lines == []
    assert result.diff_image is not None
    assert same_image_array(result.diff_image, Image.open(TEST_DATA / "tiger-diff.png"))


def test_write_diff_image_to_disk(default_test_args: DefaultTestArgs, tmp_path: Path):
    """When using a path or str, the diff image is created on disk."""
    diff_path = tmp_path / "diff.png"
    result = odiff(diff=diff_path, **default_test_args)
    check_default_result(result)
    assert result.diff_lines == []
    assert result.diff_image is not None
    assert same_image_array(result.diff_image, Image.open(TEST_DATA / "tiger-diff.png"))
    assert diff_path.is_file() is True
    assert same_image_array(Image.open(diff_path), Image.open(TEST_DATA / "tiger-diff.png"))


def test_output_diff_lines(default_test_args: DefaultTestArgs):
    """When using a path or str, the diff image is created on disk."""
    result = odiff(output_diff_lines=True, **default_test_args)
    check_default_result(result)
    assert result.diff_lines == list(range(13, 187))
    assert result.diff_image is not None
    assert same_image_array(result.diff_image, Image.open(TEST_DATA / "tiger-diff.png"))


@pytest.mark.parametrize(
    "ignore",
    [
        [(0, 0, 1000, 200)],
        [IgnoreArea(0, 0, 1000, 200)],
        [(0, 0, 1000, 100), IgnoreArea(0, 100, 1000, 200)],
    ],
)
def test_ignore_diff_area(
    default_test_args: DefaultTestArgs, ignore: list[IgnoreArea | tuple[int, int, int, int]]
):
    """Image match if the diff area is covered with ignores."""
    result = odiff(ignore=ignore, **default_test_args)
    assert result.status == CompareStatus.IMAGE_MATCH
    assert result.diff_lines == []
    assert result.diff_image is None


def test_diff_mask(default_test_args: DefaultTestArgs):
    """Using the diff mask option generate the diff mask image."""
    result = odiff(diff_mask=True, **default_test_args)
    check_default_result(result)
    assert result.diff_lines == []
    assert result.diff_image is not None
    assert same_image_array(result.diff_image, Image.open(TEST_DATA / "tiger-diff-mask.png"))


def test_reduce_ram_usage(default_test_args: DefaultTestArgs):
    """We can only test that the results are correct and the call doesn't cause a crash."""
    result = odiff(reduce_ram_usage=True, **default_test_args)
    check_default_result(result)


def test_fail_on_layout():
    """Early fail if images have different dimensions."""
    width = 400
    height = 300

    img1 = Image.new(mode="RGB", size=(width, height))
    img2 = Image.new(mode="RGB", size=(height, width))
    result = odiff(img1, img2, fail_on_layout=True)
    assert result.status == CompareStatus.LAYOUT_DIFFERENCE
    assert result.diff_pixel_count is None
    assert result.diff_percentage is None


def test_odiff_cli_error(monkeypatch: pytest.MonkeyPatch, default_test_args: DefaultTestArgs):
    """Runtime error is raised when running odiff fails with non result returncode."""
    import odiff_py.wrapper

    with monkeypatch.context() as m:
        m.setattr(odiff_py.wrapper, "run_odiff", lambda *_args: (404, "", "Random CLI Error"))
        with pytest.raises(RuntimeError) as exec_info:
            odiff(**default_test_args)
    assert str(exec_info.value) == "Error calling odiff executable:\nRandom CLI Error"


def test_diff_result_create_apng(default_test_args: DefaultTestArgs):
    """Create expected ``apng`` file content."""
    result = odiff(diff_mask=True, **default_test_args)
    expected = TEST_DATA / "tiger-compare.apng"
    assert result.create_apng() == APNG.from_file(expected)


def test_result_md_repr_no_diff(default_test_args: DefaultTestArgs):
    """MD repr is as expected."""
    test_args = cast(DefaultTestArgs, default_test_args | {"comparing": TEST_DATA / "tiger-1.jpg"})
    result = odiff(**test_args)
    assert result._repr_markdown_() == "Images are identical."


def test_result_md_repr_on_diff(default_test_args: DefaultTestArgs):
    """MD repr for diff is as expected."""
    result = odiff(diff_mask=True, output_diff_lines=True, **default_test_args)
    expected = (TEST_DATA / "diff-result.md").read_text()
    assert result._repr_markdown_() == expected


def test_result_md_repr_on_diff_checker_board_propagation(default_test_args: DefaultTestArgs):
    """Changing ``use_checker_transparency`` propagates to ``apng``."""
    result = odiff(diff_mask=True, **default_test_args)
    assert CHECKER_TRANSPARENCY_CSS in result._repr_markdown_()
    result.use_checker_transparency = False
    assert CHECKER_TRANSPARENCY_CSS not in result._repr_markdown_()


def test_ignore_areas_in_result(default_test_args: DefaultTestArgs):
    """Ignore areas are in the result and all converted to ``IgnoreArea`` instances."""
    result = odiff(ignore=[IgnoreArea(x1=1, y1=2, x2=3, y2=4), (5, 6, 7, 8)], **default_test_args)
    assert result.ignore_areas == [
        IgnoreArea(x1=1, y1=2, x2=3, y2=4),
        IgnoreArea(x1=5, y1=6, x2=7, y2=8),
    ]


def test_create_ignore_areas_overlay_noop():
    """If no ignore areas are provided the overlay is ``None``."""
    assert create_ignore_areas_overlay(Image.new("RGB", (1, 1)), []) is None


def test_create_ignore_areas_overlay(default_test_args: DefaultTestArgs):
    """Basic overlay is as expected."""
    overlay = create_ignore_areas_overlay(
        load_image(default_test_args["base"]),
        [IgnoreArea(600, 0, 880, 100), IgnoreArea(580, 20, 890, 200)],
    )
    assert overlay is not None
    expected = TEST_DATA / "overlay_red.png"
    diff_result = odiff(expected, overlay)
    assert diff_result.status == CompareStatus.IMAGE_MATCH


def test_ignore_areas_on_result_images(default_test_args: DefaultTestArgs):
    """Only when the ``show_ignore_areas_overlay`` is ``True`` the ignore area overlay is shown.

    Main goal is to verify that showing the overlay does not mutate the original image.
    """
    ignore_areas = [IgnoreArea(580, 20, 890, 200)]
    overlay = create_ignore_areas_overlay(
        load_image(default_test_args["base"]),
        ignore_areas,
    )
    assert overlay is not None
    diff_result = odiff(ignore=ignore_areas, diff_mask=True, **default_test_args)
    assert diff_result.diff_image
    assert diff_result.show_ignore_areas_overlay is True
    assert diff_result.status == CompareStatus.PIXEL_DIFFERENCE

    diff_result.show_ignore_areas_overlay = False
    original_diff_image = copy(diff_result.diff_image)

    assert (
        odiff(diff_result.base_image, load_image(default_test_args["base"])).status
        == CompareStatus.IMAGE_MATCH
    )
    assert (
        odiff(diff_result.comparing_image, load_image(default_test_args["comparing"])).status
        == CompareStatus.IMAGE_MATCH
    )
    odiff(diff_result.diff_image, original_diff_image).create_apng().save("fail.apng")
    assert odiff(diff_result.diff_image, original_diff_image).status == CompareStatus.IMAGE_MATCH

    diff_result.show_ignore_areas_overlay = True
    expected_base = copy(diff_result.base_image)
    expected_base.paste(overlay, (0, 0), overlay)
    assert (
        odiff(diff_result.base_image, expected_base, threshold=0.2).status
        == CompareStatus.IMAGE_MATCH
    )

    expected_compare = copy(diff_result.comparing_image)
    expected_compare.paste(overlay, (0, 0), overlay)
    assert (
        odiff(diff_result.comparing_image, expected_compare, threshold=0.2).status
        == CompareStatus.IMAGE_MATCH
    )

    expected_diff = copy(diff_result.diff_image)
    expected_diff.paste(overlay, (0, 0), overlay)
    assert odiff(diff_result.diff_image, expected_diff).status == CompareStatus.IMAGE_MATCH

    diff_result.show_ignore_areas_overlay = False
    assert (
        odiff(diff_result.base_image, load_image(default_test_args["base"])).status
        == CompareStatus.IMAGE_MATCH
    )
    assert (
        odiff(diff_result.comparing_image, load_image(default_test_args["comparing"])).status
        == CompareStatus.IMAGE_MATCH
    )
    assert odiff(diff_result.diff_image, original_diff_image).status == CompareStatus.IMAGE_MATCH
