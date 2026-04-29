"""EldenRing Hub — main window."""

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

from er_save_manager.games.game_profiles import PROFILES_BY_KEY
from er_save_manager.parser import Save
from er_save_manager.platform import PlatformUtils
from er_save_manager.ui.dialogs.save_selector import SaveSelectorDialog
from er_save_manager.ui.editors import RunesEditor, SpawnerEditor, UpgraderEditor
from er_save_manager.ui.messagebox import CTkMessageBox
from er_save_manager.ui.settings import get_settings
from er_save_manager.ui.theme import ThemeManager
from er_save_manager.ui.utils import trace_variable


class SaveManagerGUI:
    """Main application window."""

    def __init__(self, root):
        self.root = root
        self.root.title("EldenRing Hub")

        self.root.geometry("1000x700")
        self.root.minsize(720, 560)

        try:
            if getattr(sys, "frozen", False):
                if hasattr(sys, "_MEIPASS"):
                    base_path = Path(sys._MEIPASS)
                else:
                    base_path = Path(sys.executable).parent
            else:
                base_path = Path(__file__).parent.parent.parent

            icon_path = base_path / "resources" / "icon" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
            else:
                icon_png = base_path / "resources" / "icon" / "icon.png"
                if icon_png.exists():
                    from PIL import Image, ImageTk

                    icon_image = Image.open(icon_png)
                    icon_photo = ImageTk.PhotoImage(icon_image)
                    self.root.iconphoto(True, icon_photo)
        except Exception:
            pass

        self.settings = get_settings()

        theme_name = self.settings.get("theme", None)
        if theme_name is None or theme_name == "dark":
            ctk.set_appearance_mode("dark")
            theme_name = "dark"
        elif theme_name == "bright" or theme_name == "default":
            ctk.set_appearance_mode("light")
            theme_name = "bright"

        ctk.set_default_color_theme("blue")

        self.theme_manager = ThemeManager(theme_name)

        style = ttk.Style()
        style.theme_use("clam")
        self.theme_manager.apply_theme(style)

        self.root.configure(bg=self.theme_manager.get_color("bg"))

        self.default_save_path = Path(os.environ.get("APPDATA", "")) / "EldenRing"
        self.save_file = None
        self.save_path = None
        self.selected_slot = None
        self.selected_slot_index = -1

        self._character_slot_tools_revealed = False
        self._editor_tabs = None

        self.active_game = "elden_ring"

        self._file_load_buttons: list = []

        self.status_var = tk.StringVar(value="Ready")

        self._resize_timer = None
        self._last_width = None
        self._last_height = None

        self.process_monitor = None

        self.setup_ui()

        self.theme_manager.apply_tk_widget_colors(self.root)

        self.root.bind("<Configure>", self._on_window_resize)

        self.root.after(2000, self._init_process_monitor)

    def _on_window_resize(self, event=None):
        """Debounce window resize events to improve responsiveness"""
        if event is None:
            return

        width = event.width
        height = event.height

        if width == self._last_width and height == self._last_height:
            return

        self._last_width = width
        self._last_height = height

        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)

        self._resize_timer = self.root.after(200, self._process_resize)

    def _process_resize(self):
        """Process pending resize -- CTk handles its own layout."""
        self._resize_timer = None

    def _handle_game_running_dialog(self, profile=None) -> bool:
        """
        Show dialog when game is running and handle user choice.
        Blocks loading until game process is terminated.

        Returns:
            True if game was successfully terminated
            False if user cancelled or kill failed
        """
        game_name = profile.name if profile else "Elden Ring"
        process_name = (
            profile.process_name
            if profile and profile.process_name
            else "eldenring.exe"
        )

        result = CTkMessageBox.askyesno(
            "Game is Running",
            f"{game_name} is currently running.\n\n"
            "The save file cannot be loaded while the game is running.\n\n"
            "Would you like to force kill the game process?",
            parent=self.root,
        )

        if not result:
            return False

        if not PlatformUtils.kill_game_process():
            CTkMessageBox.showerror(
                "Error",
                f"Failed to terminate {game_name} process.\n\n"
                "The game may require manual closing or administrator permissions.",
                parent=self.root,
            )
            return False

        import time

        max_wait = 5
        wait_interval = 0.2
        elapsed = 0

        while elapsed < max_wait:
            if not self.is_game_running(process_name):
                CTkMessageBox.showinfo(
                    "Success",
                    f"{game_name} process terminated successfully.\n\n"
                    "You can now proceed safely.",
                    parent=self.root,
                )
                return True
            time.sleep(wait_interval)
            elapsed += wait_interval
            self.root.update()

        CTkMessageBox.showerror(
            "Timeout",
            f"Game process is still running after kill attempt.\n\n"
            f"Please close {game_name} manually and try again.",
            parent=self.root,
        )
        return False

    def _init_process_monitor(self):
        """Initialize auto-backup process monitor"""
        try:
            from er_save_manager.backup.process_monitor import GameProcessMonitor

            self.process_monitor = GameProcessMonitor()
            self.process_monitor.set_backup_callback(self._on_auto_backup_created)
            self.process_monitor.start()

        except Exception as e:
            print(f"Failed to initialize process monitor: {e}")

    def _on_auto_backup_created(self, game_key: str, backup_path):
        """Callback when auto-backup is created."""
        try:
            from er_save_manager.games.game_profiles import PROFILES_BY_KEY
            from er_save_manager.ui.messagebox import CTkMessageBox

            profile = PROFILES_BY_KEY.get(game_key)
            game_name = profile.name if profile else game_key

            self.root.after(
                0,
                lambda: CTkMessageBox.showinfo(
                    "Auto-Backup Created",
                    f"{game_name} launched - backup created:\n\n{backup_path.name}",
                    parent=self.root,
                ),
            )
        except Exception:
            pass

    def show_toast(self, message: str, duration: int = 3000, type: str = "success"):
        """Show toast notification"""
        from er_save_manager.ui.toast import show_toast as _show_toast

        _show_toast(self.root, message, duration, type)

    def setup_ui(self):
        """Setup main UI structure with optimized layout"""
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)
        self.root.grid_columnconfigure(0, weight=1)

        _panel = ("gray93", "#0b1220")
        _accent_line = ("gray76", "#1e293b")
        title_frame = ctk.CTkFrame(
            self.root,
            corner_radius=12,
            fg_color=_panel,
            border_width=1,
            border_color=_accent_line,
        )
        title_frame.grid(row=0, column=0, padx=10, pady=(6, 4), sticky="ew")

        ctk.CTkLabel(
            title_frame,
            text="EldenRing Hub",
            font=("Segoe UI", 17, "bold"),
        ).pack(pady=(6, 0))

        ctk.CTkLabel(
            title_frame,
            text="Character tools unlock after loading a save",
            font=("Segoe UI", 10),
            text_color=("gray30", "gray65"),
        ).pack(pady=(0, 6))

        file_frame = ctk.CTkFrame(
            self.root,
            corner_radius=12,
            fg_color=_panel,
            border_width=1,
            border_color=_accent_line,
        )
        file_frame.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="ew")

        ctk.CTkLabel(
            file_frame,
            text="Elden Ring save (typically ER*.sl2 or CO*.co2)",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=10, pady=(6, 2))

        self.file_path_var = tk.StringVar(value="")
        trace_variable(self.file_path_var, "w", self._on_file_path_changed)

        path_frame = ctk.CTkFrame(
            file_frame,
            corner_radius=10,
            fg_color=("gray90", "#0f172a"),
            border_width=1,
            border_color=("gray82", "#1e3a8a"),
        )
        path_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        ctk.CTkEntry(path_frame, textvariable=self.file_path_var, height=30).pack(
            side=tk.LEFT, fill=ctk.X, expand=True, padx=(0, 6), pady=4
        )

        _browse_btn = ctk.CTkButton(
            path_frame,
            text="Browse",
            command=self.browse_file,
            width=100,
            height=30,
        )
        _browse_btn.pack(side=tk.LEFT, padx=3, pady=4)
        self._file_load_buttons.append(_browse_btn)

        _autofind_btn = ctk.CTkButton(
            path_frame,
            text="Auto-Find",
            command=self.auto_detect,
            width=100,
            height=30,
        )
        _autofind_btn.pack(side=tk.LEFT, padx=3, pady=4)
        self._file_load_buttons.append(_autofind_btn)

        _reload_btn = ctk.CTkButton(
            path_frame,
            text="Reload",
            command=self.load_save,
            width=100,
            height=30,
        )
        _reload_btn.pack(side=tk.LEFT, padx=3, pady=4)
        self._file_load_buttons.append(_reload_btn)

        self.main_content = ctk.CTkFrame(
            self.root,
            corner_radius=12,
            fg_color=_panel,
            border_width=1,
            border_color=_accent_line,
        )
        self.main_content.grid(row=2, column=0, padx=10, pady=(2, 4), sticky="nsew")
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=1)

        self._character_tools_built = False
        self._welcome_frame = ctk.CTkFrame(self.main_content, corner_radius=10)
        self._welcome_frame.grid(row=0, column=0, sticky="nsew")

        welcome_inner = ctk.CTkFrame(
            self._welcome_frame,
            fg_color=("gray92", "#080c17"),
            border_width=1,
            border_color=("gray80", "#1e293b"),
        )
        welcome_inner.pack(fill=ctk.BOTH, expand=True, padx=4, pady=4)

        _welcome_text = (
            "Load your save above to unlock character tools.\n\n"
            "Use Browse to pick a file, or Auto-Find to search common folders.\n"
            "Typical names look like ER0000.sl2 (main) or CO60000.co2 (backup copy)."
        )
        ctk.CTkLabel(
            welcome_inner,
            text=_welcome_text,
            font=("Segoe UI", 12),
            justify="left",
            anchor="w",
            wraplength=760,
            text_color=("gray20", "gray85"),
        ).pack(fill=ctk.BOTH, expand=True, padx=8, pady=8, anchor="nw")

        self._tools_wrapper = ctk.CTkFrame(
            self.main_content, corner_radius=0, fg_color="transparent"
        )

        status_frame = ctk.CTkFrame(
            self.root,
            corner_radius=0,
            fg_color=("gray93", "#080c17"),
            border_width=1,
            border_color=("gray85", "#1e293b"),
        )
        status_frame.grid(row=3, column=0, sticky="ew")

        ctk.CTkLabel(
            status_frame,
            textvariable=self.status_var,
            anchor="w",
            padx=6,
            pady=4,
        ).pack(fill=tk.X)

    def _ensure_character_tools_ui(self):
        """Build and show Character bar after save is loaded."""

        self._welcome_frame.grid_remove()
        if not self._character_tools_built:
            self._build_minimal_tools_ui(self._tools_wrapper)
            self._character_tools_built = True
        self._tools_wrapper.grid(row=0, column=0, sticky="nsew")

    def _reset_slot_dependent_tools(self):
        """Hide Runes / Spawner / Upgrader tabs until Load character succeeds."""
        self._character_slot_tools_revealed = False
        if self._editor_tabs is not None:
            self._editor_tabs.grid_remove()
        if getattr(self, "_slot_load_hint_frame", None) is not None:
            self._slot_load_hint_frame.grid()

    @staticmethod
    def _leading_slot_number(display: str) -> int | None:
        """Parse leading slot digit from combo text (e.g. '3', '3 — Name …')."""
        if not display or not isinstance(display, str):
            return None
        head = display.split(" - ", 1)[0].strip()
        if not head.isdigit():
            return None
        n = int(head)
        if 1 <= n <= 10:
            return n
        return None

    def _build_minimal_tools_ui(self, parent):
        """Slot picker, import .erc, Item Spawner + Upgrader."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            parent,
            text="Character",
            font=("Segoe UI", 14, "bold"),
        ).grid(row=0, column=0, padx=8, pady=(6, 4), sticky="w")

        container = ctk.CTkFrame(
            parent,
            corner_radius=10,
            fg_color=("gray88", "#0f1419"),
            border_width=1,
            border_color=("gray78", "#1e293b"),
        )
        container.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)

        select_frame = ctk.CTkFrame(
            container,
            fg_color=("gray82", "#111827"),
            border_width=1,
            border_color=("gray74", "#312e81"),
        )
        select_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 5))

        ctk.CTkLabel(select_frame, text="Slot:").pack(side=ctk.LEFT, padx=(8, 10))

        self.char_slot_var = ctk.StringVar(value="1")
        self._slot_combo = ctk.CTkComboBox(
            select_frame,
            variable=self.char_slot_var,
            values=[str(i) for i in range(1, 11)],
            state="readonly",
            width=220,
        )
        self._slot_combo.pack(side=ctk.LEFT, padx=(0, 10))

        ctk.CTkButton(
            select_frame,
            text="Load character",
            command=self.load_character_for_edit,
            width=130,
        ).pack(side=ctk.LEFT, padx=(0, 10))

        ctk.CTkButton(
            select_frame,
            text="Import saved data",
            command=self.import_saved_data,
            fg_color="#1e3a8a",
            hover_color="#2563eb",
            width=150,
        ).pack(side=ctk.LEFT)

        self._slot_load_hint_frame = ctk.CTkFrame(
            container,
            fg_color=("gray90", "#0c1018"),
            border_width=1,
            border_color=("gray82", "#1e3a8a"),
        )
        self._slot_load_hint_frame.grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 5)
        )
        ctk.CTkLabel(
            self._slot_load_hint_frame,
            text=(
                "Choose a slot, then press Load character. "
                "That loads that character and unlocks Runes, Item Spawner, and Upgrader below."
            ),
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
            wraplength=760,
            text_color=("gray20", "gray80"),
        ).pack(fill=ctk.X, padx=8, pady=6)

        def current_slot_index() -> int:
            n = self._leading_slot_number(self.char_slot_var.get())
            return n - 1 if n else -1

        editor_tabs = ctk.CTkTabview(
            container,
            fg_color=("gray93", "#080c17"),
            segmented_button_fg_color=("gray76", "#0f172a"),
            segmented_button_selected_color=("#bae6fd", "#1e40af"),
            segmented_button_unselected_color=("gray72", "#1e293b"),
            segmented_button_selected_hover_color=("#93c5fd", "#2563eb"),
            segmented_button_unselected_hover_color=("gray65", "#334155"),
        )
        self._editor_tabs = editor_tabs
        editor_tabs.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

        runes_tab = editor_tabs.add("Runes")
        runes_frame = ctk.CTkFrame(runes_tab, fg_color="transparent")
        runes_frame.pack(fill=ctk.BOTH, expand=True, padx=6, pady=4)
        self.runes_editor = RunesEditor(
            runes_frame,
            lambda: self.save_file,
            current_slot_index,
            lambda: self.save_path,
        )
        self.runes_editor.setup_ui()

        spawner_tab = editor_tabs.add("Item Spawner")
        spawner_frame = ctk.CTkFrame(spawner_tab, fg_color="transparent")
        spawner_frame.pack(fill=ctk.BOTH, expand=True, padx=6, pady=4)
        self.spawner_editor = SpawnerEditor(
            spawner_frame,
            lambda: self.save_file,
            current_slot_index,
            lambda: self.save_path,
        )
        self.spawner_editor.setup_ui()

        upgrader_tab = editor_tabs.add("Upgrader")
        upgrader_frame = ctk.CTkFrame(upgrader_tab, fg_color="transparent")
        upgrader_frame.pack(fill=ctk.BOTH, expand=True, padx=6, pady=4)
        self.upgrader_editor = UpgraderEditor(
            upgrader_frame,
            lambda: self.save_file,
            current_slot_index,
            lambda: self.save_path,
        )
        self.upgrader_editor.setup_ui()

        self._editor_tabs.grid_remove()

    def import_saved_data(self):
        """Import a character from a .erc into the chosen slot."""
        if not self.save_file:
            CTkMessageBox.showwarning(
                "No save", "Load a save file first.", parent=self.root
            )
            return

        profile = self._active_profile()
        if (
            profile
            and profile.process_name
            and self.is_game_running(profile.process_name)
        ):
            CTkMessageBox.showwarning(
                "Game running",
                "Close the game before importing into a save.",
                parent=self.root,
            )
            return

        import_path = filedialog.askopenfilename(
            title="Import saved data",
            filetypes=[("ER Character", "*.erc"), ("All files", "*.*")],
        )
        if not import_path:
            return

        try:
            slot_display = self.char_slot_var.get()
        except Exception:
            slot_display = ""

        n = self._leading_slot_number(slot_display)
        if n is None:
            CTkMessageBox.showwarning(
                "Slot", "Choose a character slot (1–10).", parent=self.root
            )
            return

        to_slot = n - 1
        to_char = self.save_file.characters[to_slot]
        to_is_active = False
        if (
            self.save_file.user_data_10_parsed
            and self.save_file.user_data_10_parsed.profile_summary
        ):
            ap = self.save_file.user_data_10_parsed.profile_summary.active_profiles
            if to_slot < len(ap):
                to_is_active = ap[to_slot]

        if not to_char.is_empty() and to_is_active:
            to_name = to_char.get_character_name()
            if not CTkMessageBox.askyesno(
                "Overwrite?",
                f"Slot {to_slot + 1} has '{to_name}'.\nOverwrite with imported data?",
                parent=self.root,
            ):
                return

        try:
            from er_save_manager.backup.manager import BackupManager
            from er_save_manager.transfer.character_ops import CharacterOperations

            save_path = self.save_path
            if save_path:
                manager = BackupManager(Path(save_path))
                manager.create_backup(
                    description=f"before_import_to_slot_{to_slot + 1}",
                    operation="import_character",
                    save=self.save_file,
                )

            CharacterOperations.import_character(
                self.save_file, to_slot, Path(import_path)
            )
            self.ensure_raw_data_mutable()
            self.save_file.recalculate_checksums()
            if save_path:
                self.save_file.to_file(Path(save_path))

            self.reload_save()
            self.show_toast(f"Imported into slot {to_slot + 1}.", duration=2500)
        except Exception as e:
            CTkMessageBox.showerror("Import failed", str(e), parent=self.root)

    def load_character_for_edit(self):
        """Load character data into editors"""

        if not self.save_file:
            CTkMessageBox.showwarning(
                "No Save", "Please load a save file first!", parent=self.root
            )
            return

        try:
            slot_display = self.char_slot_var.get()
        except Exception:
            slot_display = ""

        n = self._leading_slot_number(slot_display)
        if n is None:
            CTkMessageBox.showwarning(
                "Invalid Slot", "Please choose a character slot.", parent=self.root
            )
            return

        slot_idx = n - 1

        slot = self.save_file.characters[slot_idx]

        if slot.is_empty():
            CTkMessageBox.showwarning(
                "Empty Slot", f"Slot {slot_idx + 1} is empty!", parent=self.root
            )
            return

        if not self._character_slot_tools_revealed:
            self._editor_tabs.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
            self._character_slot_tools_revealed = True
            if getattr(self, "_slot_load_hint_frame", None) is not None:
                self._slot_load_hint_frame.grid_remove()

        self.upgrader_editor.load_items()
        self.spawner_editor.refresh_list()
        self.runes_editor.refresh_from_slot()

        self.status_var.set(f"Loaded character from Slot {slot_idx + 1}")

    def ensure_raw_data_mutable(self):
        """Ensure save file _raw_data is mutable (bytearray)"""
        if self.save_file and isinstance(self.save_file._raw_data, bytes):
            self.save_file._raw_data = bytearray(self.save_file._raw_data)

    def _active_profile(self):
        """Return the GameProfile for the currently selected game."""
        return PROFILES_BY_KEY.get(self.active_game)

    def browse_file(self):
        """Browse for a save file for the active game."""
        profile = self._active_profile()

        if (
            not self.settings.get("skip_game_running_check", False)
            and profile
            and profile.process_name
            and self.is_game_running(profile.process_name)
        ):
            if not self._handle_game_running_dialog(profile):
                return

        initialdir = None
        if self.settings.get("remember_last_location", True):
            last_path = self.settings.get("last_save_path", "")
            if last_path:
                last_dir = os.path.dirname(last_path)
                if os.path.exists(last_dir):
                    initialdir = last_dir

        if not initialdir:
            default_loc = PlatformUtils.get_default_save_location(profile)
            if default_loc and default_loc.exists():
                initialdir = str(default_loc)

        if not initialdir:
            if self.default_save_path.exists():
                initialdir = str(self.default_save_path)

        if not initialdir and PlatformUtils.is_linux():
            steam_base = Path.home() / ".local" / "share" / "Steam"
            if steam_base.exists():
                initialdir = str(steam_base)

        if not initialdir:
            initialdir = str(Path.home())

        if profile:
            ext_str = " ".join(f"*{e}" for e in profile.extensions)
            filetypes = [(f"{profile.name} Saves", ext_str), ("All files", "*.*")]
            title = f"Select {profile.name} Save File"
        else:
            filetypes = [("Save Files", "*.sl2 *.co2"), ("All files", "*.*")]
            title = "Select Save File"

        filename = filedialog.askopenfilename(
            title=title,
            initialdir=initialdir,
            filetypes=filetypes,
        )
        if filename:
            self.file_path_var.set(filename)
            self.status_var.set(f"Selected: {os.path.basename(filename)}")

            if self.settings.get("remember_last_location", True):
                self.settings.set("last_save_path", filename)

            if (
                PlatformUtils.is_linux()
                and not PlatformUtils.is_save_in_default_location(
                    Path(filename), profile
                )
                and self.settings.get("show_linux_save_warning", True)
            ):
                self.show_linux_save_location_warning(Path(filename), profile)

    def auto_detect(self):
        """Auto-detect save file for the active game."""
        profile = self._active_profile()
        found_saves = PlatformUtils.find_all_save_files(profile)
        game_name = profile.name if profile else "Elden Ring"

        if not found_saves:
            if PlatformUtils.is_linux():
                CTkMessageBox.showinfo(
                    "No Saves Found",
                    f"No {game_name} save files found.\n\n"
                    "Make sure you have launched the game at least once.\n"
                    "On Linux, saves are stored in Steam's compatdata folder.",
                    parent=self.root,
                )
            else:
                CTkMessageBox.showwarning(
                    "Not Found",
                    f"No {game_name} save files found.",
                    parent=self.root,
                )
            return

        def _on_selected(path: str):
            self.file_path_var.set(path)
            if (
                PlatformUtils.is_linux()
                and not PlatformUtils.is_save_in_default_location(Path(path), profile)
                and self.settings.get("show_linux_save_warning", True)
            ):
                self.show_linux_save_location_warning(Path(path), profile)

        if len(found_saves) == 1:
            _on_selected(str(found_saves[0]))
            self.status_var.set(f"{game_name} save auto-detected")
        else:
            SaveSelectorDialog.show(self.root, found_saves, _on_selected)

    def show_linux_save_location_warning(self, save_path, profile=None):
        """Show warning about non-default save location on Linux."""
        game_name = profile.name if profile else "Elden Ring"
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Location Warning")
        dialog.geometry("550x500")
        dialog.transient(self.root)

        msg_frame = ttk.Frame(dialog, padding=20)
        msg_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            msg_frame,
            text="Non-Standard Save Location",
            font=("Segoe UI", 12, "bold"),
            foreground="orange",
        ).pack(pady=(0, 10))

        warning_text = (
            f"Your {game_name} save file is located in:\n"
            f"{save_path}\n\n"
            f"This is NOT the default Steam compatdata location!\n\n"
            f'If you remove the custom launcher (e.g. "ersc_launcher.exe") from Steam, '
            f"Steam will remove that compatdata folder and your save will get lost.\n\n"
            f"Recommended: Set a fixed Steam launch option and copy the save file to the "
            f"default location via the 'Copy Save' button below to prevent this."
        )

        ttk.Label(
            msg_frame,
            text=warning_text,
            wraplength=500,
            justify=tk.LEFT,
        ).pack(pady=10)

        launch_option = PlatformUtils.get_steam_launch_option_hint(profile)
        if launch_option:
            ttk.Label(
                msg_frame,
                text="Add this to the custom launcher's Steam launch options:",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor=tk.W, pady=(10, 5))

            option_frame = ttk.Frame(msg_frame)
            option_frame.pack(fill=tk.X, pady=5)

            option_entry = ttk.Entry(option_frame, font=("Consolas", 11))
            option_entry.insert(0, launch_option)
            option_entry.config(state="readonly")
            option_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

            def copy_to_clipboard():
                dialog.clipboard_clear()
                dialog.clipboard_append(launch_option)
                dialog.update()
                CTkMessageBox.showinfo(
                    "Copied", "Launch option copied to clipboard!", parent=dialog
                )

            ctk.CTkButton(
                option_frame, text="Copy", command=copy_to_clipboard, width=80
            ).pack(side=tk.LEFT, padx=5)

        def copy_to_default():
            target_dir = PlatformUtils.get_default_save_location(profile)
            current_path = Path(save_path)
            steamid = current_path.parent.name
            if target_dir and steamid:
                target_dir = target_dir / steamid

            if target_dir:
                if CTkMessageBox.askyesno(
                    "Copy Save",
                    f"Copy save file to:\n{target_dir}\n\nThe original file will remain in its current location.",
                    parent=self.root,
                ):
                    try:
                        import shutil

                        target_dir.mkdir(parents=True, exist_ok=True)
                        new_path = target_dir / current_path.name
                        shutil.copy2(save_path, new_path)
                        self.file_path_var.set(str(new_path))
                        CTkMessageBox.showinfo(
                            "Success",
                            f"Save file copied to:\n{new_path}\n\nOriginal file remains at:\n{save_path}",
                            parent=self.root,
                        )
                        dialog.destroy()
                    except Exception as e:
                        CTkMessageBox.showerror(
                            "Error", f"Failed to copy save:\n{e}", parent=self.root
                        )

        def dont_show_again():
            self.settings.set("show_linux_save_warning", False)
            dialog.destroy()

        button_frame = ttk.Frame(msg_frame)
        button_frame.pack(pady=10)

        ttk.Button(
            button_frame, text="Copy to Default", command=copy_to_default, width=18
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame, text="Keep Current", command=dialog.destroy, width=15
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            button_frame, text="Don't Show Again", command=dont_show_again, width=18
        ).pack(side=tk.LEFT, padx=5)

    def is_game_running(self, process_name: str = "eldenring.exe") -> bool:
        """Check if a game process is running."""
        if process_name == "eldenring.exe":
            return PlatformUtils.is_game_running()
        try:
            if PlatformUtils.is_windows():
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0  # SW_HIDE
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    startupinfo=si,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                return (
                    process_name.lower()
                    in result.stdout.decode(errors="replace").lower()
                )
            else:
                result = subprocess.run(
                    ["pgrep", "-f", process_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return result.returncode == 0
        except Exception:
            return False

    def _get_game_folder(self) -> Path | None:
        """Attempt to detect the Elden Ring installation folder."""
        try:
            if PlatformUtils.is_windows():
                import winreg

                try:
                    key = winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\WOW6432Node\Valve\Steam",
                    )
                    steam_path = Path(winreg.QueryValueEx(key, "InstallPath")[0])
                    winreg.CloseKey(key)

                    game_folder = steam_path / "steamapps" / "common" / "ELDEN RING"
                    if game_folder.exists():
                        return game_folder

                    library_file = steam_path / "steamapps" / "libraryfolders.vdf"
                    if library_file.exists():
                        content = library_file.read_text(encoding="utf-8")
                        import re

                        paths = re.findall(r'"path"\s+"(.+?)"', content)
                        for path_str in paths:
                            lib_path = Path(path_str.replace("\\\\", "\\"))
                            game_folder = (
                                lib_path / "steamapps" / "common" / "ELDEN RING"
                            )
                            if game_folder.exists():
                                return game_folder

                except Exception:
                    pass

            common_paths = [
                Path("C:/Program Files (x86)/Steam/steamapps/common/ELDEN RING"),
                Path("C:/Program Files/Steam/steamapps/common/ELDEN RING"),
                Path.home()
                / ".steam"
                / "steam"
                / "steamapps"
                / "common"
                / "ELDEN RING",
                Path.home()
                / ".local"
                / "share"
                / "Steam"
                / "steamapps"
                / "common"
                / "ELDEN RING",
            ]

            for path in common_paths:
                if path.exists():
                    return path

        except Exception:
            pass

        return None

    def _on_file_path_changed(self, *args):
        """Auto-load save file when a valid file path is entered."""
        save_path = self.file_path_var.get()
        if not save_path or not os.path.exists(save_path):
            return

        if self.active_game == "elden_ring":
            filename = os.path.basename(save_path).lower()
            if filename.startswith("er"):
                self.root.after(500, self.load_save)
        else:
            self._load_non_er_save(save_path)

    def _load_non_er_save(self, save_path: str):
        """Store path for non-ER games selected from Browse (minimal UI)."""
        profile = self._active_profile()
        if (
            not self.settings.get("skip_game_running_check", False)
            and profile
            and profile.process_name
            and self.is_game_running(profile.process_name)
        ):
            if not self._handle_game_running_dialog(profile):
                return

        self.save_path = Path(save_path)
        self.save_file = None
        self.status_var.set(f"Selected: {os.path.basename(save_path)}")
        self.show_toast(
            f"Save file loaded: {os.path.basename(save_path)}", duration=2500
        )

    def on_slot_selected(self, slot_index: int):
        """Handle character slot selection from Fixer tab."""
        self.selected_slot_index = slot_index

    def load_save(self, silent=False):
        """Load save file in background thread to prevent UI freezing

        Args:
            silent: If True, suppress the success message (used for reloads after operations)
        """
        save_path = self.file_path_var.get()

        if not save_path or not os.path.exists(save_path):
            CTkMessageBox.showerror(
                "Error", "Please select a valid save file first!", parent=self.root
            )
            return

        profile = self._active_profile()
        process_name = (
            profile.process_name
            if profile and profile.process_name
            else "eldenring.exe"
        )
        if not self.settings.get(
            "skip_game_running_check", False
        ) and self.is_game_running(process_name):
            if not self._handle_game_running_dialog(profile):
                return

        if (
            self.active_game == "elden_ring"
            and save_path.lower().endswith(".sl2")
            and self.settings.get("show_eac_warning", True)
        ):
            warning_dialog = tk.Toplevel(self.root)
            warning_dialog.title("⚠️ EAC Warning - Vanilla Save File Detected")
            warning_dialog.geometry("520x420")
            warning_dialog.transient(self.root)
            warning_dialog.grab_set()

            msg_frame = ttk.Frame(warning_dialog, padding=20)
            msg_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(
                msg_frame,
                text="⚠️ EAC Warning - Vanilla Save File Detected",
                font=("Segoe UI", 12, "bold"),
                foreground="red",
            ).pack(pady=(0, 10))

            warning_text = (
                "You are loading a Vanilla save file (.sl2).\n\n"
                "WARNING: Modifying save files can result in a BAN if:\n"
                "• Easy Anti-Cheat (EAC) is enabled\n"
                "• You play online with modified saves\n\n"
                "To avoid bans:\n"
                "1. Launch Elden Ring with EAC disabled\n"
                "2. Only play offline with modified saves\n"
                "3. Do not use modified saves in online/multiplayer\n\n"
                "Do you understand and want to continue?"
            )

            ttk.Label(
                msg_frame,
                text=warning_text,
                wraplength=470,
                justify=tk.LEFT,
            ).pack(pady=10)

            dont_show_var = tk.BooleanVar(value=False)
            ttk.Checkbutton(
                msg_frame,
                text="Don't show this warning again",
                variable=dont_show_var,
            ).pack(pady=10)

            button_frame = ttk.Frame(msg_frame)
            button_frame.pack(pady=10)

            result = {"continue": False}

            def on_yes():
                if dont_show_var.get():
                    self.settings.set("show_eac_warning", False)
                result["continue"] = True
                warning_dialog.destroy()

            def on_no():
                result["continue"] = False
                warning_dialog.destroy()

            ttk.Button(
                button_frame, text="Yes, Continue", command=on_yes, width=15
            ).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="No, Cancel", command=on_no, width=15).pack(
                side=tk.LEFT, padx=5
            )

            self.root.wait_window(warning_dialog)

            if not result["continue"]:
                self.status_var.set("Load cancelled by user")
                return

        self.status_var.set("Loading save file...")
        thread = threading.Thread(
            target=self._load_save_background, args=(save_path, silent), daemon=True
        )
        thread.start()

    def _load_save_background(self, save_path, silent=False):
        """Background thread for loading save file"""
        try:
            verbose = self.settings.get("verbose_logging", False)
            if verbose:
                self._verbose_log(f"Loading save: {save_path}")

            save_file = Save.from_file(save_path)

            if verbose:
                self._verbose_log(f"Parsed successfully: {save_path}")

            self.root.after(0, self._finalize_save_load, save_file, save_path, silent)
        except Exception as e:
            error_msg = str(e)
            if self.settings.get("verbose_logging", False):
                self._verbose_log(f"Load failed: {save_path} -- {error_msg}")

            self.root.after(
                0,
                lambda: CTkMessageBox.showerror(
                    "Error", f"Failed to load save file:\n{error_msg}", parent=self.root
                ),
            )
            self.root.after(0, lambda: self.status_var.set("Load failed"))

    def reload_save(self):
        """Reload the current save file without showing success message"""
        self.load_save(silent=True)

    def _finalize_save_load(self, save_file, save_path, silent=False):
        """Finalize save loading on main thread"""
        self.save_file = save_file
        self.save_path = Path(save_path)

        self._ensure_character_tools_ui()
        self._reset_slot_dependent_tools()

        if self.active_game == "elden_ring":
            self._update_character_editor_slots()

        self.status_var.set(f"Loaded: {os.path.basename(save_path)}")
        if not silent:
            self.show_toast("Save file loaded successfully!", duration=2500)

    def _update_character_editor_slots(self):
        """Update Character Editor slot dropdown with character names"""
        if not self.save_file:
            return

        slot_names = []
        profiles = None

        try:
            if self.save_file.user_data_10_parsed:
                profiles = self.save_file.user_data_10_parsed.profile_summary.profiles
        except Exception:
            pass

        for i in range(10):
            slot_num = i + 1
            char = self.save_file.characters[i]

            if char.is_empty():
                slot_names.append(f"{slot_num} - Empty")
                continue

            char_name = "Unknown"
            lvl = None
            pg = getattr(char, "player_game_data", None)
            if pg is not None:
                try:
                    lvl = getattr(pg, "level", None)
                except Exception:
                    lvl = None
            if profiles and i < len(profiles):
                try:
                    char_name = profiles[i].character_name or "Unknown"
                except Exception:
                    pass

            lvl_part = ""
            try:
                if lvl is not None:
                    lvl_part = f"  Lv {int(lvl)}"
            except (TypeError, ValueError):
                lvl_part = ""

            slot_names.append(f"{slot_num} - {char_name}{lvl_part}")

        if hasattr(self, "char_slot_var"):
            for widget in self.root.winfo_children():
                self._update_combobox_recursive(widget, slot_names)

    def _update_combobox_recursive(self, widget, values):
        """Recursively find and update character slot combobox"""
        try:
            if isinstance(widget, ctk.CTkComboBox):
                if (
                    hasattr(widget, "cget")
                    and widget.cget("variable") == self.char_slot_var
                ):
                    current = self.char_slot_var.get()
                    widget.configure(values=values)
                    n_sel = SaveManagerGUI._leading_slot_number(current)
                    if n_sel is not None:
                        idx = n_sel - 1
                        if idx < len(values):
                            self.char_slot_var.set(values[idx])
                    return

            for child in widget.winfo_children():
                self._update_combobox_recursive(child, values)
        except Exception:
            pass

    def _verbose_log(self, message: str) -> None:
        """Write a timestamped line to the verbose log file next to the current save."""
        import datetime

        save_path = self.file_path_var.get() if hasattr(self, "file_path_var") else ""
        log_dir = Path(save_path).parent if save_path else Path.home()
        log_path = log_dir / "er_save_manager.log"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except OSError:
            pass


def main():
    """Main entry point for GUI"""
    root = ctk.CTk()
    app = SaveManagerGUI(root)

    def on_closing():
        if app.process_monitor:
            app.process_monitor.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
