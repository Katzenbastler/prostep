from __future__ import annotations

import ctypes
import queue
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Optional

from .config import QualityMode, ReconstructionConfig
from .version import __version__


class ReconstructionApp:
    UI_VERSION = "v3 beta"

    def __init__(self) -> None:
        self._set_windows_app_id()

        self.root = tk.Tk()
        self.root.title("prostep")
        self.root.geometry("980x720")
        self.root.minsize(860, 620)
        self.root.configure(bg="#242424")

        self.source_path: Optional[Path] = None
        self.output_path: Optional[Path] = None
        self.busy = False
        self.events: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._icon_photo: Optional[tk.PhotoImage] = None

        self.lang_var = tk.StringVar(value="English")
        self.path_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value="")
        self.tol_text = tk.StringVar(value="")

        self._set_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._apply_language()
        self.root.after(100, self._poll_events)

    @staticmethod
    def _resource_path(rel_path: str) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        return base / rel_path

    @staticmethod
    def _set_windows_app_id() -> None:
        if sys.platform != "win32":
            return
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Katzenbastler.prostep.v3beta")
        except Exception:
            pass

    def _set_window_icon(self) -> None:
        try:
            ico = self._resource_path("assets/icons/proSTEP.ico")
            png = self._resource_path("assets/icons/prostep_brand.png")

            if png.exists():
                self._icon_photo = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._icon_photo)
            if ico.exists():
                self.root.iconbitmap(default=str(ico))
        except Exception:
            pass

    def _is_de(self) -> bool:
        return self.lang_var.get().strip().lower().startswith("de")

    def _t(self, key: str) -> str:
        en = {
            "subtitle": "STL to STEP (AP242) | v3 beta",
            "updates": "Updates later",
            "lang": "Language",
            "file_none": "STL: <no file>",
            "file_pick": "Choose STL",
            "quality": "Quality mode",
            "smooth": "Feature-aware smoothing",
            "analytic": "Prefer analytical surfaces (experimental and broken, can cause errors)",
            "tol": "Export tolerance [mm]: {value:.3f}",
            "start": "Start conversion",
            "save": "Save file",
            "ready": "Ready.",
            "out_none": "Output: <none>",
            "version": "Version: {version}",
            "credit": "made by Katzenbastler",
            "signature": "Digital Program Creator: Katzenbastler industries",
            "status_missing_file": "Please choose an STL first.",
            "status_file_not_found": "File not found.",
            "status_file_selected": "File selected. Ready for conversion.",
            "status_start": "Starting conversion...",
            "status_no_output": "No STEP file available yet.",
            "status_saved": "Saved: {name}",
            "status_save_failed": "Could not save file: {error}",
            "status_done": "Done in {sec:.2f}s | STEP: {name} | watertight={watertight}",
            "status_error": "Error: {error}",
            "dialog_open": "Choose STL",
            "dialog_save": "Save STEP file",
            "ft_stl": "STL Mesh",
            "ft_step": "STEP",
            "ft_all": "All files",
        }
        de = {
            "subtitle": "STL zu STEP (AP242) | v3 beta",
            "updates": "Updates später",
            "lang": "Sprache",
            "file_none": "STL: <keine Datei>",
            "file_pick": "STL auswählen",
            "quality": "Qualitätsmodus",
            "smooth": "Feature-aware smoothing",
            "analytic": "Analytische Flächen bevorzugen (experimental and broken, kann Fehler verursachen)",
            "tol": "Export-Toleranz [mm]: {value:.3f}",
            "start": "Umwandlung starten",
            "save": "Datei sichern",
            "ready": "Bereit.",
            "out_none": "Output: <noch keiner>",
            "version": "Version: {version}",
            "credit": "made by Katzenbastler",
            "signature": "Digital Program Creator: Katzenbastler industries",
            "status_missing_file": "Bitte zuerst eine STL auswählen.",
            "status_file_not_found": "Datei nicht gefunden.",
            "status_file_selected": "Datei ausgewählt. Bereit zur Umwandlung.",
            "status_start": "Umwandlung startet...",
            "status_no_output": "Noch keine STEP-Datei vorhanden.",
            "status_saved": "Gespeichert: {name}",
            "status_save_failed": "Konnte Datei nicht speichern: {error}",
            "status_done": "Fertig in {sec:.2f}s | STEP: {name} | watertight={watertight}",
            "status_error": "Fehler: {error}",
            "dialog_open": "STL auswählen",
            "dialog_save": "STEP-Datei speichern",
            "ft_stl": "STL Mesh",
            "ft_step": "STEP",
            "ft_all": "Alle Dateien",
        }
        return (de if self._is_de() else en)[key]

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        bg = "#242424"
        panel = "#2f2f2f"
        card = "#353535"
        border = "#414141"
        text = "#f2f2f2"
        muted = "#c9c9c9"
        accent = "#f0f0f0"
        accent_hover = "#ffffff"
        accent_press = "#dddddd"
        sec_bg = "#3f3f3f"
        sec_hover = "#4b4b4b"
        sec_press = "#373737"

        self.root.option_add("*TCombobox*Listbox*Background", "#303030")
        self.root.option_add("*TCombobox*Listbox*Foreground", text)
        self.root.option_add("*TCombobox*Listbox*selectBackground", "#4a4a4a")
        self.root.option_add("*TCombobox*Listbox*selectForeground", text)

        style.configure("App.TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("Card.TFrame", background=card, relief="flat", borderwidth=1)
        style.configure("Title.TLabel", background=panel, foreground=text, font=("Segoe UI Semibold", 20))
        style.configure("Sub.TLabel", background=panel, foreground=muted, font=("Segoe UI", 10))
        style.configure("CardHead.TLabel", background=card, foreground=text, font=("Segoe UI Semibold", 11))
        style.configure("Text.TLabel", background=card, foreground=text, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=card, foreground=muted, font=("Segoe UI", 9))
        style.configure("Footer.TLabel", background=panel, foreground=muted, font=("Segoe UI", 9))

        style.configure("TCheckbutton", background=card, foreground=text, font=("Segoe UI", 10), padding=(2, 2))
        style.map("TCheckbutton", background=[("active", card)], foreground=[("active", text)])

        style.configure("TCombobox", fieldbackground="#3a3a3a", background="#3a3a3a", foreground=text, padding=7)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#3a3a3a")],
            foreground=[("readonly", text)],
            selectbackground=[("readonly", "#3a3a3a")],
            selectforeground=[("readonly", text)],
        )

        style.configure("App.Horizontal.TProgressbar", troughcolor="#2a2a2a", background="#d8d8d8", bordercolor="#2a2a2a")

        style.configure("Primary.TButton", background=accent, foreground="#161616", borderwidth=0, padding=(16, 9))
        style.map(
            "Primary.TButton",
            background=[("pressed", accent_press), ("active", accent_hover)],
            foreground=[("pressed", "#000000"), ("active", "#000000")],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )

        style.configure("Secondary.TButton", background=sec_bg, foreground=text, borderwidth=0, padding=(16, 9))
        style.map(
            "Secondary.TButton",
            background=[("pressed", sec_press), ("active", sec_hover)],
            foreground=[("pressed", "#ffffff"), ("active", "#ffffff")],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )

        root_frame = ttk.Frame(self.root, style="App.TFrame", padding=16)
        root_frame.pack(fill="both", expand=True)

        panel_frame = ttk.Frame(root_frame, style="Panel.TFrame", padding=18)
        panel_frame.pack(fill="both", expand=True)

        top_row = ttk.Frame(panel_frame, style="Panel.TFrame")
        top_row.pack(fill="x")

        left_header = ttk.Frame(top_row, style="Panel.TFrame")
        left_header.pack(side="left", fill="x", expand=True)

        ttk.Label(left_header, text="prostep", style="Title.TLabel").pack(anchor="w")
        self.subtitle_label = ttk.Label(left_header, text="", style="Sub.TLabel")
        self.subtitle_label.pack(anchor="w", pady=(2, 0))
        self.updates_label = ttk.Label(left_header, text="", style="Sub.TLabel")
        self.updates_label.pack(anchor="w", pady=(2, 0))

        right_header = ttk.Frame(top_row, style="Panel.TFrame")
        right_header.pack(side="right", anchor="ne")

        self.lang_label = ttk.Label(right_header, text="", style="Sub.TLabel")
        self.lang_label.pack(anchor="e", pady=(4, 4))

        self.lang_combo = ttk.Combobox(
            right_header,
            textvariable=self.lang_var,
            values=["English", "Deutsch"],
            state="readonly",
            width=12,
        )
        self.lang_combo.pack(anchor="e")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_changed)

        content = ttk.Frame(panel_frame, style="Panel.TFrame")
        content.pack(fill="both", expand=True, pady=(14, 10))

        file_card = tk.Frame(content, bg=card, highlightbackground=border, highlightthickness=1, bd=0)
        file_card.pack(fill="x", pady=(0, 10))
        file_inner = ttk.Frame(file_card, style="Card.TFrame", padding=12)
        file_inner.pack(fill="both", expand=True)

        self.file_head = ttk.Label(file_inner, text="", style="CardHead.TLabel")
        self.file_head.pack(anchor="w")
        self.path_label = ttk.Label(file_inner, textvariable=self.path_var, style="Text.TLabel")
        self.path_label.pack(anchor="w", pady=(6, 10))
        self.pick_btn = ttk.Button(file_inner, text="", command=self._choose_file, style="Secondary.TButton")
        self.pick_btn.pack(anchor="w")

        settings_card = tk.Frame(content, bg=card, highlightbackground=border, highlightthickness=1, bd=0)
        settings_card.pack(fill="x", pady=(0, 10))
        settings_inner = ttk.Frame(settings_card, style="Card.TFrame", padding=12)
        settings_inner.pack(fill="both", expand=True)

        self.quality_label = ttk.Label(settings_inner, text="", style="CardHead.TLabel")
        self.quality_label.pack(anchor="w")
        self.quality_var = tk.StringVar(value="Medium")
        self.quality_combo = ttk.Combobox(
            settings_inner,
            textvariable=self.quality_var,
            values=["Low", "Medium", "High", "Ultra"],
            state="readonly",
            width=16,
        )
        self.quality_combo.pack(anchor="w", pady=(6, 10))

        self.smoothing_var = tk.BooleanVar(value=True)
        self.smoothing_check = ttk.Checkbutton(settings_inner, text="", variable=self.smoothing_var)
        self.smoothing_check.pack(anchor="w", pady=(0, 6))

        self.prefer_analytic_var = tk.BooleanVar(value=True)
        self.analytic_check = ttk.Checkbutton(settings_inner, text="", variable=self.prefer_analytic_var)
        self.analytic_check.pack(anchor="w", pady=(0, 10))

        self.tol_var = tk.DoubleVar(value=0.010)
        self.tol_label = ttk.Label(settings_inner, textvariable=self.tol_text, style="Text.TLabel")
        self.tol_label.pack(anchor="w")
        self.tol_scale = tk.Scale(
            settings_inner,
            from_=0.001,
            to=0.2,
            orient="horizontal",
            resolution=0.001,
            variable=self.tol_var,
            command=self._on_tol_changed,
            bg=card,
            fg=text,
            troughcolor="#2a2a2a",
            activebackground="#f5f5f5",
            highlightthickness=0,
            bd=0,
        )
        self.tol_scale.pack(fill="x", pady=(4, 0))

        run_card = tk.Frame(content, bg=card, highlightbackground=border, highlightthickness=1, bd=0)
        run_card.pack(fill="x")
        run_inner = ttk.Frame(run_card, style="Card.TFrame", padding=12)
        run_inner.pack(fill="both", expand=True)

        button_row = ttk.Frame(run_inner, style="Card.TFrame")
        button_row.pack(fill="x", pady=(0, 12))

        self.start_btn = ttk.Button(button_row, text="", command=self._run_reconstruction, style="Primary.TButton")
        self.start_btn.pack(side="left")

        self.save_btn = ttk.Button(button_row, text="", command=self._save_output_file, style="Secondary.TButton")
        self.save_btn.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(run_inner, style="App.Horizontal.TProgressbar", mode="determinate", maximum=100, value=0)
        self.progress.pack(fill="x", pady=(0, 10))

        self.status_label = ttk.Label(run_inner, textvariable=self.status_var, style="Text.TLabel")
        self.status_label.pack(anchor="w")

        self.output_label = ttk.Label(run_inner, textvariable=self.output_var, style="Muted.TLabel")
        self.output_label.pack(anchor="w", pady=(5, 0))

        self.version_label = ttk.Label(run_inner, text="", style="Muted.TLabel")
        self.version_label.pack(anchor="w", pady=(9, 0))

        footer = ttk.Frame(panel_frame, style="Panel.TFrame")
        footer.pack(fill="x", side="bottom", pady=(6, 0))

        self.credit_label = ttk.Label(footer, text="", style="Footer.TLabel")
        self.credit_label.pack(side="left")

        self.signature_label = ttk.Label(footer, text="", style="Footer.TLabel")
        self.signature_label.pack(side="right")

    def _apply_language(self) -> None:
        self.subtitle_label.configure(text=self._t("subtitle"))
        self.updates_label.configure(text=self._t("updates"))
        self.lang_label.configure(text=self._t("lang"))
        self.file_head.configure(text=self._t("file_pick"))
        self.pick_btn.configure(text=self._t("file_pick"))
        self.quality_label.configure(text=self._t("quality"))
        self.smoothing_check.configure(text=self._t("smooth"))
        self.analytic_check.configure(text=self._t("analytic"))
        self.start_btn.configure(text=self._t("start"))
        self.save_btn.configure(text=self._t("save"))
        self.version_label.configure(text=self._t("version").format(version=self.UI_VERSION))
        self.credit_label.configure(text=self._t("credit"))
        self.signature_label.configure(text=self._t("signature"))

        self._on_tol_changed(str(self.tol_var.get()))

        if self.source_path is None:
            self.path_var.set(self._t("file_none"))
        else:
            self.path_var.set(f"STL: {self.source_path.name}")

        if self.output_path is None:
            self.output_var.set(self._t("out_none"))
        else:
            self.output_var.set(f"Output: {self.output_path.name}")

        if not self.status_var.get().strip():
            self.status_var.set(self._t("ready"))

    def _on_language_changed(self, _event: object | None = None) -> None:
        self._apply_language()

    def _on_tol_changed(self, _value: str) -> None:
        self.tol_text.set(self._t("tol").format(value=self.tol_var.get()))

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("dialog_open"),
            filetypes=[(self._t("ft_stl"), "*.stl"), (self._t("ft_all"), "*.*")],
        )
        if not path:
            return
        selected = Path(path)
        if not selected.exists():
            self._set_status(self._t("status_file_not_found"))
            return
        self.source_path = selected
        self.output_path = None
        self.path_var.set(f"STL: {selected.name}")
        self.output_var.set(self._t("out_none"))
        self._set_status(self._t("status_file_selected"))

    def _get_mode(self) -> QualityMode:
        text = self.quality_var.get().lower().strip()
        if text == "low":
            return QualityMode.LOW
        if text == "medium":
            return QualityMode.MEDIUM
        if text == "high":
            return QualityMode.HIGH
        return QualityMode.ULTRA

    def _run_reconstruction(self) -> None:
        if self.busy:
            return
        if self.source_path is None:
            self._set_status(self._t("status_missing_file"))
            return

        self.busy = True
        self.progress["value"] = 0
        self._set_status(self._t("status_start"))

        cfg = ReconstructionConfig(
            quality_mode=self._get_mode(),
            enable_smoothing=self.smoothing_var.get(),
            prefer_analytic_surfaces=self.prefer_analytic_var.get(),
            export_tolerance_mm=float(self.tol_var.get()),
            verbose=False,
        )
        output = self.source_path.with_name(f"{self.source_path.stem}_{cfg.quality_mode.value}.step")

        def worker() -> None:
            try:
                from .pipeline import ReconstructionPipeline

                pipeline = ReconstructionPipeline(config=cfg, progress=self._thread_progress_cb)
                result = pipeline.run(self.source_path, output_step=output)
                self.events.put(("done", result))
            except Exception as exc:  # pragma: no cover
                self.events.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _thread_progress_cb(self, p: float, msg: str) -> None:
        self.events.put(("progress", (float(p), msg)))

    def _save_output_file(self) -> None:
        if self.output_path is None or not self.output_path.exists():
            self._set_status(self._t("status_no_output"))
            return
        target = filedialog.asksaveasfilename(
            title=self._t("dialog_save"),
            defaultextension=".step",
            initialfile=self.output_path.name,
            filetypes=[(self._t("ft_step"), "*.step *.stp"), (self._t("ft_all"), "*.*")],
        )
        if not target:
            return
        try:
            target_path = Path(target).resolve()
            source_path = self.output_path.resolve()
            if source_path == target_path:
                self._set_status(self._t("status_saved").format(name=target_path.name))
                return
            shutil.copy2(source_path, target_path)
            self._set_status(self._t("status_saved").format(name=target_path.name))
        except Exception as exc:
            self._set_status(self._t("status_save_failed").format(error=exc))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    p, msg = payload  # type: ignore[misc]
                    p = max(0.0, min(1.0, float(p)))
                    self.progress["value"] = p * 100.0
                    self._set_status(str(msg))
                elif kind == "done":
                    result = payload
                    self.busy = False
                    self.progress["value"] = 100.0
                    self.output_path = result.output_step
                    self.output_var.set(f"Output: {result.output_step.name}")
                    self._set_status(
                        self._t("status_done").format(
                            sec=result.elapsed_sec,
                            name=result.output_step.name,
                            watertight=result.brep.watertight,
                        )
                    )
                elif kind == "error":
                    self.busy = False
                    self.progress["value"] = 0.0
                    self._set_status(self._t("status_error").format(error=payload))
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_events)

    def _on_close(self) -> None:
        self.busy = False
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def run_gui() -> None:
    ReconstructionApp().run()
