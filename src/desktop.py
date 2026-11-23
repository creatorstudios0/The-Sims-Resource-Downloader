"""Sims 4 download queue and mod library for Windows."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, SimpleQueue
import json
import msvcrt
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from uuid import uuid4
import webbrowser

from config import CONFIG, CURRENT_DIR, PROJECT_DIR
from desktop_data import DETAILS, fetch_item, inspect_item, parse_url, save_json
from exceptions import InvalidURL
from sims_install import install, install_plan, verify_record
from windows_folders import app_data, default_downloads, detect_game

FROZEN = getattr(sys, "frozen", False)
DATA_DIR = app_data() if FROZEN else Path(PROJECT_DIR)
SESSION_DIR = DATA_DIR if FROZEN else Path(CURRENT_DIR)


STATE_PATH = DATA_DIR / "desktop-state.json"
READY = {"Review", "Queued", "Download failed", "Paused"}
WORKING = {"Checking", "Downloading"}
WINDOW_BG = "#101820"
PANEL_BG = "#17242d"
INPUT_BG = "#1f303c"
TEXT = "#eaf3f5"
MUTED = "#aac1ca"
ACCENT = "#79e2b7"
SELECTED = "#315766"


class DesktopApp:
    def __init__(self, root):
        self.root = root
        root.title("Sims 4 Mod Library")
        root.geometry("1100x740")
        root.minsize(900, 620)
        root.configure(background=WINDOW_BG)
        self.state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
        self.settings = self.state.setdefault("settings", {})
        self.settings.setdefault("downloads", str(default_downloads(CONFIG["downloadDirectory"])))
        self.settings.setdefault("workers", CONFIG["maxActiveDownloads"])
        self.settings.setdefault("organize", CONFIG.get("organizeDownloads", True))
        self.settings.setdefault("watch", False)
        if "game" not in self.state:
            game = detect_game()
            if game:
                self.state["game"] = str(game)
        self.items = self.state.setdefault("items", {})
        self.batches = self.state.setdefault("installs", {})
        self.state.setdefault("profiles", {})
        self.events = SimpleQueue()
        self.metadata = ThreadPoolExecutor(max_workers=2)
        self.transfers = ThreadPoolExecutor(max_workers=10)
        self.active = set()
        self.inspections = set()
        self.paused = True
        self.closing = False
        self.last_clipboard = ""
        self.import_legacy_queue()
        for item in self.items.values():
            if item["status"] == "Downloading":
                item["status"] = "Paused"
            if item["status"] == "Checking":
                item["status"] = "New"
        self.build()
        self.persist()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.tick)
        root.after(650, self.watch_clipboard)

    def build(self):
        self.configure_style()
        frame = ttk.Frame(self.root, padding=(24, 18))
        frame.pack(fill="both", expand=True)
        header = ttk.Frame(frame)
        header.pack(fill="x", pady=(0, 17))
        ttk.Label(header, text="◆", style="Mark.TLabel").pack(side="left", padx=(0, 10))
        ttk.Label(header, text="Sims 4 Mod Library", style="Heading.TLabel").pack(side="left")
        self.release_button = ttk.Button(header, text="Check releases", command=lambda: webbrowser.open(
            "https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases"
        ))
        self.release_button.pack(side="right")
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill="both", expand=True)
        queue_tab = ttk.Frame(self.tabs, padding=16)
        library_tab = ttk.Frame(self.tabs, padding=16)
        installs_tab = ttk.Frame(self.tabs, padding=16)
        self.settings_tab = ttk.Frame(self.tabs, padding=18)
        for tab, name in ((queue_tab, "Download queue"), (library_tab, "Library"),
                          (installs_tab, "Install history"), (self.settings_tab, "Settings")):
            self.tabs.add(tab, text=name)

        ttk.Label(queue_tab, text="Paste one or more TSR item links to review.").pack(anchor="w")
        self.links = tk.Text(queue_tab, height=3, wrap="word", font=("Segoe UI", 10),
                             bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, selectbackground=SELECTED,
                             relief="flat", padx=9, pady=7, highlightthickness=1,
                             highlightbackground=SELECTED, highlightcolor=ACCENT)
        self.links.pack(fill="x", pady=(4, 8))
        toolbar = self.toolbar(queue_tab, [
            ("Review links", self.review_links), ("Download selected", self.queue_selected),
            ("Retry / recheck", self.retry_selected), ("Remove", self.remove_selected),
            ("Dependencies", self.show_dependencies),
        ])
        self.watch = tk.BooleanVar(value=self.settings["watch"])
        ttk.Checkbutton(toolbar, text="Watch clipboard", variable=self.watch, command=self.save_watch).pack(side="right")
        self.queue_tree = self.table(queue_tab, [("Item", 290), ("Creator", 105), ("Status", 115), ("Detail", 270)])
        self.queue_tree.bind("<Double-1>", lambda _event: self.show_dependencies())
        toolbar = self.toolbar(queue_tab, [("Pause / resume queue", self.toggle_queue)])
        self.queue_status = ttk.Label(toolbar)
        self.queue_status.pack(side="left", padx=8)

        toolbar = self.toolbar(library_tab, [("Add local files", self.add_local), ("Install preview", self.preview_install),
                     ("Open folder", self.open_file_folder), ("Category", self.change_category),
                     ("Dependencies", lambda: self.show_dependencies(self.library_tree))])
        self.search = tk.StringVar()
        ttk.Label(toolbar, text="Search").pack(side="left", padx=(12, 4))
        ttk.Entry(toolbar, textvariable=self.search, width=22).pack(side="left")
        self.search.trace_add("write", lambda *_: self.refresh())
        self.toolbar(library_tab, [("Save profile", self.save_profile), ("Load profile", self.load_profile),
                                  ("Clear profile filter", self.clear_profile),
                                  ("Export links", self.export_links), ("Import links", self.import_links)])
        self.profile_filter = None
        self.library_tree = self.table(library_tab, [("Item", 320), ("Creator", 120), ("Category", 170), ("Status", 115)])

        self.toolbar(installs_tab, [("Game folder", self.select_game), ("Quarantine / restore", self.quarantine),
                                   ("Undo selected install", self.undo)])
        self.install_tree = self.table(installs_tab, [("File", 430), ("Folder", 140), ("Status", 140)])
        self.feedback = tk.StringVar(value="Ready")
        self.build_settings()
        ttk.Label(frame, textvariable=self.feedback, style="Muted.TLabel", wraplength=980).pack(anchor="w", pady=(12, 0))

    def configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background=PANEL_BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=PANEL_BG)
        style.configure("TLabel", background=PANEL_BG, foreground=TEXT)
        style.configure("Heading.TLabel", font=("Segoe UI Semibold", 24))
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 13))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Mark.TLabel", foreground=ACCENT, font=("Segoe UI Symbol", 23))
        style.configure("TNotebook", background=WINDOW_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=WINDOW_BG, foreground=MUTED, padding=(17, 10))
        style.map("TNotebook.Tab", background=[("selected", PANEL_BG), ("active", INPUT_BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TButton", background=INPUT_BG, foreground=TEXT, bordercolor=SELECTED, padding=(9, 6))
        style.map("TButton", background=[("active", SELECTED)], foreground=[("disabled", MUTED)])
        style.configure("Accent.TButton", background=ACCENT, foreground=WINDOW_BG, bordercolor=ACCENT)
        style.map("Accent.TButton", background=[("active", "#a2f0cf")])
        style.configure("TCheckbutton", background=PANEL_BG, foreground=TEXT, indicatorbackground=INPUT_BG)
        style.map("TCheckbutton", background=[("active", PANEL_BG)], indicatorbackground=[("selected", ACCENT)])
        for widget in ("TEntry", "TSpinbox", "TCombobox"):
            style.configure(widget, fieldbackground=INPUT_BG, foreground=TEXT, insertcolor=TEXT,
                            background=INPUT_BG, bordercolor=SELECTED, arrowcolor=TEXT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", INPUT_BG)])
        style.configure("Treeview", rowheight=32, background=INPUT_BG, fieldbackground=INPUT_BG,
                        foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_BG, foreground=MUTED,
                        font=("Segoe UI Semibold", 10), padding=(8, 8), bordercolor=INPUT_BG)
        style.map("Treeview", background=[("selected", SELECTED)], foreground=[("selected", TEXT)])
        style.map("Treeview.Heading", background=[("active", PANEL_BG)])
        style.configure("Vertical.TScrollbar", background=INPUT_BG, troughcolor=PANEL_BG,
                        bordercolor=PANEL_BG, arrowcolor=MUTED)

    def build_settings(self):
        panel = self.settings_tab
        panel.columnconfigure(1, weight=1)
        self.game_var = tk.StringVar(value=self.state.get("game", ""))
        self.download_var = tk.StringVar(value=self.settings["downloads"])
        self.worker_var = tk.StringVar(value=str(self.settings["workers"]))
        self.organize_var = tk.BooleanVar(value=self.settings["organize"])
        self.game_var.trace_add("write", lambda *_: self.show_game_paths())
        ttk.Label(panel, text="Sims 4 folders", style="Section.TLabel").grid(row=0, columnspan=3, sticky="w", pady=(0, 10))
        ttk.Label(panel, text="Game user data").grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(panel, textvariable=self.game_var).grid(row=1, column=1, sticky="ew")
        ttk.Button(panel, text="Browse", command=lambda: self.browse_path(self.game_var)).grid(row=1, column=2, padx=(8, 0), sticky="ew")
        self.game_labels = {}
        for row, (name, child) in enumerate((("Mods", "Mods"), ("Tray", "Tray"), ("Game saves", "saves")), start=2):
            ttk.Label(panel, text=name).grid(row=row, column=0, sticky="w", pady=4)
            label = ttk.Label(panel, style="Muted.TLabel", wraplength=720)
            label.grid(row=row, column=1, sticky="w", pady=4)
            self.game_labels[child] = label
            ttk.Button(panel, text="Open", command=lambda folder=child: self.open_game_subfolder(folder)).grid(
                row=row, column=2, padx=(8, 0), sticky="ew")
        ttk.Button(panel, text="Detect Sims 4 folders", command=self.detect_settings).grid(
            row=5, column=1, sticky="w", pady=(6, 16))
        ttk.Separator(panel).grid(row=6, columnspan=3, sticky="ew")
        ttk.Label(panel, text="Downloads", style="Section.TLabel").grid(row=7, columnspan=3, sticky="w", pady=(14, 10))
        ttk.Label(panel, text="Download folder").grid(row=8, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(panel, textvariable=self.download_var).grid(row=8, column=1, sticky="ew")
        ttk.Button(panel, text="Browse", command=lambda: self.browse_path(self.download_var)).grid(row=8, column=2, padx=(8, 0), sticky="ew")
        ttk.Label(panel, text="Active downloads").grid(row=9, column=0, sticky="w", pady=8)
        ttk.Spinbox(panel, from_=1, to=10, width=5, textvariable=self.worker_var).grid(row=9, column=1, sticky="w", pady=8)
        ttk.Checkbutton(panel, text="Sort new files into category folders", variable=self.organize_var).grid(row=10, column=1, sticky="w")
        ttk.Checkbutton(panel, text="Watch clipboard for TSR links", variable=self.watch).grid(row=11, column=1, sticky="w", pady=6)
        ttk.Button(panel, text="Save settings", style="Accent.TButton", command=self.save_settings).grid(
            row=12, column=1, sticky="w", pady=(8, 0))
        self.show_game_paths()

    def show_game_paths(self):
        value = self.game_var.get().strip()
        for child, label in self.game_labels.items():
            if not value:
                label.configure(text="Folder not detected")
                continue
            path = Path(value) / child
            label.configure(text=str(path) + ("" if path.is_dir() else "  ·  Folder not found"))

    @staticmethod
    def browse_path(variable):
        current = Path(variable.get().strip())
        initial = current if current.is_dir() and current.is_absolute() else Path.home()
        path = filedialog.askdirectory(initialdir=str(initial))
        if path:
            variable.set(str(Path(path).resolve()))

    def open_game_subfolder(self, folder):
        value = self.game_var.get().strip()
        path = Path(value) / folder
        if value and path.is_dir():
            os.startfile(str(path))
        else:
            self.feedback.set(f"The {folder} folder could not be found.")

    def detect_settings(self):
        path = detect_game()
        if path:
            self.game_var.set(str(path))
            self.feedback.set("Sims 4 user data found. Save settings to use this folder.")
        else:
            self.feedback.set("Sims 4 user data was not found in Documents or OneDrive. Browse to the folder if you moved it.")

    def save_watch(self):
        self.settings["watch"] = self.watch.get()
        self.persist()

    def save_settings(self):
        game = self.game_var.get().strip()
        downloads = self.download_var.get().strip()
        try:
            workers = int(self.worker_var.get())
            if not 1 <= workers <= 10:
                raise ValueError
        except ValueError:
            messagebox.showerror("Settings", "Enter a download limit from 1 to 10.")
            return
        if game and not self.is_game_folder(Path(game)):
            messagebox.showerror("Settings", "Choose the Sims 4 user data folder containing Mods, Tray, or saves.")
            return
        if not downloads or not Path(downloads).expanduser().is_absolute():
            messagebox.showerror("Settings", "Choose a full path for the download folder.")
            return
        try:
            destination = Path(downloads).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror("Settings", str(error))
            return
        if game:
            self.state["game"] = str(Path(game).resolve())
        else:
            self.state.pop("game", None)
        self.settings.update(downloads=str(destination), workers=workers, organize=self.organize_var.get(),
                             watch=self.watch.get())
        self.persist()
        self.feedback.set("Settings saved. New transfers will use the updated download settings.")

    @staticmethod
    def is_game_folder(path):
        return path.is_absolute() and any((path / name).is_dir() for name in ("Mods", "Tray", "saves"))

    @staticmethod
    def toolbar(parent, actions):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(4, 7))
        for name, callback in actions:
            ttk.Button(bar, text=name, command=callback).pack(side="left", padx=(0, 5))
        return bar

    @staticmethod
    def table(parent, columns):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=[name for name, _ in columns], show="headings")
        for name, width in columns:
            tree.heading(name, text=name)
            tree.column(name, width=width, minwidth=65)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def persist(self):
        save_json(STATE_PATH, self.state)

    def import_legacy_queue(self):
        path = SESSION_DIR / "urls.txt"
        if self.state.get("legacyImported"):
            return
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    item = parse_url(line)
                except (ValueError, InvalidURL):
                    continue
                self.add_item(str(item.itemId), line)
        self.state["legacyImported"] = True
        self.persist()

    def add_item(self, key, url):
        return self.items.setdefault(key, {
            "name": f"TSR item {key}", "creator": "", "url": url, "status": "New",
            "requires": [], "detail": "",
        })

    @staticmethod
    def update_table(tree, rows):
        selected = set(tree.selection())
        for key in tree.get_children():
            if key not in rows:
                tree.delete(key)
        for key, values in rows.items():
            if tree.exists(key):
                if tuple(str(value) for value in tree.item(key, "values")) != tuple(values):
                    tree.item(key, values=values)
            else:
                tree.insert("", "end", iid=key, values=values)
        tree.selection_set([key for key in selected if tree.exists(key)])

    def refresh(self):
        search = self.search.get().casefold().strip()
        queue_rows, library_rows = {}, {}
        installed_keys = {batch["item"] for batch in self.batches.values() if batch["files"]}
        for key, item in self.items.items():
            if item.get("url") and item["status"] != "Complete":
                queue_rows[key] = (item["name"], item.get("creator", ""), item["status"], item.get("detail", ""))
            if item["status"] != "Complete":
                continue
            category = item.get("category", "")
            if self.profile_filter is not None and key not in self.profile_filter:
                continue
            fields = [item["name"], item.get("creator", ""), category, item.get("url", ""), item.get("path", "")]
            if search and search not in " ".join(fields).casefold():
                continue
            status = "Missing file" if not Path(item["path"]).is_file() else ("Installed" if key in installed_keys else "Available")
            library_rows[key] = (fields[0], fields[1], category, status)
        install_rows = {}
        for batch_id, batch in self.batches.items():
            for index, record in enumerate(batch["files"]):
                path = Path(record["path"])
                install_rows[f"{batch_id}:{index}"] = (path.name, path.parent.name, "Quarantined" if record["disabled"] else "Installed")
        self.update_table(self.queue_tree, queue_rows)
        self.update_table(self.library_tree, library_rows)
        self.update_table(self.install_tree, install_rows)
        self.queue_status.configure(text=f"{'Paused' if self.paused else 'Running'} · {len(self.active)} active")

    def review_links(self):
        self.review_text(self.links.get("1.0", "end"))
        self.links.delete("1.0", "end")

    def review_text(self, text):
        recognized = skipped = 0
        for token in text.split():
            try:
                url = parse_url(token)
            except (ValueError, InvalidURL):
                skipped += 1
                continue
            key = str(url.itemId)
            item = self.add_item(key, url.url)
            if item["status"] == "Complete" and not Path(item["path"]).is_file():
                item["status"] = "New"
            if item["status"] in {"New", "Lookup failed"}:
                self.lookup(key)
            recognized += 1
        self.feedback.set(f"{recognized} TSR links recognized · {skipped} skipped")
        self.persist()
        self.refresh()

    def watch_clipboard(self):
        if self.closing:
            return
        if self.watch.get():
            try:
                text = self.root.clipboard_get()
            except tk.TclError:
                text = ""
            if text != self.last_clipboard:
                self.last_clipboard = text
                if "thesimsresource.com/" in text.lower():
                    self.review_text(text)
        self.root.after(650, self.watch_clipboard)

    def schedule(self, pool, key, operation, func, *args):
        future = pool.submit(func, *args)
        future.add_done_callback(lambda completed: self.events.put((operation, key, completed)))

    def lookup(self, key):
        if key in self.inspections:
            return
        self.inspections.add(key)
        self.items[key]["status"] = "Checking"
        self.schedule(self.metadata, key, "lookup", inspect_item, self.items[key]["url"])

    def queue_selected(self):
        for key in self.queue_tree.selection():
            if self.items[key]["status"] in READY:
                self.items[key].update(status="Queued", detail="")
        self.paused = False
        self.persist()
        self.refresh()

    def retry_selected(self):
        for key in self.queue_tree.selection():
            item = self.items[key]
            if item["status"] in {"New", "VIP only", "Lookup failed"}:
                self.lookup(key)
            if item["status"] in {"Download failed", "Paused"}:
                item.update(status="Queued", detail="")
                self.paused = False
        self.persist()
        self.refresh()

    def remove_selected(self):
        for key in self.queue_tree.selection():
            if self.items[key]["status"] not in WORKING:
                del self.items[key]
        self.persist()
        self.refresh()

    def toggle_queue(self):
        self.paused = not self.paused
        self.feedback.set("Active transfers finish when the queue is paused." if self.paused else "Queue resumed.")
        self.refresh()

    def show_dependencies(self, tree=None):
        keys = (tree or self.queue_tree).selection()
        if not keys:
            return
        key = keys[0]
        item = self.items[key]
        dependencies = item.get("requires", [])
        if not dependencies:
            messagebox.showinfo("Dependencies", f"{item['name']}\n\nNo required files have been detected.")
            return
        missing = []
        lines = []
        for dep in dependencies:
            child = self.items.get(dep, {})
            available = child.get("status") == "Complete" and Path(child["path"]).is_file()
            lines.append(f"{child.get('name', 'TSR item ' + dep)} · {'Downloaded' if available else 'Missing'}")
            if not available:
                missing.append(dep)
        if missing and messagebox.askyesno("Dependencies", "\n".join(lines) + "\n\nAdd missing links for review?"):
            self.review_text("\n".join(DETAILS + dep for dep in missing))
        elif not missing:
            messagebox.showinfo("Dependencies", "\n".join(lines))

    def tick(self):
        dirty = repaint = False
        while True:
            try:
                action, key, payload = self.events.get_nowait()
            except Empty:
                break
            item = self.items[key]
            repaint = True
            if action == "progress":
                label, received, total = payload
                item["detail"] = f"{received / total:.0%} · {label}" if total else (
                    f"{received / 1048576:.1f} MiB · {label}" if received else label
                )
                continue
            dirty = True
            (self.inspections if action == "lookup" else self.active).discard(key)
            try:
                item.update(payload.result())
            except Exception as error:
                item["status"] = "Lookup failed" if action == "lookup" else "Download failed"
                if getattr(error, "response", None) is not None and error.response.status_code == 429:
                    self.paused = True
                    item["detail"] = "TSR rate limit. Wait before retrying."
                elif getattr(error, "response", None) is not None:
                    item["detail"] = f"TSR HTTP {error.response.status_code}"
                else:
                    item["detail"] = type(error).__name__ if "http" in str(error) else str(error)[:180]
                item["detail"] = item["detail"] or type(error).__name__
        if not self.paused and not self.closing:
            for key, item in self.items.items():
                if len(self.active) >= self.settings["workers"]:
                    break
                if item["status"] != "Queued":
                    continue
                self.active.add(key)
                item.update(status="Downloading", detail="Requesting ticket")
                session = SESSION_DIR / "session"
                session_id = session.read_text(encoding="utf-8").strip() if session.exists() else ""
                self.schedule(self.transfers, key, "download", fetch_item, item["url"], session_id,
                              self.settings["downloads"],
                              lambda *values, item_key=key: self.events.put(("progress", item_key, values)),
                              self.settings["organize"])
                dirty = True
        if dirty:
            self.persist()
        if dirty or repaint:
            self.refresh()
        if self.closing and not self.active and not self.inspections:
            self.root.destroy()
        else:
            self.root.after(120, self.tick)

    def add_local(self):
        paths = filedialog.askopenfilenames(title="Add Sims 4 files", filetypes=[
            ("Sims 4 files", "*.zip *.package *.ts4script *.trayitem *.blueprint *.bpi *.hhi *.sgi *.householdbinary *.room *.rmi"),
        ])
        known = {item.get("path", "").casefold() for item in self.items.values()}
        from download_organizer import getDownloadCategory
        for value in paths:
            path = Path(value).resolve()
            if str(path).casefold() in known:
                continue
            self.items[uuid4().hex] = {"name": path.name, "creator": "", "path": str(path),
                                       "category": " / ".join(getDownloadCategory(path)), "status": "Complete"}
        self.persist()
        self.refresh()

    def selected_library(self):
        selected = self.library_tree.selection()
        if len(selected) == 1:
            return selected[0], self.items[selected[0]]
        self.feedback.set("Select one file in the library.")
        return None, None

    def open_file_folder(self):
        _, item = self.selected_library()
        if item and Path(item["path"]).parent.is_dir():
            os.startfile(Path(item["path"]).parent)

    def change_category(self):
        _, item = self.selected_library()
        if item:
            value = simpledialog.askstring("Category", "Library category", initialvalue=item.get("category", ""))
            if value is not None:
                item["category"] = value.strip()
                self.persist()
                self.refresh()

    def save_profile(self):
        keys = self.library_tree.selection()
        if not keys:
            self.feedback.set("Select library files to save as a profile.")
            return
        name = simpledialog.askstring("Save profile", "Profile name")
        if name and name.strip():
            self.state["profiles"][name.strip()] = list(keys)
            self.persist()
            self.feedback.set(f"Saved profile {name.strip()} with {len(keys)} items.")

    def load_profile(self):
        profiles = self.state["profiles"]
        if not profiles:
            self.feedback.set("No saved profiles yet.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Load profile")
        dialog.transient(self.root)
        choice = tk.StringVar(value=next(iter(profiles)))
        ttk.Combobox(dialog, textvariable=choice, values=list(profiles), state="readonly").pack(padx=12, pady=12)

        def apply():
            self.profile_filter = set(profiles[choice.get()])
            self.feedback.set(f"Showing profile {choice.get()}.")
            self.refresh()
            dialog.destroy()

        ttk.Button(dialog, text="Show profile", command=apply).pack(pady=(0, 12))

    def clear_profile(self):
        self.profile_filter = None
        self.feedback.set("Showing all library items.")
        self.refresh()

    def export_links(self):
        links = [self.items[key]["url"] for key in self.library_tree.selection() if self.items[key].get("url")]
        if not links:
            self.feedback.set("Select downloaded TSR items to export their links.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Link list", "*.txt")])
        if path:
            Path(path).write_text("\n".join(links) + "\n", encoding="utf-8")

    def import_links(self):
        path = filedialog.askopenfilename(filetypes=[("Link list", "*.txt")])
        if path:
            self.review_text(Path(path).read_text(encoding="utf-8-sig"))

    def select_game(self):
        self.tabs.select(self.settings_tab)
        self.feedback.set("Set your Sims 4 user data folder in Settings.")

    def preview_install(self):
        key, item = self.selected_library()
        if not item:
            return
        game = Path(self.state.get("game", ""))
        if not self.is_game_folder(game):
            self.select_game()
            return
        try:
            plan = install_plan(item["path"], game.resolve())
        except Exception as error:
            messagebox.showerror("Install preview", str(error))
            return
        dialog = tk.Toplevel(self.root)
        dialog.geometry("720x400")
        dialog.title("Install preview")
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=str(game), padding=10).pack(anchor="w")
        table = self.table(dialog, [("File", 350), ("Folder", 100), ("Action", 190)])
        for _, target, _, conflict in plan:
            table.insert("", "end", values=(target.name, target.parent.name, "Skip · filename conflict" if conflict else "Copy"))
        count = sum(not row[3] for row in plan)

        def confirm():
            try:
                records = install(item["path"], plan)
                if records:
                    self.batches[uuid4().hex] = {"item": key, "files": records}
                    self.persist()
                self.feedback.set(f"Installed {len(records)} files · skipped {len(plan) - len(records)}.")
                self.refresh()
                dialog.destroy()
            except Exception as error:
                messagebox.showerror("Install failed", str(error), parent=dialog)

        button = ttk.Button(dialog, text=f"Install {count} files", command=confirm)
        if count == 0:
            button.state(["disabled"])
        button.pack(pady=9)

    def quarantine(self):
        selected = self.install_tree.selection()
        if not selected:
            return
        errors = []
        for key in selected:
            batch, index = key.split(":")
            record = self.batches[batch]["files"][int(index)]
            try:
                current = verify_record(record)
                path = Path(record["path"])
                target = path if record["disabled"] else path.with_name(path.name + ".disabled")
                if target.exists() or target.is_symlink():
                    raise FileExistsError(target)
                current.rename(target)
                record["disabled"] = not record["disabled"]
            except (OSError, ValueError) as error:
                errors.append(str(error))
        self.persist()
        self.refresh()
        if errors:
            messagebox.showerror("Quarantine / restore", "\n".join(errors))

    def undo(self):
        batches = {key.split(":")[0] for key in self.install_tree.selection()}
        if not batches or not messagebox.askyesno("Undo install", "Remove the selected install batches from the game folders?"):
            return
        errors = []
        for key in batches:
            batch = self.batches[key]
            for record in batch["files"][:]:
                try:
                    verify_record(record).unlink()
                    batch["files"].remove(record)
                except (OSError, ValueError) as error:
                    errors.append(str(error))
            if not batch["files"]:
                del self.batches[key]
        self.persist()
        self.refresh()
        if errors:
            messagebox.showerror("Undo install", "\n".join(errors))

    def close(self):
        if self.active or self.inspections:
            self.closing = True
            self.paused = True
            self.feedback.set("Closing after active network tasks finish.")
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with STATE_PATH.with_suffix(".lock").open("a+b") as lock:
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                messagebox.showinfo("Sims 4 Mod Library", "The library is already open.", parent=root)
                return
            app = DesktopApp(root)
            root.deiconify()
            try:
                root.mainloop()
            finally:
                app.metadata.shutdown()
                app.transfers.shutdown()
    except (OSError, ValueError) as error:
        messagebox.showerror("Sims 4 Mod Library", str(error), parent=root)
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

if __name__ == "__main__":
    main()
