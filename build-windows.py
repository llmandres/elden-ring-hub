"""Build script for Windows (cx_Freeze).

Usage:
        uv sync --dev
        uv run python build-windows.py build
"""

import sys
import warnings
from pathlib import Path

import tomlkit
from cx_Freeze import Executable, setup
from cx_Freeze.finder import ModuleFinder


def load_version() -> str:
    version_txt = Path(__file__).parent / "resources" / "version.txt"
    if version_txt.exists():
        for line in version_txt.read_text(encoding="utf-8").splitlines():
            if line.startswith("version="):
                version_str = line.split("=", 1)[1].strip()
                return version_str.rstrip("0").rstrip(".")
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    pyproject_content = pyproject_path.read_text(encoding="utf-8")
    pyproject_data = tomlkit.parse(pyproject_content)
    return pyproject_data["project"]["version"]


VERSION = load_version()

warnings.filterwarnings("ignore", category=SyntaxWarning)

if sys.platform != "win32":
    sys.exit("This script must be run on Windows to build a Windows binary.")

include_files = [
    ("src/resources/", "resources/"),
    ("resources/", "resources/"),
    ("resources/app.manifest", "app.manifest"),
]

ui_packages = []

build_exe_options = {
    "packages": ["er_save_manager"] + ui_packages,
    "includes": [],
    "include_files": include_files,
    "zip_exclude_packages": ["er_save_manager", "customtkinter", "customtkinterthemes"],
    "zip_include_packages": ["*"],
    "excludes": ["unittest", "pydoc"],
    "build_exe": f"dist/windows-{VERSION}/er-save-manager_{VERSION}",
    "optimize": 2,
}

base = "gui" if sys.platform == "win32" else None

executables = [
    Executable(
        "run_gui.py",
        base=base,
        target_name="EldenRing Hub",
        icon="resources/icon/icon.ico",
        manifest="resources/app.manifest",
    )
]

original_include_files = ModuleFinder.include_files


def patched_include_files(self, source_path, target_path, copy_dependent_files=True):
    source_path = Path(source_path)
    target_path = Path(target_path)

    if str(target_path).startswith("share") and source_path.is_dir():
        if "tcl" in source_path.name or "tk" in source_path.name:
            for file_path in source_path.rglob("*"):
                if file_path.is_dir():
                    continue

                rel_path = file_path.relative_to(source_path)
                if "tzdata" in rel_path.parts or "demos" in rel_path.parts:
                    continue

                final_target = target_path / rel_path
                original_include_files(
                    self, file_path, final_target, copy_dependent_files
                )
            return

    original_include_files(self, source_path, target_path, copy_dependent_files)


ModuleFinder.include_files = patched_include_files

setup(
    name="EldenRing Hub",
    version=VERSION,
    description="EldenRing Hub — Elden Ring save editor (GUI)",
    options={"build_exe": build_exe_options},
    executables=executables,
)
