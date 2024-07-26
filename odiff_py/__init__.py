"""Top-level package for odiff-py."""

from __future__ import annotations

from pathlib import Path

ODIFF_EXE = Path(__file__).parent / "bin/odiff.exe"

from odiff_py.wrapper import CompareStatus  # noqa: E402
from odiff_py.wrapper import DiffResult  # noqa: E402
from odiff_py.wrapper import odiff  # noqa: E402

__all__ = ["odiff", "DiffResult", "CompareStatus"]


__author__ = """Sebastian Weigand"""
__email__ = "s.weigand.phy@gmail.com"
__version__ = "0.0.1"
