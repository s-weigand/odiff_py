"""Utility module to run odiff."""

from __future__ import annotations

import base64
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from apngasm_python.apngasm import APNGAsmBinder

from odiff_py import ODIFF_EXE

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Sequence

    from PIL import Image

    try:
        from typing import Self  # type:ignore[attr-defined]
    except ImportError:
        from typing_extensions import Self

# Image manipulation tool like transparency background style (e.g. photoshop)
# Taken from https://stackoverflow.com/a/47061022/3990615
CHECKER_TRANSPARENCY_CSS = " ".join(
    """
background: -webkit-linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), -webkit-linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), white;
background: -moz-linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), -moz-linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), white;
background: linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), linear-gradient(45deg, rgba(0, 0, 0, 0.0980392) 25%, transparent 25%, transparent 75%, rgba(0, 0, 0, 0.0980392) 75%, rgba(0, 0, 0, 0.0980392) 0), white;
background-repeat: repeat, repeat;
background-position: 0px 0, 5px 5px;
-webkit-transform-origin: 0 0 0;
transform-origin: 0 0 0;
-webkit-background-origin: padding-box, padding-box;
background-origin: padding-box, padding-box;
-webkit-background-clip: border-box, border-box;
background-clip: border-box, border-box;
-webkit-background-size: 10px 10px, 10px 10px;
background-size: 10px 10px, 10px 10px;
-webkit-box-shadow: none;
box-shadow: none;
text-shadow: none;
-webkit-transition: none;
-moz-transition: none;
-o-transition: none;
transition: none;
-webkit-transform: scaleX(1) scaleY(1) scaleZ(1);
transform: scaleX(1) scaleY(1) scaleZ(1);
""".splitlines()  # noqa: E501
)


def run_odiff(*args: str, capture_output: bool = True) -> tuple[int, str, str]:
    """Run odiff binary.

    Parameters
    ----------
    *args : str
        Arguments passed directly to the ``odiff`` executable.
    capture_output : bool
        Whether to capture the output or not. The only place where ``False`` should be used is to
        invoke the executable as CLI tool so the user sees the output. Defaults to True

    Returns
    -------
    tuple[int, str, str]
        Return code of running odiff and stdout.
    """
    cmd: str | Sequence[str] = (quote(ODIFF_EXE.as_posix()), *args)
    if platform.system().lower() == "windows":
        cmd = " ".join(cmd)
    result = subprocess.run(cmd, capture_output=capture_output, text=True)
    return result.returncode, result.stdout, result.stderr


def png_images_to_apng_bytes(
    images: Iterable[Image.Image | None],
    out_file: str | Path | None = None,
    *,
    delay_num: int = 500,
    delay_den: int = 1000,
) -> bytes:
    """Convert png images to ``bytes`` representation of an animated png.

    Parameters
    ----------
    images : Iterable[Image.Image  |  None]
        Sequence of images to create ``apng`` from. If an image is ``None`` it will be skipped.
    out_file : str | Path | None
        Path to an output file to generate. Defaults to None
    delay_num : int
        The delay numerator for frames. Defaults to 500
    delay_den : int
        The delay denominator for frames. Defaults to 1000

    Returns
    -------
    bytes

    See Also
    --------
    APNGAsmBinder.add_frame_from_pillow
    """
    apngasm = APNGAsmBinder()

    for image in images:
        if image is not None:
            apngasm.add_frame_from_pillow(image, delay_num=delay_num, delay_den=delay_den)
    with TemporaryDirectory() as tmp_dir:
        out_file = Path(out_file) if out_file is not None else Path(tmp_dir) / "animated.apng"
        apngasm.assemble(out_file.as_posix())
        return out_file.read_bytes()


@dataclass
class APNG:
    """APNG wrapper class."""

    data: bytes
    use_checker_transparency: bool = True

    @classmethod
    def from_images(
        cls,
        images: Iterable[Image.Image | None],
        *,
        delay_num: int = 500,
        delay_den: int = 1000,
    ) -> Self:
        """Create new instance from images.

        Parameters
        ----------
        images : Iterable[Image.Image  |  None]
            Images to create the apng instance from.
        delay_num : int
            The delay numerator for frames. Defaults to 500
        delay_den : int
            The delay denominator for frames. Defaults to 1000

        Returns
        -------
        Self
        """
        return cls(
            data=png_images_to_apng_bytes(images=images, delay_num=delay_num, delay_den=delay_den)
        )

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """Create new instance from apng file.

        Parameters
        ----------
        path : str | Path
            File to load.

        Returns
        -------
        Self
        """
        return cls(data=Path(path).read_bytes())

    def save(self, path: str | Path) -> Path:
        """Save to file at ``path``.

        Parameters
        ----------
        path : str | Path
            Path to save the file to.

        Returns
        -------
        Path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.data)
        return path

    def __str__(self) -> str:  # noqa:DOC
        """Create string repr for instance."""
        img_str = base64.b64encode(self.data).decode(encoding="utf-8")
        return (
            '<img style="border: 1px solid; '
            f'{CHECKER_TRANSPARENCY_CSS if self.use_checker_transparency is True else ""}" '
            f'src="data:image/apng;base64,{img_str}">'
        )

    def _repr_markdown_(self) -> str:  # noqa:DOC
        """Magic method for rendering automatically in jupyter notebooks."""
        return str(self)
