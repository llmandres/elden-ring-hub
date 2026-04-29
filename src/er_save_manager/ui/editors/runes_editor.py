"""Minimal runes (wallet / death pile) editor for Elden Ring character slots."""

from io import BytesIO
from pathlib import Path

import customtkinter as ctk

from er_save_manager.backup.manager import BackupManager
from er_save_manager.parser.slot_rebuild import rebuild_slot
from er_save_manager.parser.user_data_x import UserDataX
from er_save_manager.ui.messagebox import CTkMessageBox
from er_save_manager.ui.utils import int_from_tk_str_var

SLOT_DATA_SIZE = 0x280000
CHECKSUM_SIZE = 0x10


def _clamp_u32(value: int) -> int:
    return max(0, min(0xFFFFFFFF, int(value)))


class RunesEditor:
    """Wallet runes + dropped pile (death recovery) linked to PlayerGameData."""

    def __init__(self, parent, get_save_file_cb, get_char_slot_cb, get_save_path_cb):
        self.parent = parent
        self.get_save_file = get_save_file_cb
        self.get_char_slot = get_char_slot_cb
        self.get_save_path = get_save_path_cb

        self.runes_var = ctk.StringVar(value="0")
        self.runes_memory_var = ctk.StringVar(value="0")

    def setup_ui(self):
        frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        frame.pack(fill=ctk.BOTH, expand=True)

        hint = ctk.CTkLabel(
            frame,
            text=(
                "Carried — runes you're holding now. Lost pile — dropped on your corpse until you pick them "
                "(set to 0 if nothing is dropped). Align both entries with what should load after restarting the game."
            ),
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
            wraplength=720,
            text_color=("gray30", "gray75"),
        )
        hint.pack(anchor="w", padx=8, pady=(8, 10))

        row_wallet = ctk.CTkFrame(frame, fg_color="transparent")
        row_wallet.pack(fill=ctk.X, padx=8, pady=4)

        ctk.CTkLabel(row_wallet, text="Runes carried", width=170, anchor="w").pack(
            side=ctk.LEFT, padx=(0, 8)
        )
        ctk.CTkEntry(row_wallet, textvariable=self.runes_var, width=220).pack(
            side=ctk.LEFT
        )

        row_mem = ctk.CTkFrame(frame, fg_color="transparent")
        row_mem.pack(fill=ctk.X, padx=8, pady=4)

        ctk.CTkLabel(row_mem, text="Dropped / lost pile", width=170, anchor="w").pack(
            side=ctk.LEFT, padx=(0, 8)
        )
        ctk.CTkEntry(row_mem, textvariable=self.runes_memory_var, width=220).pack(
            side=ctk.LEFT
        )

        footer = ctk.CTkLabel(
            frame,
            text=(
                "Tip: Quit the game before saving. Reload the save in-game after writing."
            ),
            font=("Segoe UI", 10),
            text_color=("gray35", "gray65"),
        )
        footer.pack(anchor="w", padx=8, pady=(6, 4))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill=ctk.X, padx=8, pady=12)

        ctk.CTkButton(
            btn_row,
            text="Apply changes",
            command=self.apply_changes,
            fg_color="#1e40af",
            hover_color="#2563eb",
            width=160,
            height=32,
        ).pack(side=ctk.LEFT)

    def refresh_from_slot(self):
        """Populate fields from the currently loaded character."""
        save = self.get_save_file()
        if not save:
            return

        idx = self.get_char_slot()
        if idx < 0 or idx >= 10:
            return

        slot = save.characters[idx]
        if slot.is_empty():
            self.runes_var.set("0")
            self.runes_memory_var.set("0")
            return

        pg = getattr(slot, "player_game_data", None)
        if not pg:
            self.runes_var.set("0")
            self.runes_memory_var.set("0")
            return

        self.runes_var.set(str(max(0, getattr(pg, "runes", 0))))
        self.runes_memory_var.set(str(max(0, getattr(pg, "runes_memory", 0))))

    def apply_changes(self):
        save_file = self.get_save_file()
        if not save_file:
            CTkMessageBox.showwarning(
                "No Save", "Load a save first.", parent=self.parent
            )
            return

        slot_idx = self.get_char_slot()
        if slot_idx < 0 or slot_idx > 9:
            CTkMessageBox.showwarning(
                "Slot", "Choose Load character above first.", parent=self.parent
            )
            return

        slot = save_file.characters[slot_idx]
        if slot.is_empty():
            CTkMessageBox.showwarning(
                "Empty", f"Slot {slot_idx + 1} has no character.", parent=self.parent
            )
            return

        if isinstance(save_file._raw_data, bytes):
            save_file._raw_data = bytearray(save_file._raw_data)

        save_path = self.get_save_path()
        try:
            if save_path:
                manager = BackupManager(Path(save_path))
                manager.create_backup(
                    description=f"before_runes_slot_{slot_idx + 1}",
                    operation="edit_runes",
                    save=save_file,
                )
        except Exception as e:
            CTkMessageBox.showwarning("Backup", str(e), parent=self.parent)

        char = slot.player_game_data
        char.runes = _clamp_u32(int_from_tk_str_var(self.runes_var, char.runes))
        char.runes_memory = _clamp_u32(
            int_from_tk_str_var(self.runes_memory_var, char.runes_memory)
        )

        try:
            rebuilt = rebuild_slot(slot)
            if len(rebuilt) != SLOT_DATA_SIZE:
                raise ValueError(
                    f"Rebuilt slot size mismatch: {len(rebuilt)} != {SLOT_DATA_SIZE}"
                )

            if slot_idx >= len(save_file._slot_offsets):
                raise RuntimeError("Missing slot offset for this save.")

            slot_offset = save_file._slot_offsets[slot_idx]
            abs_offset = slot_offset + CHECKSUM_SIZE

            if abs_offset + len(rebuilt) > len(save_file._raw_data):
                raise ValueError("Write would exceed file bounds")

            save_file._raw_data[abs_offset : abs_offset + len(rebuilt)] = rebuilt

            try:
                slot_buf = BytesIO(
                    bytes(save_file._raw_data[abs_offset : abs_offset + len(rebuilt)])
                )
                save_file.character_slots[slot_idx] = UserDataX.read(
                    slot_buf, save_file.is_ps, abs_offset, len(rebuilt)
                )
            except Exception:
                pass

            save_file.recalculate_checksums()
            if save_path:
                save_file.to_file(Path(save_path))
            self.refresh_from_slot()
            CTkMessageBox.showinfo(
                "Saved",
                "Runes written to disk.\nQuit the game if it was open, then reload the save.",
                parent=self.parent,
            )
        except Exception as e:
            CTkMessageBox.showerror("Failed", str(e), parent=self.parent)
