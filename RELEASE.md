# Publishing a Windows release (.zip via GitHub)

End users download **one `.zip` from GitHub Releases** containing the frozen app (`EldenRing Hub.exe` and dependencies). This project ships that GUI built with **cx_Freeze** on Windows. Build on a Windows machine (no cross-compilation).

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

Inside you will find **`EldenRing Hub.exe`** (plus DLLs and `lib/`). Zip the **`er-save-manager_<version>/`** folder (or the whole `dist/windows-<version>/` contents—whatever you want users to extract). **That zip is the only file most users need.**

## GitHub Release checklist

1. Tag the commit (e.g. `v0.14.0`).
2. Create a **Release** on GitHub from that tag.
3. **Attach the `.zip`** as the main download asset. Users grab this from the Releases page; nothing else is required from automation.
4. In the release notes, repeat the **online / anti-cheat** warning from the README (offline play, Seamless Coop at user’s own risk).

Optional mirrors (for example Nexus Mods) can republish the same zip; GitHub Releases remains the canonical download for this fork unless you document otherwise.

## Notes

- Do not run the build with the game open; a clean `uv sync` environment avoids pulling unrelated packages into the frozen app.
- If the app fails to start on another PC, install the **Visual C++ Redistributable** (x64) on that machine—typical for Python-based Windows builds.
