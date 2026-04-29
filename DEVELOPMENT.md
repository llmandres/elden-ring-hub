# Development

## Requirements
- Python **3.13+** (see `.python-version`)
- [`uv`](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Setup

```bash
uv sync --locked --dev
```

## Run

```bash
# Run GUI (default)
uv run python run_gui.py
```

## Lint / Format

```bash
uv run ruff check
uv run ruff format
```

## Test

```bash
uv run pytest -v
```

## Build

**Public releases for players:** ship a single **Windows `.zip`** built locally and uploaded to **[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)**. That zip is what users download and extract ([RELEASE.md](RELEASE.md)).

### Windows (cx_Freeze)

```bash
uv run python build-windows.py build
```

Outputs to `dist/windows-{version}/` (executable **`EldenRing Hub.exe`** inside `er-save-manager_{version}`). Zip that output and attach the zip to the release.

### Linux (PyInstaller, optional)

```bash
uv run ./build-linux.sh
```

Outputs to `dist/linux-{version}/` — developer use or custom packaging only; **not** the default end-user artifact for this fork.

**Note:** PyInstaller does not cross-compile. Build on the target platform.

## Project Structure (EldenRing Hub)

```
src/er_save_manager/
    __init__.py
    cli.py
    parser/                 # Save parsing and slot rebuild
    fixes/                  # CLI fixes (torrent, teleport, etc.)
    backup/                 # Backup manager (used by GUI edits and CLI)
    data/                   # item_database, starting_classes, convergence_items, event_flags_db, items/
    games/                  # Per-game profiles and SteamID helpers
    platform/               # Save paths, process utils
    transfer/               # character_ops (.erc import/export)
    ui/
        gui.py              # EldenRing Hub main window
        settings.py, theme.py, messagebox.py, toast.py, utils.py, backup_utils.py
        dialogs/            # save_selector (+ __init__)
        editors/            # runes_editor, spawner_editor, upgrader_editor
resources/                  # Root: icon, manifest (build)
src/resources/             # eventflag_bst, map (parser assets)
```

Older docs may still mention removed tabs, community browsers, and Supabase—they are no longer in this tree.

scripts/                        # Build/release scripts (bump_version, etc.)
tests/                          # Unit tests
build-windows.py / build-linux.sh / run_gui.py / main.py / pyproject.toml
```

## Architecture Notes

### Save File Structure

- **UserData10**: Common save data (SteamID, character list, profiles)
- **UserDataX**: Individual character slots (1-10)
- **PlayerGameData**: Core character data structure

### UI (EldenRing Hub)

- **CustomTkinter** main window (`gui.py`): file path, slot + Load character, tabs for Runes / Item Spawner / Upgrader.

### Platform Support

- **Windows**: Native paths, AppData save location
- **Linux**: Proton/Wine compatdata detection, multiple Steam paths
- **Save Detection**: Auto-detect from default locations or libraryfolders.vdf

## Adding New Features

### Extending the Hub window

Edit `src/er_save_manager/ui/gui.py` (and add submodules under `ui/editors/` or `ui/dialogs/` as needed). Re-run `build-windows.py` after substantive import changes.

### Adding Game Data

1. Add files under `src/er_save_manager/data/` (often `items/` lists read by `item_database.py`).
2. Update imports only where the new data is used.

### Adding a Corruption Fix

1. Create `src/er_save_manager/fixes/your_fix.py`
2. Inherit from `BaseFix`
3. Implement `detect()` and `apply()`
4. Register in `fixes/__init__.py` (`ALL_FIXES`) for CLI `fix` command

## Troubleshooting

### Icon not showing in build
- Ensure `resources/icon/icon.ico` (Windows) and `resources/icon/icon.png` (Linux) exist
- Check build scripts include `--icon` parameter

### Missing UI modules in build
- Add to `--hidden-import` in `build-linux.sh`
- Add to `includes` list in `build-windows.py`

### Linux save file not detected
- Check `~/.local/share/Steam/config/libraryfolders.vdf` for custom library paths
- Verify compatdata folder exists: `~/.local/share/Steam/steamapps/compatdata/1245620/`
