import tkinter as tk
import customtkinter as ctk
from pathlib import Path
import struct

from er_save_manager.ui.messagebox import CTkMessageBox
from er_save_manager.ui.utils import bind_mousewheel
from er_save_manager.data.item_database import get_item_name

class UpgraderEditor:
    """Safe item upgrader for weapons and spirit ashes"""

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
        self.level_var = ctk.StringVar(value="0")
        self.listbox = None
        self.lbl_selected = None
        self.btn_upgrade = None
        self.entry_level = None
        self._filter_job = None

        self.upgradeable_items = []
        self.displayed_items = []
        self._current_sel_item = None

    @staticmethod
    def _item_key(item: dict) -> tuple:
        if item["type"] == "weapon":
            return ("weapon", item["idx"])
        return ("spirit", item.get("inv_type"), item["idx"], item.get("name"))

    def setup_ui(self):
        """Setup the upgrader UI"""
        frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        frame.pack(fill=ctk.BOTH, expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            frame,
            text="Weapons and Spirit Ashes from your pocket inventory.",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 4))

        ctk.CTkLabel(
            frame,
            text=(
                "Warning: Confirm each item's maximum upgrade level before setting New Level "
                "(somber vs standard smithing differs; Spirit Ashes follow their own cap). "
                "Check in-game or a wiki. Too high risks corruption or a broken inventory row."
            ),
            font=("Segoe UI", 10),
            justify="left",
            anchor="w",
            wraplength=720,
            text_color=("#b45309", "#fcd34d"),
        ).grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))

        search_frame = ctk.CTkFrame(frame, fg_color="transparent")
        search_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=0)
        
        ctk.CTkLabel(search_frame, text="Search:").pack(side=ctk.LEFT)
        self.search_var.trace_add("write", lambda *_a: self._schedule_refresh_filter())

        ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200).pack(
            side=ctk.LEFT, padx=5
        )
        
        ctk.CTkButton(search_frame, text="Refresh Items", command=self.load_items, width=120).pack(side=ctk.RIGHT, padx=5)

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
        self.listbox.bind("<<ListboxSelect>>", self.on_item_select)

        # Bottom Frame: Upgrade Controls
        bot_frame = ctk.CTkFrame(frame, fg_color=("gray86", "gray25"))
        bot_frame.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        
        self.lbl_selected = ctk.CTkLabel(bot_frame, text="Selected: None", font=("Segoe UI", 12, "bold"))
        self.lbl_selected.pack(side=ctk.LEFT, padx=8, pady=6)

        ctk.CTkLabel(bot_frame, text="New Level:").pack(side=ctk.LEFT, padx=(12, 5), pady=6)

        self.entry_level = ctk.CTkEntry(bot_frame, textvariable=self.level_var, width=50)
        self.entry_level.pack(side=ctk.LEFT, padx=4, pady=6)
        self.entry_level.bind(
            "<FocusIn>",
            lambda _e=None: self._sync_level_display_from_selected(),
        )

        self.btn_upgrade = ctk.CTkButton(
            bot_frame, 
            text="Apply Upgrade", 
            command=self.apply_upgrade, 
            state="disabled", 
            fg_color="#b58900", 
            hover_color="#cb9b00",
            width=120
        )
        self.btn_upgrade.pack(side=ctk.LEFT, padx=8, pady=6)

    def _schedule_refresh_filter(self):
        """Debounce search typing so list filter does not wipe selection every keystroke."""
        if self._filter_job is not None:
            try:
                self.listbox.after_cancel(self._filter_job)
            except tk.TclError:
                pass
            self._filter_job = None

        def _run():
            self._filter_job = None
            self.refresh_list()

        if self.listbox is not None:
            self._filter_job = self.listbox.after(140, _run)

    def _apply_selected_item_from_index(self, idx: int):
        item = self.displayed_items[idx]
        self._current_sel_item = item
        self.lbl_selected.configure(text=f"Selected: {item['name']}")
        self.level_var.set(str(item["level"]))
        self.btn_upgrade.configure(state="normal")

    def _sync_level_display_from_selected(self):
        """When focusing the level field, restore the current upgrade from the list / selection."""
        sel = self.listbox.curselection() if self.listbox else ()
        if sel:
            ri = int(sel[0])
            if 0 <= ri < len(self.displayed_items):
                lvl = self.displayed_items[ri]["level"]
                self.level_var.set(str(lvl))
                self._current_sel_item = self.displayed_items[ri]
                return
        if self._current_sel_item is not None:
            self.level_var.set(str(self._current_sel_item["level"]))
            self.lbl_selected.configure(text=f"Selected: {self._current_sel_item['name']}")
            self.btn_upgrade.configure(state="normal")

    def refresh_list(self, restore_key: tuple | None = None):
        """Refresh the listbox based on search filter; optionally restore selection by item key."""
        if self.listbox is None or self.lbl_selected is None:
            return

        if restore_key is None and self._current_sel_item is not None:
            restore_key = self._item_key(self._current_sel_item)

        self.listbox.delete(0, tk.END)
        search_query = self.search_var.get().lower()

        self.displayed_items = []
        for item in self.upgradeable_items:
            if search_query in item["name"].lower():
                lvl = item["level"]
                lvl_str = f"+{lvl}" if lvl > 0 else ""
                display_text = f"{item['name']} {lvl_str}".strip()

                type_str = "[Weapon]" if item["type"] == "weapon" else "[Spirit Ash]"

                self.listbox.insert(tk.END, f"{type_str} {display_text}")
                self.displayed_items.append(item)

        restore_idx = None
        if restore_key is not None:
            for i, dit in enumerate(self.displayed_items):
                if self._item_key(dit) == restore_key:
                    restore_idx = i
                    break

        if restore_idx is not None:
            self.listbox.selection_set(restore_idx)
            self.listbox.activate(restore_idx)
            self._apply_selected_item_from_index(restore_idx)
        elif not self.displayed_items:
            self._current_sel_item = None
            self.lbl_selected.configure(text="Selected: None")
            self.level_var.set("0")
            self.btn_upgrade.configure(state="disabled")
        elif self._current_sel_item is not None:
            self.lbl_selected.configure(
                text=f"Selected: {self._current_sel_item['name']} (narrow Search to show in list)",
            )
            self.btn_upgrade.configure(state="normal")

    def on_item_select(self, event=None):
        """Handle item selection in the listbox."""
        if self.listbox is None:
            return
        selection = self.listbox.curselection()
        if not selection:
            if self._current_sel_item is not None:
                self.lbl_selected.configure(text=f"Selected: {self._current_sel_item['name']}")
                self.btn_upgrade.configure(state="normal")
                self.level_var.set(str(self._current_sel_item["level"]))
            return

        self._apply_selected_item_from_index(int(selection[0]))

    def _get_inventory_offsets(self, char):
        offset = char.data_start + 32
        for g in char.gaitem_map:
            offset += g.get_size()
            
        offset += 432 # PlayerGameData
        offset += 13 * 16 # SPEffect
        offset += 88 # EquippedItemsEquipIndex
        offset += 28 # ActiveWeaponSlotsAndArmStyle
        offset += 88 # EquippedItemsItemIds
        offset += 88 # EquippedItemsGaitemHandles
        
        held_offset = offset
        
        offset += 4 + (2688 * 12) + 4 + (384 * 12) + 8
        offset += 116 # EquippedSpells
        offset += 140 # EquippedItems
        offset += 24 # EquippedGestures
        offset += 4 + (char.acquired_projectiles.count * 8)
        offset += 156 # EquippedArmamentsAndItems
        offset += 12 # EquippedPhysics
        offset += 303 # FaceData
        
        storage_offset = offset
        return held_offset, storage_offset

    def load_items(self):
        """Load upgradeable items from the current character"""
        save_file = self.get_save_file()
        if not save_file:
            return

        slot_idx = self.get_char_slot()
        if slot_idx < 0:
            return

        char = save_file.characters[slot_idx]
        if char.is_empty():
            return

        preserve_key = (
            self._item_key(self._current_sel_item)
            if self._current_sel_item is not None
            else None
        )

        self.upgradeable_items.clear()
        
        import re
        from er_save_manager.data.item_database import get_item_database, ItemCategory
        db = get_item_database()
        
        # 1. WEAPONS
        for i, gaitem in enumerate(char.gaitem_map):
            # Skip empty slots
            if gaitem.item_id in (0, 0xFFFFFFFF):
                continue
                
            category = gaitem.item_id & 0xF0000000
            
            if category == ItemCategory.WEAPON and gaitem.unk0x10 is not None:
                name = get_item_name(gaitem.item_id)
                if not name.startswith("Unknown"):
                    self.upgradeable_items.append({
                        'idx': i,
                        'gaitem': gaitem,
                        'name': name,
                        'type': 'weapon',
                        'level': gaitem.unk0x10,
                        'max_level': 25
                    })
                    
        # 2. SPIRIT ASHES (GOODS)
        for inv_type, inv in [('held', char.inventory_held.common_items), ('storage', char.inventory_storage_box.common_items)]:
            for i, inv_item in enumerate(inv):
                if inv_item.gaitem_handle == 0 or inv_item.quantity == 0:
                    continue
                    
                base_id = inv_item.gaitem_handle & 0x0FFFFFFF
                handle_type = inv_item.gaitem_handle & 0xF0000000
                
                if handle_type == 0xB0000000:
                    item_id = base_id | 0x40000000
                    item_obj = db.get_item_by_id(item_id)
                    if not item_obj: continue
                    
                    name = item_obj.name
                    
                    # Determine base name and current level
                    match = re.match(r'^(.*?) \+(\d+)$', name)
                    if match:
                        base_name = match.group(1)
                        current_level = int(match.group(2))
                    else:
                        base_name = name
                        current_level = 0
                        
                    # Exclude flasks and common items
                    if "Flask" in base_name or ("Tear" in base_name and "Mimic" not in base_name):
                        continue
                        
                    # Check if it's upgradeable by looking for the +1 variant
                    base_items = db.search_items(base_name)
                    has_upgrades = any(x.name == f"{base_name} +1" and x.category == ItemCategory.GOODS for x in base_items)
                    
                    if has_upgrades:
                        # Find base item ID
                        base_item = next((x for x in base_items if x.name == base_name and x.category == ItemCategory.GOODS), None)
                        if base_item:
                            self.upgradeable_items.append({
                                'idx': i,
                                'inv_type': inv_type,
                                'name': base_name,
                                'type': 'spirit',
                                'level': current_level,
                                'max_level': 10,
                                'base_id': base_item.id
                            })
                
        self.refresh_list(restore_key=preserve_key)

    def apply_upgrade(self):
        """Apply the upgrade to the selected item safely"""
        save_file = self.get_save_file()
        if not save_file:
            return

        slot_idx = self.get_char_slot()
        if slot_idx < 0:
            return

        selection = self.listbox.curselection()
        if selection:
            item = self.displayed_items[int(selection[0])]
        elif self._current_sel_item is not None:
            item = self._current_sel_item
        else:
            CTkMessageBox.showwarning(
                "No item selected",
                "Select an upgradeable item in the list first.",
                parent=self.parent,
            )
            return

        gaitem_idx = item["idx"]
        name = item["name"]
        item_type = item["type"]
        max_level = item["max_level"]
        
        try:
            new_lvl = int(self.level_var.get())
            if new_lvl < 0 or new_lvl > max_level:
                CTkMessageBox.showwarning("Warning", f"Upgrade level for this item should be between 0 and {max_level}.", parent=self.parent)
                if new_lvl < 0: new_lvl = 0
                if new_lvl > max_level: new_lvl = max_level
                self.level_var.set(str(new_lvl))
        except ValueError:
            CTkMessageBox.showerror("Error", "Please enter a valid number.", parent=self.parent)
            return
            
        # Create backup
        save_path = self.get_save_path()
        if save_path:
            from er_save_manager.backup.manager import BackupManager
            manager = BackupManager(Path(save_path))
            manager.create_backup(
                description=f"before_upgrade_{name}_slot_{slot_idx + 1}",
                operation="upgrade_item",
                save=save_file,
            )

        char = save_file.characters[slot_idx]
        
        # Ensure _raw_data is mutable
        if isinstance(save_file._raw_data, bytes):
            save_file._raw_data = bytearray(save_file._raw_data)
            
        if item_type == 'weapon':
            # Update the gaitem in memory
            char.gaitem_map[gaitem_idx].unk0x10 = new_lvl
            
            old_item_id = char.gaitem_map[gaitem_idx].item_id
            base_id = (old_item_id // 100) * 100
            new_item_id = base_id + new_lvl
            char.gaitem_map[gaitem_idx].item_id = new_item_id
            
            # Calculate the absolute byte offset of this gaitem in the save file
            gaitem_offset = char.data_start + 32
            for i in range(gaitem_idx):
                gaitem_offset += char.gaitem_map[i].get_size()
                
            # item_id is located 4 bytes into the Gaitem structure
            item_id_offset = gaitem_offset + 4
            save_file._raw_data[item_id_offset:item_id_offset+4] = struct.pack("<I", new_item_id)
            
            # unk0x10 (upgrade level) is located 8 bytes into the Gaitem structure
            unk0x10_offset = gaitem_offset + 8
            # Write the new level directly to raw data
            save_file._raw_data[unk0x10_offset:unk0x10_offset+4] = struct.pack("<i", new_lvl)
            
            # Also update equipped items if this weapon is currently equipped
            target_handle = char.gaitem_map[gaitem_idx].gaitem_handle
            
            # Calculate offsets for equipment structures
            offset = char.data_start + 32
            for g in char.gaitem_map:
                offset += g.get_size()
                
            offset += 432 # PlayerGameData
            offset += 13 * 16 # SPEffect
            offset += 88 # EquippedItemsEquipIndex
            offset += 28 # ActiveWeaponSlotsAndArmStyle
            
            item_ids_offset = offset
            offset += 88 # EquippedItemsItemIds
            gaitem_handles_offset = offset
            
            # Check the 22 equipment slots (each is 4 bytes)
            for slot_idx in range(22):
                handle_offset = gaitem_handles_offset + (slot_idx * 4)
                handle = struct.unpack("<I", save_file._raw_data[handle_offset:handle_offset+4])[0]
                if handle == target_handle:
                    # Update the corresponding item_id
                    id_offset = item_ids_offset + (slot_idx * 4)
                    save_file._raw_data[id_offset:id_offset+4] = struct.pack("<I", new_item_id)
                    
            # Also update EquippedArmamentsAndItems
            offset += 88 # EquippedItemsGaitemHandles
            offset += 4 + (2688 * 12) + 4 + (384 * 12) + 8 # InventoryHeld
            offset += 116 # EquippedSpells
            offset += 140 # EquippedItems
            offset += 24 # EquippedGestures
            offset += 4 + (char.acquired_projectiles.count * 8) # AcquiredProjectiles
            
            armaments_offset = offset
            # Check the first 18 slots (weapons, ammo, armor, talismans)
            for slot_idx in range(18):
                id_offset = armaments_offset + (slot_idx * 4)
                current_id = struct.unpack("<I", save_file._raw_data[id_offset:id_offset+4])[0]
                if current_id == old_item_id:
                    save_file._raw_data[id_offset:id_offset+4] = struct.pack("<I", new_item_id)
            
        elif item_type == 'spirit':
            inv_type = item['inv_type']
            inv_idx = item['idx']
            
            # Spirit Ashes store their level in the item_id itself
            # The gaitem_handle is base_id | 0xB0000000
            new_base_id = item['base_id'] + new_lvl
            new_handle = new_base_id | 0xB0000000
            
            held_offset, storage_offset = self._get_inventory_offsets(char)
            
            if inv_type == 'held':
                # Update in memory
                char.inventory_held.common_items[inv_idx].gaitem_handle = new_handle
                # Calculate raw offset: held_offset + 4 (count) + inv_idx * 12
                item_offset = held_offset + 4 + (inv_idx * 12)
            else:
                char.inventory_storage_box.common_items[inv_idx].gaitem_handle = new_handle
                item_offset = storage_offset + 4 + (inv_idx * 12)
                
            # Write the new gaitem_handle directly to raw data (first 4 bytes of InventoryItem)
            save_file._raw_data[item_offset:item_offset+4] = struct.pack("<I", new_handle)
        
        # Recalculate checksums
        save_file.recalculate_checksums()
        
        # Save to disk
        if save_path:
            save_file.save(save_path)
        
        CTkMessageBox.showinfo(
            "Success",
            f"Upgraded {name} to +{new_lvl}!\n\nChanges have been saved to the file.",
            parent=self.parent,
        )

        self.load_items()