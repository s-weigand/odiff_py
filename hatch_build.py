"""Download odiff binaries from last release when building the wheel or in dev env."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

REPO_ROOT = Path(__file__).parent

file_to_include = REPO_ROOT / "coverage.xml"
rel_dest_path = "odiff_py/bin/artifact"


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        print(f"{build_data=}")
        print(f"{self.root=}")
        print(f"{self.directory=}")
        print(f"{self.config=}")
        print(f"{self.metadata=}")
        print(f"{self.build_config=}")
        build_data["force_include"][file_to_include.as_posix()] = rel_dest_path

    def clean(self, versions: list[str]) -> None:
        file_to_include.unlink(missing_ok=True)


# curl -L \
#   -H "Accept: application/vnd.github+json" \
#   -H "X-GitHub-Api-Version: 2022-11-28" \
#   "https://api.github.com/repos/dmtrKovalenko/odiff/releases?per_page=1"

if __name__ == "__main__":
    dest_path = REPO_ROOT / rel_dest_path
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    copyfile(file_to_include, REPO_ROOT / rel_dest_path)
