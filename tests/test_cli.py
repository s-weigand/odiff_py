"""Tests for `odiff_py` CLI."""

from __future__ import annotations

import platform
import subprocess
import sys

from tests import TEST_DATA


def test_command_line_interface():
    """Test the CLI."""
    cmd = [sys.executable, "-m", "odiff_py", "--help=plain"]
    if platform.system().lower() == "windows":
        cmd = " ".join(cmd)
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.rstrip() == (TEST_DATA / "help.txt").read_text().rstrip()
