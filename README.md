# Elden Ring Save Manager / EldenRing Hub

A save file editor and backup utility for **Elden Ring** with a desktop GUI.  
The default application window is **EldenRing Hub**: load a save, pick a character slot, then use **Runes**, **Item Spawner** (grace chest), and **Upgrader** tools. The repository also contains parsers and modules for broader save work (see docs).

---

## Online play, bans, Easy Anti-Cheat, and Seamless Coop

**Read this before using any save editor.**

- **Modified saves are unsafe for online play.** Elden Ring uses **Easy Anti-Cheat (EAC)**. Editing save data and then connecting to the game’s online services (**including co-op or invasions**) can **result in bans or restrictions**, even when changes look harmless (e.g. runes).
- **Use offline.** Launch the game in **offline mode** (or launch with **EAC disabled** if your setup allows it) and avoid online features while playing on an edited save. This mirrors common community guidance for save tooling and cheats.
- **Seamless Coop** saves are normal Elden Ring save files (`ER*.sl2`, etc.). This application reads/writes those files the same way as vanilla saves. Seamless Coop has its **own installation and multiplayer rules**—follow the mod authors’ docs. Combine **edited saves + coop mods at your own risk**; we do not guarantee acceptance by the mod executable or immunity from bans.
- **You are responsible** for backups, verifying files, and how you use edits. Not affiliated with FromSoftware or Bandai Namco.

If you distribute builds, **repeat this warning** in release notes.

---

## How it works

1. **Locate the save.** On Windows the app usually finds saves under `%APPDATA%\EldenRing\` (`ER0000.sl2`, backups like `CO60000.co2`, etc.).
2. **Parse.** The `.sl2` file is unpacked as documented by community reverse engineering (`BND4` layout, `/USER_DATA_0x`/character slots).
3. **Edit in memory.** Your character slot (`UserDataX`) is rebuilt when needed so variable sections stay consistent (`rebuild_slot`, checksum-aware writes).
4. **Write back.** The tool updates raw bytes and **recalculates MD5 checksums** per slot (and relevant sections), then saves the file to disk.
5. **Game closed.** Elden Ring must **not** be running while reading/writing the file, or Windows may serve a stale copy.

**Workflow in EldenRing Hub:** Browse or Auto-Find → open the save → choose **Slot** → **Load character** → use **Runes** / **Item Spawner** / **Upgrader** → **Apply** / spawn actions → quit the game if it was open → load the save again in-game.

---

## Documentation and user guides

[https://elden-ring-save-manager.readthedocs.io/en/main/](https://elden-ring-save-manager.readthedocs.io/en/main/)

---

## Features

### EldenRing Hub (default GUI)

- **Runes** — Edit runes carried and dropped pile (recovery) for the loaded character slot.
- **Item Spawner** — Add items to the **grace chest** (inventory storage box), not directly to pockets (see in-app wording).
- **Upgrader** — Raise **weapon** / **spirit ash** reinforcement levels for items already in **your pockets** (not arbitrary spawns).
- **Import saved data** — Bring a character from an `.erc` into a slot where supported.

### Extended capabilities (documentation / codebase)

Older documentation and modules may still describe a wider toolset (fixer, teleports, event flags, community browsers, other FromSoftware titles, etc.). Not all tabs may appear in every build; behaviour depends on how `gui.py` is configured in your checkout.

---

## Installation

Download the latest **Windows** build from your repository’s **[Releases]** page (`EldenRing Hub.exe` inside the published folder/ZIP).

- **Linux**: AppImage and scripts may still exist in the repo history; verify `build-linux.sh` and CI for your fork.

*(Replace the Releases URL in your fork: `https://github.com/YOUR_ORG/YOUR_REPO/releases`.)*

---

## Usage

1. Launch **EldenRing Hub** (or run from source — see below).
2. Browse or Auto-Find to select your `.sl2` / `.co2` file.
3. Choose a slot, then **Load character** to unlock the tools.
4. Apply changes; **fully quit Elden Ring** before writing; reload the save in-game afterward.

---

## Building from source

See [DEVELOPMENT.md](DEVELOPMENT.md).

Quick run:

```bash
uv sync --locked --dev
uv run python run_gui.py
```

---

## Publishing a Windows .exe release

See **[RELEASE.md](RELEASE.md)** for version bumps, cx_Freeze build, and attaching artifacts to GitHub Releases.

Summary:

```powershell
uv run python build-windows.py build
```

Artifacts appear under `dist/windows-<version>/`.

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Credits

### Upstream author

**[Elden Ring Save Manager](https://github.com/Hapfel1/er-save-manager)** — original project author **[Hapfel1](https://github.com/Hapfel1)**. This codebase and tooling (save parsing, workflows, docs, releases) descend from [that repository](https://github.com/Hapfel1/er-save-manager).  

If you reuse or fork the project, keep credit clearly visible alongside the MIT license requirements.

---

### Save file research

- [ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib)
- [Umgak](https://github.com/Umgak) and contributors to [TGA Cheat Table](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA)
- [Souls Modding Wiki](https://soulsmodding.com/doku.php?id=er-refmat:main)
- [SimpleSekiroSavegameHelper](https://github.com/uberhalit/SimpleSekiroSavegameHelper)

### Community

- Preset contributors and testers credited in upstream history ([2Pz](https://github.com/2Pz), [Ghostlyswat12](https://github.com/Ghostlyswat12)).

### Automation

- [2Pz](https://github.com/2Pz) for automated build/release workflows in upstream forks.
