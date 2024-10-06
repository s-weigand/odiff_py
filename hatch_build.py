"""Download odiff binaries from last release when building the wheel or in dev env."""

from __future__ import annotations

import os
import platform
import stat
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import httpx
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.tags import sys_tags

REPO_ROOT = Path(__file__).parent

ODIFF_VERSION = (REPO_ROOT / ".odiff-version").read_text().strip()
ODIFF_BIN = REPO_ROOT / "odiff_py/bin/odiff.exe"
ODIFF_LIC = REPO_ROOT / "odiff_py/bin/LICENSE-odiff"

EXTRA_HEADERS = {}
# Needed for CI rate limits
gh_token = os.getenv("GH_TOKEN")
if gh_token is not None:
    EXTRA_HEADERS["Authorization"] = f"Bearer {gh_token}"


def get_release_assets(tag_name: str = ODIFF_VERSION) -> tuple[list[dict[str, Any]], str]:
    """Get list of assets for the release with tag ``tag_name``.

    Parameters
    ----------
    tag_name : str
        Release tag. Defaults to ODIFF_VERSION

    Returns
    -------
    tuple[list[dict[str, Any]], str]
        Assets of the release and zipball url.

    Raises
    ------
    ValueError
        If the API response has a response code that isn't 200.
    ValueError
        If response has an unexpected shape.
    """
    resp = httpx.get(
        "https://api.github.com/repos/dmtrKovalenko/odiff/releases", headers=EXTRA_HEADERS
    )
    if resp.status_code != 200:
        msg = f"Bad API response: {resp}"
        raise ValueError(msg)
    for release in resp.json():
        if release.get("tag_name", None) == tag_name:
            return release["assets"], release["zipball_url"]
    msg = "API response has unexpected shape."
    raise ValueError(msg)


def get_odiff_bin_download_url(tag_name: str = ODIFF_VERSION) -> tuple[str, str]:
    """Get download url for the system form the release page json payload.

    Parameters
    ----------
    tag_name : str
        Release tag. Defaults to ODIFF_VERSION

    Returns
    -------
    tuple[str, str]
        Download url of the release asset for the current platform and zipball url.

    Raises
    ------
    ValueError
        If no version for the platform could be found.
    """
    system = platform.system().lower()
    processor = platform.processor()

    assets, zipball_url = get_release_assets(tag_name)
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
            return asset["browser_download_url"], zipball_url
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
    binary_url, zipball_url = get_odiff_bin_download_url(tag_name)
    binary_resp = httpx.get(binary_url, follow_redirects=True, headers=EXTRA_HEADERS)
    ODIFF_BIN.write_bytes(binary_resp.content)
    st = ODIFF_BIN.stat()
    ODIFF_BIN.chmod(st.st_mode | stat.S_IEXEC)
    zipball_resp = httpx.get(zipball_url, follow_redirects=True, headers=EXTRA_HEADERS)
    with ZipFile(BytesIO(zipball_resp.content)) as zipball:
        base_dir = zipball.namelist()[0]
        ODIFF_LIC.write_bytes(zipball.read(f"{base_dir}LICENSE"))


class CustomBuildHook(BuildHookInterface):
    """Custom build hook class."""

    def initialize(self, _version: str, build_data: dict[str, Any]) -> None:  # noqa: DOC
        """Download odiff binary and update build data."""
        if any("musllinux" in t.platform for t in sys_tags()) and ODIFF_BIN.is_file() is False:
            msg = "The upstream odiff project does currently not support 'musllinux'."
            raise ValueError(msg)
        tag = next(iter(t for t in sys_tags()))
        download_odiff_bin()

        build_data["force_include"][ODIFF_BIN.as_posix()] = ODIFF_BIN.relative_to(
            REPO_ROOT
        ).as_posix()
        build_data["force_include"][ODIFF_LIC.as_posix()] = ODIFF_LIC.relative_to(
            REPO_ROOT
        ).as_posix()
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{tag.platform}"

    def clean(self, _versions: list[str]) -> None:  # noqa: DOC
        """Clean up after building the wheel."""
        ODIFF_BIN.unlink(missing_ok=True)


if __name__ == "__main__":
    download_odiff_bin()
