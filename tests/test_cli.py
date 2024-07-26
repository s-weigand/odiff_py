#!/usr/bin/env python

"""Tests for `odiff_py` package."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from odiff_py import cli


def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.app)
    assert result.exit_code == 0
    assert "odiff_py.cli.main" in result.output
    help_result = runner.invoke(cli.app, ["--help"])
    assert help_result.exit_code == 0
    assert re.search(r"--help\s+Show this message and exit.", help_result.output)
