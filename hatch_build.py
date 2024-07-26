"""Download odiff binaries from last release when building the wheel or in dev env."""

from __future__ import annotations

import os
import platform
import stat
from pathlib import Path
from typing import Any

import httpx
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.tags import sys_tags

REPO_ROOT = Path(__file__).parent

ODIFF_VERSION = "v3.1.1"
REL_DEST_PATH = "odiff_py/bin/odiff.exe"
ODIFF_BIN = REPO_ROOT / REL_DEST_PATH


def get_release_assets(tag_name: str = ODIFF_VERSION) -> list[dict[str, Any]]:
    """Get list of assets for the release with tag ``tag_name``.

    Parameters
    ----------
    tag_name : str
        Release tag. Defaults to ODIFF_VERSION

    Returns
    -------
    list[dict[str, Any]]
        Assets of the release.

    Raises
    ------
    ValueError
        If the API response has a response code that isn't 200.
    ValueError
        If response has an unexpected shape.
    """
    headers = {}
    # Needed for CI rate limits
    gh_token = os.getenv("GH_TOKEN")
    if gh_token is not None:
        headers["Authorization"] = f"Bearer {gh_token}"
    resp = httpx.get("https://api.github.com/repos/dmtrKovalenko/odiff/releases", headers=headers)
    if resp.status_code != 200:
        msg = f"Bad API response: {resp}"
        raise ValueError(msg)
    for release in resp.json():
        if release.get("tag_name", None) == tag_name:
            return release["assets"]
    msg = "API response has unexpected shape."
    raise ValueError(msg)


def get_odiff_bin_download_url(tag_name: str = ODIFF_VERSION) -> str:
    """Get download url for the system form the release page json payload.

    Parameters
    ----------
    tag_name : str
        Release tag. Defaults to ODIFF_VERSION

    Returns
    -------
    str
        Download url of the release asset for the current platform.

    Raises
    ------
    ValueError
        If no version for the platform could be found.
    """
    system = platform.system().lower()
    processor = platform.processor()

    assets = get_release_assets(tag_name)
    for asset in assets:
        if (
            (system == "linux" and asset["name"] == "odiff-linux-x64.exe")
            or (system == "windows" and asset["name"] == "odiff-windows-x64.exe")
            or (
                system == "darwin"
                and (
                    (processor.startswith("arm") and asset["name"] == "odiff-macos-arm64.exe")
                    or (processor == "i386" and asset["name"] == "odiff-macos-x64.exe")
                )
            )
        ):
            return asset["browser_download_url"]
    msg = f"Couldn't find odiff binary for your system:\n\t{system=}\n\t{processor}"
    raise ValueError(msg)


def download_odiff_bin(tag_name: str = ODIFF_VERSION) -> None:
    """Download odiff binary for the system from the github release page.

    Parameters
    ----------
    tag_name : str
        Release tag. Defaults to ODIFF_VERSION
    """
    if ODIFF_BIN.is_file() is True:
        return
    print("Downloading odiff binary...")  # noqa: T201
    ODIFF_BIN.parent.mkdir(parents=True, exist_ok=True)
    download_url = get_odiff_bin_download_url(tag_name)
    resp = httpx.get(download_url, follow_redirects=True)
    ODIFF_BIN.write_bytes(resp.content)
    st = ODIFF_BIN.stat()
    ODIFF_BIN.chmod(st.st_mode | stat.S_IEXEC)


class CustomBuildHook(BuildHookInterface):
    """Custom build hook class."""

    def initialize(self, _version: str, build_data: dict[str, Any]) -> None:  # noqa: DOC
        """Download odiff binary and update build data."""
        # Linux tag is after many/musl; packaging tools are required to skip
        # many/musl, see https://github.com/pypa/packaging/issues/160
        tag = next(
            iter(
                t
                for t in sys_tags()
                if "manylinux" not in t.platform and "musllinux" not in t.platform
            )
        )
        download_odiff_bin()

        build_data["force_include"][ODIFF_BIN.as_posix()] = REL_DEST_PATH
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{tag.platform}"

    def clean(self, _versions: list[str]) -> None:  # noqa: DOC
        """Clean up after building the wheel."""
        ODIFF_BIN.unlink(missing_ok=True)


if __name__ == "__main__":
    download_odiff_bin()
