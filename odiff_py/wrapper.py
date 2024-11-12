"""Module containing the odiff wrapper functionality."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from typing import Iterable
from typing import NamedTuple

from PIL import Image
from PIL import ImageDraw
from PIL.ImageColor import getrgb

from odiff_py.utils import APNG
from odiff_py.utils import load_image
from odiff_py.utils import run_odiff


class CompareStatus(Enum):
    """Odiff comparison status result."""

    IMAGE_MATCH = 0
    LAYOUT_DIFFERENCE = 21
    PIXEL_DIFFERENCE = 22


class IgnoreArea(NamedTuple):
    """Container for odiff ignore are definitions."""

    x1: int
    y1: int
    x2: int
    y2: int

    def to_region_str(self) -> str:
        """Format to odiff CLI argument.

        Returns
        -------
        str
        """
        return f"{self.x1}:{self.y1}-{self.x2}:{self.y2}"


def create_ignore_areas_overlay(
    original_image: Image.Image,
    ignore_areas: list[IgnoreArea],
    color: str = "red",
    *,
    fill: float = 0.2,
) -> Image.Image | None:
    """Create transparent overlay showing the ignore areas.

    Parameters
    ----------
    original_image : Image.Image
        Original image to create the overlay for.
    ignore_areas : list[IgnoreArea]
        Ignore areas to create an overlay for. The order determines which element is on top.
        Top elements overwrite intersecting parts of bottom elements. The order of importance is
        descending.
    color : str
        Border and fill color for ignore are elements, where the border color is taken as is and
        the opacity of fillcolor is taken from the ``fill`` argument. Defaults to "red"
    fill : float
        Opacity of the ignore area filling. Defaults to 0.2

    Returns
    -------
    Image.Image | None
    """
    if len(ignore_areas) == 0:
        return None
    overlay = Image.new("RGBA", original_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    border_color = getrgb(color)
    fill_color = (*border_color[:3], int(255 * fill))
    for ignore_area in reversed(ignore_areas):
        draw.rectangle(ignore_area, fill=fill_color if fill != 0 else None, outline=color, width=2)
    return overlay


@dataclass
class DiffResult:
    """Result container for odiff comparison."""

    base_image: Image.Image
    comparing_image: Image.Image
    diff_image: Image.Image | None
    status: CompareStatus
    diff_pixel_count: int | None
    diff_percentage: float | None
    diff_lines: list[int]
    ignore_areas: list[IgnoreArea]
    use_checker_transparency: bool = True
    show_ignore_areas_overlay: bool = True

    def create_apng(
        self,
        *,
        delay_num: int = 500,
        delay_den: int = 1000,
        color: str = "red",
        fill: float = 0.2,
    ) -> APNG:
        """Create an apng from the images and their diff if there is any.

        Parameters
        ----------
        delay_num : int
            The delay numerator for frames. Defaults to 500
        delay_den : int
            The delay denominator for frames. Defaults to 1000
        color : str
            Border and fill color for ignore area elements, where the border color is taken as is
            and the opacity of fillcolor is taken from the ``fill`` argument. Defaults to "red"
        fill : float
            Opacity of the ignore area filling. Defaults to 0.2

        Returns
        -------
        APNG
        """
        images = [self.base_image, self.comparing_image, self.diff_image]
        return APNG.from_images(
            images,
            delay_num=delay_num,
            delay_den=delay_den,
            overlay_image=self.create_ignore_areas_overlay(color=color, fill=fill)
            if self.show_ignore_areas_overlay is True
            else None,
        )

    def create_ignore_areas_overlay(
        self, color: str = "red", fill: float = 0.2
    ) -> Image.Image | None:
        """Create ignore area overlay based on ``ignore_areas`` and ``base_image``.

        Parameters
        ----------
        color : str
            Border and fill color for ignore area elements, where the border color is taken as is
            and the opacity of fillcolor is taken from the ``fill`` argument. Defaults to "red"
        fill : float
            Opacity of the ignore area filling. Defaults to 0.2

        Returns
        -------
        Image.Image | None
        """
        return create_ignore_areas_overlay(
            self.base_image, self.ignore_areas, color=color, fill=fill
        )

    def _repr_markdown_(self) -> str:  # noqa:DOC
        """Magic method for rendering automatically in jupyter notebooks."""
        if self.status == CompareStatus.IMAGE_MATCH:
            return "Images are identical."
        result_lines = [
            "|Meaning|Value|",
            "|-------|-----|",
            f"|Status|{self.status.name.replace('_',' ').capitalize()}|",
            f"|Diff Pixel Count|{self.diff_pixel_count}|",
            f"|Diff Percentage|{self.diff_percentage:.2f}%|",
        ]
        if len(self.diff_lines) > 0:
            result_lines.append(f"|Diff Lines|{self.diff_lines}|")
        apng = self.create_apng()
        apng.use_checker_transparency = self.use_checker_transparency
        result_lines.append(f"\n<br>{apng}\n")
        return "\n".join(result_lines)

    def __getattribute__(self, name: str) -> Any:  # noqa: DOC
        """Get instance attributes."""
        attr = super().__getattribute__(name)
        if (
            name
            in {
                "base_image",
                "comparing_image",
                "diff_image",
            }
            and len(self.ignore_areas) != 0
            and self.show_ignore_areas_overlay is True
            and isinstance(attr, Image.Image)
        ):
            base_image = attr if name == "base_image" else self.base_image
            ignore_areas_overlay = create_ignore_areas_overlay(base_image, self.ignore_areas)
            assert ignore_areas_overlay is not None
            attr = copy(attr)
            attr.paste(ignore_areas_overlay, (0, 0), ignore_areas_overlay)
            return attr
        return attr


def _odiff(  # noqa: C901
    tmp_dir: Path,
    base: str | Path | Image.Image,
    comparing: str | Path | Image.Image,
    diff: str | Path | None = None,
    *,
    antialiasing: bool = False,
    diff_color: str = "#FF0000",
    diff_mask: bool = False,
    fail_on_layout: bool = False,
    ignore: Iterable[IgnoreArea | tuple[int, int, int, int]] | None = None,
    output_diff_lines: bool = False,
    reduce_ram_usage: bool = False,
    threshold: float = 0.1,
) -> DiffResult:
    """Run odiff in a temp directory.

    Parameters
    ----------
    tmp_dir : Path
        Temp dir to run odiff in.
    base : str | Path | Image.Image
        Base image.
    comparing : str | Path | Image.Image
        Comparing image.
    diff : str | Path | None
        _description_. Defaults to None
    antialiasing : bool
        With this flag enabled, antialiased pixels are not counted to the diff of an image.
        Defaults to False
    diff_color : str
        Color used to highlight different pixels in the output (in hex format e.g. #cd2cc9).
        Defaults to "#FF0000"
    diff_mask : bool
        Output only changed pixel over transparent background. Defaults to False
    fail_on_layout : bool
        Do not compare images and produce output if images layout is different. Defaults to False
    ignore : Iterable[IgnoreArea  |  tuple[int, int, int, int]] | None
        An array of regions to ignore in the diff. Defaults to None
    output_diff_lines : bool
        With this flag enabled, output result in case of different images will output lines for
        all the different pixels. Defaults to False
    reduce_ram_usage : bool
        With this flag enabled odiff will use less memory, but will be slower in some cases.
        Defaults to False
    threshold : float
        Color difference threshold (from 0 to 1). Less more precise. Defaults to 0.1

    Returns
    -------
    DiffResult

    Raises
    ------
    RuntimeError
        If odiff throws an unexpected error.
    """
    cli_args = ["--parsable-stdout"]
    ignore_areas: list[IgnoreArea] = (
        [IgnoreArea(*ia) for ia in ignore] if ignore is not None else []
    )
    if isinstance(base, Image.Image):
        base_path = tmp_dir / "base.png"
        base.save(base_path)
        base = base_path
    if isinstance(comparing, Image.Image):
        comparing_path = tmp_dir / "comparing.png"
        comparing.save(comparing_path)
        comparing = comparing_path
    if diff is None:
        diff = tmp_dir / "diff.png"
    if antialiasing is True:
        cli_args.append("--antialiasing")
    cli_args.append(f"--diff-color={diff_color}")
    if diff_mask is True:
        cli_args.append("--diff-mask")
    if fail_on_layout is True:
        cli_args.append("--fail-on-layout")
    if len(ignore_areas) > 0:
        cli_args.append(f"--ignore={','.join(ia.to_region_str() for ia in ignore_areas)}")
    if output_diff_lines is True:
        cli_args.append("--output-diff-lines")
    if reduce_ram_usage is True:
        cli_args.append("--reduce-ram-usage")
    cli_args.append(f"--threshold={threshold}")
    cli_args.extend(
        [
            Path(base).as_posix(),
            Path(comparing).as_posix(),
            Path(diff).as_posix(),
        ]
    )

    returncode, stdout, stderr = run_odiff(*cli_args)
    if returncode not in CompareStatus._value2member_map_:
        msg = f"Error calling odiff executable:\n{stderr}"
        raise RuntimeError(msg)
    diff_pixel_count, _, rest = stdout.partition(";")
    diff_percent, _, diff_lines = rest.partition(";")

    return DiffResult(
        base_image=load_image(base),
        comparing_image=load_image(comparing),
        diff_image=load_image(diff) if Path(diff).is_file() else None,
        status=CompareStatus(returncode),
        diff_pixel_count=int(diff_pixel_count) if diff_pixel_count != "" else None,
        diff_percentage=float(diff_percent) if diff_percent != "" else None,
        diff_lines=[int(line_nr) for line_nr in diff_lines.split(",") if line_nr.rstrip() != ""],
        ignore_areas=ignore_areas,
    )


def odiff(
    base: str | Path | Image.Image,
    comparing: str | Path | Image.Image,
    diff: str | Path | None = None,
    *,
    antialiasing: bool = False,
    diff_color: str = "#FF0000",
    diff_mask: bool = False,
    fail_on_layout: bool = False,
    ignore: Iterable[IgnoreArea | tuple[int, int, int, int]] | None = None,
    output_diff_lines: bool = False,
    reduce_ram_usage: bool = False,
    threshold: float = 0.1,
) -> DiffResult:
    """Run odiff in a temp directory.

    Parameters
    ----------
    base : str | Path | Image.Image
        Base image.
    comparing : str | Path | Image.Image
        Comparing image.
    diff : str | Path | None
        _description_. Defaults to None
    antialiasing : bool
        With this flag enabled, antialiased pixels are not counted to the diff of an image.
        Defaults to False
    diff_color : str
        Color used to highlight different pixels in the output (in hex format e.g. #cd2cc9).
        Defaults to "#FF0000"
    diff_mask : bool
        Output only changed pixel over transparent background. Defaults to False
    fail_on_layout : bool
        Do not compare images and produce output if images layout is different. Defaults to False
    ignore : Iterable[IgnoreArea | tuple[int, int, int, int]] | None
        An array of regions to ignore in the diff. Defaults to None
    output_diff_lines : bool
        With this flag enabled, output result in case of different images will output lines for
        all the different pixels. Defaults to False
    reduce_ram_usage : bool
        With this flag enabled odiff will use less memory, but will be slower in some cases.
        Defaults to False
    threshold : float
        Color difference threshold (from 0 to 1). Less more precise. Defaults to 0.1

    Returns
    -------
    DiffResult

    Raises
    ------
    RuntimeError
        If odiff throws an unexpected error.
    """
    with TemporaryDirectory(prefix="odiff-py-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        return _odiff(
            tmp_dir=tmp_dir,
            base=base,
            comparing=comparing,
            diff=diff,
            antialiasing=antialiasing,
            diff_color=diff_color,
            diff_mask=diff_mask,
            fail_on_layout=fail_on_layout,
            ignore=ignore,
            output_diff_lines=output_diff_lines,
            reduce_ram_usage=reduce_ram_usage,
            threshold=threshold,
        )
