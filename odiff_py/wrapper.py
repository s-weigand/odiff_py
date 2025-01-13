"""Module containing the odiff wrapper functionality."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple

from PIL import Image

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
    use_checker_transparency: bool = True

    def create_apng(
        self,
        *,
        delay_num: int = 500,
        delay_den: int = 1000,
    ) -> APNG:
        """Create an apng from the images and their diff if there is any.

        Parameters
        ----------
        delay_num : int
            The delay numerator for frames. Defaults to 500
        delay_den : int
            The delay denominator for frames. Defaults to 1000

        Returns
        -------
        APNG
        """
        images = [self.base_image, self.comparing_image, self.diff_image]
        return APNG.from_images(images, delay_num=delay_num, delay_den=delay_den)

    def _repr_markdown_(self) -> str:  # noqa:DOC
        """Magic method for rendering automatically in jupyter notebooks."""
        if self.status == CompareStatus.IMAGE_MATCH:
            return "Images are identical."
        result_lines = [
            "|Meaning|Value|",
            "|-------|-----|",
            f"|Status|{self.status.name.replace('_', ' ').capitalize()}|",
            f"|Diff Pixel Count|{self.diff_pixel_count}|",
            f"|Diff Percentage|{self.diff_percentage:.2f}%|",
        ]
        if len(self.diff_lines) > 0:
            result_lines.append(f"|Diff Lines|{self.diff_lines}|")
        result_lines.append(f"\n<br>{self.create_apng()}\n")
        return "\n".join(result_lines)


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
    ignore: list[IgnoreArea | tuple[int, int, int, int]] | None = None,
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
    ignore : list[IgnoreArea  |  tuple[int, int, int, int]] | None
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
    if ignore is not None:
        cli_args.append(f"--ignore={','.join(IgnoreArea(*ia).to_region_str() for ia in ignore)}")
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
    ignore: list[IgnoreArea | tuple[int, int, int, int]] | None = None,
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
    ignore : list[IgnoreArea  |  tuple[int, int, int, int]] | None
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
