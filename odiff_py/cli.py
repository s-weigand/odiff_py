"""Console script for odiff_py."""

from __future__ import annotations

import typer

app = typer.Typer()


@app.command()
def main() -> int:
    """Console script for odiff_py.

    Returns
    -------
    int
        Returncode
    """
    typer.echo("Replace this message by putting your code into odiff_py.cli.main")
    typer.echo("See click documentation at https://typer.tiangolo.com/")
    return 0


if __name__ == "__main__":
    app()
