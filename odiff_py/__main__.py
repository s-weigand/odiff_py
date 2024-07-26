"""Main module."""

from __future__ import annotations

import sys

from odiff_py.utils import run_odiff


def main():
    """Run odiff binary with CLI args."""
    run_odiff(*sys.argv[1:], capture_output=False)


if __name__ == "__main__":
    main()
