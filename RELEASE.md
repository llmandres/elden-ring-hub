# Publishing a Windows release (.exe)

This project ships a GUI built with **cx_Freeze** on Windows. Build on a Windows machine (no cross-compilation).

## Prerequisites

- Windows 10/11
- Python **3.13+** (see `.python-version`)
- [`uv`](https://github.com/astral-sh/uv) recommended

## One-time setup

```powershell
cd path\to\er-save-manager
uv sync --locked --dev
```

## Bump version (before building)

1. Set `version` in `pyproject.toml`.
2. Update `resources/version.txt` (`version=`, `file_version=`, `product_version=` lines) to match.

## Build the executable

```powershell
uv run python build-windows.py build
```

Output directory (example for `0.14.0`):

`dist/windows-0.14.0/er-save-manager_0.14.0/`

Inside you will find **`EldenRing Hub.exe`** (plus DLLs and `lib/`). Distribute the **entire folder**, or zip it and attach the zip to the GitHub Release.

## GitHub Release checklist

1. Tag the commit (e.g. `v0.14.0`).
2. Create a Release from that tag on GitHub.
3. Upload the **zipped build folder** (or the full `dist/windows-*` tree as produced by the build).
4. In the release notes, repeat the **online / anti-cheat** warning from the README (offline play, Seamless Coop at user’s own risk).

## Notes

- Do not run the build with the game open; a clean `uv sync` environment avoids pulling unrelated packages into the frozen app.
- If the app fails to start on another PC, install the **Visual C++ Redistributable** (x64) on that machine—typical for Python-based Windows builds.
