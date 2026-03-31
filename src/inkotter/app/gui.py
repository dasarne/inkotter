"""First desktop-oriented GUI for InkOtter."""

from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from inkotter.core import prepare_print_job, summarize_print_job
from inkotter.devices import KATASYMBOL_E10_PROFILE
from inkotter.transport import auto_select_device, list_visible_devices, send_packets


class InkOtterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("InkOtter")
        self.root.geometry("760x520")

        self.image_path = tk.StringVar()
        self.no_scale = tk.BooleanVar(value=False)
        self.channel = tk.IntVar(value=1)
        self.scan_seconds = tk.IntVar(value=4)
        self.selected_printer = tk.StringVar(value="(not selected)")
        self.selected_mac: str = ""
        self.status_text = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(outer, text="InkOtter", font=("TkDefaultFont", 18, "bold"))
        title.pack(anchor=tk.W)
        tagline = ttk.Label(outer, text="Labels, unleashed.")
        tagline.pack(anchor=tk.W, pady=(0, 12))

        file_box = ttk.LabelFrame(outer, text="Document", padding=12)
        file_box.pack(fill=tk.X)
        ttk.Entry(file_box, textvariable=self.image_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_box, text="Choose…", command=self._choose_file).pack(side=tk.LEFT, padx=(8, 0))

        options_box = ttk.LabelFrame(outer, text="Options", padding=12)
        options_box.pack(fill=tk.X, pady=(12, 0))
        ttk.Checkbutton(
            options_box,
            text="Use actual document size (no scale)",
            variable=self.no_scale,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(options_box, text="RFCOMM channel").grid(row=0, column=1, sticky="e", padx=(24, 6))
        ttk.Spinbox(options_box, from_=1, to=30, textvariable=self.channel, width=5).grid(row=0, column=2, sticky="w")
        ttk.Label(options_box, text="Scan seconds").grid(row=0, column=3, sticky="e", padx=(24, 6))
        ttk.Spinbox(options_box, from_=0, to=20, textvariable=self.scan_seconds, width=5).grid(row=0, column=4, sticky="w")

        printer_box = ttk.LabelFrame(outer, text="Printer", padding=12)
        printer_box.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(printer_box, textvariable=self.selected_printer).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(printer_box, text="Search", command=self._search_printers).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(printer_box, text="Auto-select", command=self._auto_select_printer).pack(side=tk.LEFT, padx=(8, 0))

        action_box = ttk.Frame(outer)
        action_box.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(action_box, text="Dry Run", command=self._dry_run).pack(side=tk.LEFT)
        ttk.Button(action_box, text="Print", command=self._print).pack(side=tk.LEFT, padx=(8, 0))

        summary_box = ttk.LabelFrame(outer, text="Summary", padding=12)
        summary_box.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.summary = tk.Text(summary_box, height=14, wrap="word")
        self.summary.pack(fill=tk.BOTH, expand=True)
        self.summary.configure(state="disabled")

        status = ttk.Label(outer, textvariable=self.status_text)
        status.pack(anchor=tk.W, pady=(10, 0))

    def _append_summary(self, text: str) -> None:
        self.summary.configure(state="normal")
        self.summary.delete("1.0", tk.END)
        self.summary.insert(tk.END, text)
        self.summary.configure(state="disabled")

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select document",
            filetypes=[
                ("Supported documents", "*.svg *.png *.jpg *.jpeg"),
                ("SVG", "*.svg"),
                ("Raster images", "*.png *.jpg *.jpeg"),
                ("All files", "*"),
            ],
        )
        if path:
            self.image_path.set(path)
            self.status_text.set("Document selected.")

    def _search_printers(self) -> None:
        def worker() -> None:
            try:
                devices = list_visible_devices(scan_seconds=self.scan_seconds.get())
                if not devices:
                    self.root.after(0, lambda: self._show_info("No printers", "No Bluetooth devices found."))
                    return
                lines = [f"{device.mac}  {device.name}" for device in devices]
                self.root.after(0, lambda: self._append_summary("Visible Bluetooth devices:\n\n" + "\n".join(lines)))
                self.root.after(0, lambda: self.status_text.set("Bluetooth scan finished."))
            except RuntimeError as exc:
                self.root.after(0, lambda: self._show_error("Bluetooth discovery failed", str(exc)))

        self.status_text.set("Scanning for Bluetooth devices…")
        threading.Thread(target=worker, daemon=True).start()

    def _auto_select_printer(self) -> None:
        def worker() -> None:
            try:
                selected = auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=self.scan_seconds.get())
                def apply_selection() -> None:
                    self.selected_mac = selected.mac
                    self.selected_printer.set(f"{selected.name} ({selected.mac})")
                    self.status_text.set("Printer selected.")
                self.root.after(0, apply_selection)
            except RuntimeError as exc:
                self.root.after(0, lambda: self._show_error("Printer auto-discovery failed", str(exc)))

        self.status_text.set("Selecting printer…")
        threading.Thread(target=worker, daemon=True).start()

    def _render_summary_text(self, summary) -> str:
        return (
            f"Device: {summary.device_name}\n"
            f"Document: {summary.document_path}\n"
            f"Layout: {summary.layout_mode}\n"
            f"Canvas: {summary.canvas_width_px}x{summary.canvas_height_px}\n"
            f"Pages: {summary.page_count}\n"
            f"Frames: {summary.frame_count}\n"
            f"Chunks per page: {list(summary.chunks_per_page)}\n"
        )

    def _require_image(self) -> Path | None:
        raw = self.image_path.get().strip()
        if not raw:
            self._show_error("Missing document", "Choose an SVG, PNG, or JPG first.")
            return None
        return Path(raw)

    def _dry_run(self) -> None:
        image = self._require_image()
        if image is None:
            return

        def worker() -> None:
            try:
                job = prepare_print_job(image, KATASYMBOL_E10_PROFILE, no_scale=self.no_scale.get())
                summary = summarize_print_job(job)
                self.root.after(0, lambda: self._append_summary(self._render_summary_text(summary)))
                self.root.after(0, lambda: self.status_text.set("Dry run ready."))
            except Exception as exc:  # pragma: no cover - UI surface
                self.root.after(0, lambda: self._show_error("Dry run failed", str(exc)))

        self.status_text.set("Preparing dry run…")
        threading.Thread(target=worker, daemon=True).start()

    def _print(self) -> None:
        image = self._require_image()
        if image is None:
            return

        def worker() -> None:
            try:
                job = prepare_print_job(image, KATASYMBOL_E10_PROFILE, no_scale=self.no_scale.get())
                summary = summarize_print_job(job)
                target_mac = self.selected_mac
                printer_label = self.selected_printer.get()
                if not target_mac:
                    selected = auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=self.scan_seconds.get())
                    target_mac = selected.mac
                    printer_label = f"{selected.name} ({selected.mac})"
                send_packets(
                    mac=target_mac,
                    channel=self.channel.get(),
                    packets=job.frames,
                )
                def done() -> None:
                    self.selected_mac = target_mac
                    self.selected_printer.set(printer_label)
                    self._append_summary(self._render_summary_text(summary) + f"\nPrinted via: {printer_label}\n")
                    self.status_text.set("Print sent.")
                self.root.after(0, done)
            except PermissionError:
                self.root.after(
                    0,
                    lambda: self._show_error(
                        "Bluetooth permission denied",
                        "RFCOMM open/connect was denied. Retry as a user with Bluetooth access or with sudo.",
                    ),
                )
            except Exception as exc:  # pragma: no cover - UI surface
                self.root.after(0, lambda: self._show_error("Print failed", str(exc)))

        self.status_text.set("Sending print job…")
        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, title: str, message: str) -> None:
        self.status_text.set(message)
        messagebox.showerror(title, message)

    def _show_info(self, title: str, message: str) -> None:
        self.status_text.set(message)
        messagebox.showinfo(title, message)


def main() -> None:
    root = tk.Tk()
    app = InkOtterApp(root)
    app.status_text.set("Ready.")
    root.mainloop()


if __name__ == "__main__":
    main()
