import struct
import tkinter as tk
import customtkinter as ctk
from pathlib import Path

from er_save_manager.ui.messagebox import CTkMessageBox
from er_save_manager.ui.utils import bind_mousewheel
from er_save_manager.data.item_database import get_item_database, ItemCategory
from er_save_manager.parser.slot_rebuild import rebuild_slot
from er_save_manager.parser.world import GaitemGameDataEntry

class SpawnerEditor:
    """Spawn items into the grace chest storage (site of grace)."""
    def __init__(
        self,
        parent,
        get_save_file_callback,
        get_char_slot_callback,
        get_save_path_callback,
    ):
        self.parent = parent
        self.get_save_file = get_save_file_callback
        self.get_char_slot = get_char_slot_callback
        self.get_save_path = get_save_path_callback

        # UI variables
        self.search_var = ctk.StringVar()
        self.listbox = None
        self.lbl_selected = None
        self.btn_spawn = None

        self.db = get_item_database()
        self.all_items = []
        self.displayed_items = []

    def setup_ui(self):
        """Setup the spawner UI"""
        frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        frame.pack(fill=ctk.BOTH, expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            frame,
            text="Items are added only to your grace chest (not pockets). Rest at grace and open Chest to see items.",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 4))

        warn_shell = ctk.CTkFrame(frame, fg_color=("gray92", "#1f2937"), corner_radius=8)
        warn_shell.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        ctk.CTkLabel(
            warn_shell,
            text=(
                "If something looks missing or wrong in-game, put any item into the Chest at a site "
                "of grace, close the Chest, reopen it, save a clean load, then reopen this editor and try again "
                "(the game caches inventory views sometimes)."
            ),
            font=("Segoe UI", 10),
            justify="left",
            anchor="w",
            wraplength=720,
            text_color=("#92400e", "#fbbf24"),
        ).pack(fill=ctk.X, padx=8, pady=6)

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=0)
        
        ctk.CTkLabel(search_frame, text="Search Item:").pack(side=ctk.LEFT)
        self.search_var.trace_add("write", lambda *args: self.refresh_list())
        ctk.CTkEntry(search_frame, textvariable=self.search_var, width=250).pack(side=ctk.LEFT, padx=5)
        
        ctk.CTkButton(search_frame, text="Load Database", command=self.load_database, width=120).pack(side=ctk.RIGHT, padx=5)

        # Listbox for items
        list_container = ctk.CTkFrame(frame)
        list_container.grid(row=3, column=0, sticky="nsew", padx=4, pady=5)
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        scrollbar = tk.Scrollbar(list_container)
        mode = ctk.get_appearance_mode()
        if mode == "Light":
            listbox_bg = "#f0f0f0"
            listbox_fg = "#000000"
            listbox_select_bg = "#b8a0d0"
        else:
            listbox_bg = "#1f1f28"
            listbox_fg = "#e5e5f5"
            listbox_select_bg = "#c9a0dc"

        self.listbox = tk.Listbox(
            list_container, 
            yscrollcommand=scrollbar.set, 
            font=("Consolas", 11), 
            bg=listbox_bg, 
            fg=listbox_fg, 
            selectbackground=listbox_select_bg,
            relief=tk.FLAT,
            exportselection=False,
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        scrollbar.config(command=self.listbox.yview)
        bind_mousewheel(self.listbox)
        self.listbox.bind('<<ListboxSelect>>', self.on_item_select)

        bot_frame = ctk.CTkFrame(frame, fg_color=("gray86", "gray25"))
        bot_frame.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        
        self.lbl_selected = ctk.CTkLabel(bot_frame, text="Selected: None", font=("Segoe UI", 12, "bold"))
        self.lbl_selected.pack(side=ctk.LEFT, padx=8, pady=6)
        
        self.btn_spawn = ctk.CTkButton(
            bot_frame, 
            text="Spawn Item", 
            command=self.apply_spawn, 
            state="disabled", 
            fg_color="#28a745", 
            hover_color="#218838",
            width=120
        )
        self.btn_spawn.pack(side=ctk.RIGHT, padx=8, pady=6)
        
        self.qty_var = ctk.StringVar(value="1")
        self.entry_qty = ctk.CTkEntry(bot_frame, textvariable=self.qty_var, width=60)
        self.entry_qty.pack(side=ctk.RIGHT, padx=4, pady=6)
        ctk.CTkLabel(bot_frame, text="Qty:").pack(side=ctk.RIGHT, padx=4)
        
        self.load_database()

    def load_database(self):
        """Load items from the database"""
        self.all_items.clear()
        
        # Load Talismans, Weapons, Armors, and Goods (Materials)
        allowed_categories = [
            ItemCategory.TALISMAN, 
            ItemCategory.WEAPON, 
            ItemCategory.ARMOR,
            ItemCategory.GOODS
        ]
        
        for item in self.db.items:
            if item.category in allowed_categories:
                # Exclude empty or debug items
                if item.name and not item.name.startswith("Unknown") and not item.name.startswith("?"):
                    self.all_items.append(item)
                
        self.refresh_list()

    def refresh_list(self):
        """Refresh the listbox based on search filter"""
        self.listbox.delete(0, tk.END)
        search_query = self.search_var.get().lower()
        
        self.displayed_items = []
        for item in self.all_items:
            if search_query in item.name.lower():
                # Add category prefix
                cat_str = "Talisman"
                if item.category == ItemCategory.WEAPON:
                    cat_str = "Weapon"
                elif item.category == ItemCategory.ARMOR:
                    cat_str = "Armor"
                elif item.category == ItemCategory.GOODS:
                    cat_str = "Material/Item"
                    
                self.listbox.insert(tk.END, f"[{cat_str}] {item.name}")
                self.displayed_items.append(item)
                
        self.lbl_selected.configure(text="Selected: None")
        self.btn_spawn.configure(state="disabled")

    @staticmethod
    def _merge_gaitem_game_data_acquired_id(char, full_item_id: int) -> None:
        """
        The game only treats items as owned if their full_id appears in GaitemGameData.
        Pairs of IDs are stored per entry, sorted, matching the vanilla layout.
        """
        ggd = char.gaitem_game_data
        ids: set[int] = set()
        for e in ggd.entries:
            if e.id != 0:
                ids.add(e.id)
            if e.next_item_id != 0:
                ids.add(e.next_item_id)
        ids.add(full_item_id)
        item_ids = sorted(ids)
        n = len(item_ids)
        ggd.count = n
        num_blocks = (n + 1) // 2
        for i in range(7000):
            ggd.entries[i] = GaitemGameDataEntry()
        for bi in range(num_blocks):
            i1 = bi * 2
            i2 = bi * 2 + 1
            id1 = item_ids[i1] if i1 < n else 0
            id2 = item_ids[i2] if i2 < n else 0
            e = ggd.entries[bi]
            e.id = id1
            e.unk0x4 = 1 if id1 else 0
            e.next_item_id = id2
            e.unk0xc = 1 if id2 else 0

    @staticmethod
    def _merge_menu_profile_item_id(char, full_item_id: int) -> None:
        """
        Register full item id in menu profile / save-load item list so the client can
        resolve names and icon state (avoids “blank” or invisible lines in inventory UI).
        """
        m = char.menu_profile_save_load
        if m is None or not m.data:
            return
        data = bytearray(m.data)
        for o in range(0, len(data) - 3, 4):
            if struct.unpack_from("<I", data, o)[0] == full_item_id:
                return
        # Skip a small leading header (layout varies; do not clobber it)
        start = 16 if len(data) > 20 else 0
        for o in range(start, len(data) - 3, 4):
            if struct.unpack_from("<I", data, o)[0] == 0:
                struct.pack_into("<I", data, o, full_item_id)
                m.data = bytes(data)
                return

    def on_item_select(self, event):
        """Handle item selection in the listbox"""
        selection = self.listbox.curselection()
        if not selection:
            self.btn_spawn.configure(state="disabled")
            return
            
        idx = selection[0]
        item = self.displayed_items[idx]
        
        self.lbl_selected.configure(text=f"Selected: {item.name}")
        self.btn_spawn.configure(state="normal")

    def apply_spawn(self):
        """Inject item into chest storage box, then full slot rebuild."""
        save_file = self.get_save_file()
        if not save_file:
            return

        slot_idx = self.get_char_slot()
        if slot_idx < 0 or slot_idx > 9:
            CTkMessageBox.showwarning(
                "Character slot",
                "Choose a valid character (1–10) in the Character Editor bar above, "
                "then use Spawner. The selected slot is what we modify.",
                parent=self.parent,
            )
            return

        selection = self.listbox.curselection()
        if not selection:
            return

        item = self.displayed_items[selection[0]]
        char = save_file.characters[slot_idx]

        if char.is_empty():
            CTkMessageBox.showerror(
                "Empty slot",
                f"Slot {slot_idx + 1} has no character. Spawner only works on a loaded character.\n"
                "In the main Character Editor dropdown, pick the row that matches your in-game save "
                f'(e.g. "3 - YourName" for the third character), then use Spawner again.',
                parent=self.parent,
            )
            return

        try:
            quantity = int(self.qty_var.get())
            quantity = max(1, min(999, quantity))
        except (ValueError, TypeError):
            quantity = 1

        # Weapons, armors and talismans are unique items (qty = 1)
        if item.category in (ItemCategory.WEAPON, ItemCategory.ARMOR, ItemCategory.TALISMAN):
            quantity = 1

        # Create backup before any modification
        save_path = self.get_save_path()
        if save_path:
            from er_save_manager.backup.manager import BackupManager
            manager = BackupManager(Path(save_path))
            manager.create_backup(
                description=f"before_spawn_{item.name}_slot_{slot_idx + 1}",
                operation="spawn_item",
                save=save_file,
            )

        # Ensure raw data is mutable
        if isinstance(save_file._raw_data, bytes):
            save_file._raw_data = bytearray(save_file._raw_data)

        try:
            inventory = char.inventory_storage_box
            full_msg = "Your grace chest storage is full in this save."
            actual_item_id = item.full_id

            # Generate gaitem_handle and create a gaitem entry for weapons/armor
            if item.category in (ItemCategory.WEAPON, ItemCategory.ARMOR):
                gaitem_handle = self._create_gaitem_entry(char, item, actual_item_id)
                if gaitem_handle is None:
                    CTkMessageBox.showerror(
                        "No free equipment slot",
                        "No free gaitem slot in this save (all map entries appear in use). "
                        "In-game, remove or store an extra weapon or armor, save, re-open "
                        "this file in the editor, then try again.",
                        parent=self.parent,
                    )
                    return
            else:
                # Direct handle (no gaitem row): use 0xB0 prefix for both goods and talismans;
                # the client expects this for common_items without a Gaitem map entry.
                gaitem_handle = (item.id & 0x00FFFFFF) | 0xB0000000

            # Next slot is always index common_item_count; do not use last_used+1
            # (gaps in the array are ignored; the game only reads the first count slots).
            empty_inv_idx = inventory.common_item_count

            if empty_inv_idx >= len(inventory.common_items):
                CTkMessageBox.showerror("Full", full_msg, parent=self.parent)
                return

            # Acquisition index is a global counter; take the max across held + storage
            max_acq = max(
                char.inventory_held.acquisition_index_counter,
                char.inventory_storage_box.acquisition_index_counter,
            )
            for inv_item in (
                list(char.inventory_held.common_items)
                + list(char.inventory_held.key_items)
                + list(char.inventory_storage_box.common_items)
                + list(char.inventory_storage_box.key_items)
            ):
                if (
                    inv_item.gaitem_handle not in (0, 0xFFFFFFFF)
                    and inv_item.acquisition_index > max_acq
                ):
                    max_acq = inv_item.acquisition_index
            acq_index = max_acq + 1

            # Write the new inventory item in memory
            inventory.common_items[empty_inv_idx].gaitem_handle = gaitem_handle
            inventory.common_items[empty_inv_idx].quantity = quantity
            inventory.common_items[empty_inv_idx].acquisition_index = acq_index

            inventory.common_item_count += 1
            inventory.acquisition_index_counter = acq_index + 1
            char.inventory_held.acquisition_index_counter = acq_index + 1
            char.inventory_storage_box.acquisition_index_counter = acq_index + 1

            self._merge_gaitem_game_data_acquired_id(char, actual_item_id)
            self._merge_menu_profile_item_id(char, actual_item_id)

            # Rebuild the full slot and write it back
            slot_bytes = rebuild_slot(char)
            if len(slot_bytes) != 0x280000:
                raise ValueError(
                    f"Rebuilt slot size mismatch: {len(slot_bytes)} != 0x280000"
                )

            CHECKSUM_SIZE = 0x10
            slot_offset = save_file._slot_offsets[slot_idx]
            abs_offset = slot_offset + CHECKSUM_SIZE

            if abs_offset + len(slot_bytes) > len(save_file._raw_data):
                raise ValueError("Write would exceed file bounds")

            save_file._raw_data[abs_offset : abs_offset + len(slot_bytes)] = slot_bytes

            # Re-parse the slot so subsequent spawns see a consistent in-memory state
            try:
                from io import BytesIO
                from er_save_manager.parser.user_data_x import UserDataX
                slot_buf = BytesIO(
                    bytes(
                        save_file._raw_data[abs_offset : abs_offset + len(slot_bytes)]
                    )
                )
                save_file.character_slots[slot_idx] = UserDataX.read(
                    slot_buf, save_file.is_ps, abs_offset, len(slot_bytes)
                )
            except Exception:
                pass

            save_file.recalculate_checksums()

            if save_path:
                save_file.to_file(Path(save_path))

            file_hint = Path(save_path).name if save_path else "save"
            CTkMessageBox.showinfo(
                "Success",
                f"Added {item.name} for character {slot_idx + 1} to the grace chest "
                "(open Chest at a site of grace to see it).\n\n"
                f"File written: {file_hint}\n\n"
                "Fully quit the game, reload this save, then check the chest.",
                parent=self.parent,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            CTkMessageBox.showerror(
                "Error", f"Failed to spawn item: {e}", parent=self.parent
            )

    def _create_gaitem_entry(self, char, item, actual_item_id):
        """
        Allocate a Gaitem entry for a weapon or armor and return the new gaitem_handle.
        Returns None if no empty slot is available.

        Handle indices share a unified namespace across prefixes 0x8/0x9/0xC, so we
        find the next free index globally (starting at 0x80008C) rather than per-category.

        Empties are often 8 bytes on disk; a weapon (21 B) or armor (16 B) is written in
        memory and rebuild_slot extends the prefix, trimming an equal number of bytes
        from the slot tail (see UserDataX.rest / structured_byte_len).
        """
        if item.category == ItemCategory.WEAPON:
            prefix = 0x80000000
        else:
            prefix = 0x90000000

        def _is_empty_gaitem(i: int) -> bool:
            return char.gaitem_map[i].item_id in (0, 0xFFFFFFFF)

        # Collect used indices across ALL existing gaitems (unified namespace)
        used_indices = set()
        for g in char.gaitem_map:
            if g.gaitem_handle != 0 and g.item_id not in (0, 0xFFFFFFFF):
                used_indices.add(g.gaitem_handle & 0x00FFFFFF)

        # Find first gap at or above 0x80008C, otherwise use max+1
        next_idx = 0x80008C
        if used_indices:
            sorted_idx = sorted(used_indices)
            found_gap = False
            for i in range(1, len(sorted_idx)):
                expected = sorted_idx[i - 1] + 1
                if sorted_idx[i] != expected and expected >= 0x80008C:
                    next_idx = expected
                    found_gap = True
                    break
            if not found_gap:
                next_idx = max(sorted_idx[-1] + 1, 0x80008C)

        gaitem_handle = (prefix | next_idx) & 0xFFFFFFFF

        # Find an empty slot in gaitem_map. Prefer a slot inside the category's range.
        category_positions = []
        for i, g in enumerate(char.gaitem_map):
            if g.gaitem_handle != 0 and g.item_id not in (0, 0xFFFFFFFF):
                if (g.gaitem_handle & 0xF0000000) == prefix:
                    category_positions.append(i)

        empty_gaitem_idx = -1
        if category_positions:
            lo, hi = min(category_positions), max(category_positions)
            for i in range(lo, hi + 1):
                if _is_empty_gaitem(i):
                    empty_gaitem_idx = i
                    break
            if empty_gaitem_idx == -1:
                for i in range(hi + 1, len(char.gaitem_map)):
                    if _is_empty_gaitem(i):
                        empty_gaitem_idx = i
                        break
        if empty_gaitem_idx == -1:
            for i, _g in enumerate(char.gaitem_map):
                if _is_empty_gaitem(i):
                    empty_gaitem_idx = i
                    break
        if empty_gaitem_idx == -1:
            return None

        g = char.gaitem_map[empty_gaitem_idx]
        g.gaitem_handle = gaitem_handle
        g.item_id = actual_item_id
        g.unk0x10 = 0
        g.unk0x14 = 0  # MUST stay 0; non-zero corrupts armor equip slots
        if item.category == ItemCategory.WEAPON:
            g.gem_gaitem_handle = 0
            g.unk0x1c = 0
        else:
            g.gem_gaitem_handle = None
            g.unk0x1c = None

        return gaitem_handle
