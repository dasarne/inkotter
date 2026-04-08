"""Qt-based desktop GUI for InkOtter."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
import json
from pathlib import Path
import platform
import sys

try:
    from PySide6.QtCore import QFileSystemWatcher, QLocale, QObject, QPoint, QSize, Qt, QThread, QTimer, Signal, qVersion
    from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QImage, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QSpinBox,
        QStatusBar,
        QTabWidget,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - import surface
    if exc.name == "PySide6":
        raise SystemExit(
            "PySide6 is not installed in this Python environment. "
            "Activate the project venv and run: pip install -e . "
            "or install the GUI dependency directly with: pip install PySide6"
        ) from exc
    raise

from inkotter.core import (
    DEFAULT_MONOCHROME_THRESHOLD,
    MonochromeStrategy,
    build_preview_images,
    encode_preview_png,
    prepare_print_job,
    summarize_print_job,
)
from inkotter.devices import KATASYMBOL_E10_PROFILE
from inkotter.devices.base import first_matching_name
from inkotter.transport import auto_select_device, list_visible_devices, send_packets


APP_NAME = "InkOtter"
DEFAULT_PREVIEW_ZOOM_PERCENT = 100
MAX_RECENT_DOCUMENTS = 8
RECENT_DOCUMENTS_PATH = Path.home() / ".config" / "inkotter" / "gui_recent_documents.json"
GUI_SETTINGS_PATH = Path.home() / ".config" / "inkotter" / "gui_settings.json"
ABOUT_LOGO_PATH = Path(__file__).resolve().parents[3] / "assets" / "icons" / "Inkotter-Claim.svg"
PLACEHOLDER_LOGO_PATH = Path(__file__).resolve().parents[3] / "assets" / "icons" / "inkotter_gray.svg"
I18N_DIR = Path(__file__).resolve().parent / "i18n"
SUPPORTED_LANGUAGES = ("en", "de")
LANGUAGE_LABELS = {"en": "English", "de": "Deutsch"}


@dataclass(frozen=True)
class PreviewPayload:
    summary_text: str
    preview_info_text: str
    graphic_png: bytes
    physical_print_png: bytes


def _load_language_catalog(language_code: str) -> dict[str, str]:
    catalog_path = I18N_DIR / f"{language_code}.json"
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def _resolve_initial_language(settings: dict[str, str]) -> str:
    configured = settings.get("language", "")
    if configured in SUPPORTED_LANGUAGES:
        return configured
    system_language = QLocale.system().name().split("_", 1)[0].lower()
    if system_language in SUPPORTED_LANGUAGES:
        return system_language
    return "en"


class PreviewLabel(QLabel):
    def __init__(self, empty_text: str, parent: QWidget | None = None) -> None:
        super().__init__(empty_text, parent)
        self._base_pixmap = QPixmap()
        self._placeholder_pixmap = QPixmap()
        self._zoom_percent = DEFAULT_PREVIEW_ZOOM_PERCENT
        self._viewport_size = QSize(640, 360)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setMinimumSize(320, 180)
        self.setWordWrap(True)
        self.setStyleSheet(
            "QLabel { background: #f0f0f0; border: 1px solid palette(mid); padding: 12px; }"
        )

    def show_pixmap(self, pixmap: QPixmap) -> None:
        self._base_pixmap = pixmap
        self._placeholder_pixmap = QPixmap()
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_zoom()

    def show_placeholder(self, text: str, pixmap: QPixmap | None = None) -> None:
        self._base_pixmap = QPixmap()
        self._placeholder_pixmap = QPixmap() if pixmap is None else pixmap
        if self._placeholder_pixmap.isNull():
            self.setPixmap(QPixmap())
            self.setText(text)
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.resize(max(320, self._viewport_size.width()), max(180, self._viewport_size.height()))
            return
        self.setText("")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_zoom()

    def set_zoom_percent(self, zoom_percent: int) -> None:
        self._zoom_percent = zoom_percent
        self._apply_zoom()

    def set_viewport_size(self, size: QSize) -> None:
        self._viewport_size = size
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        available_width = max(1, self._viewport_size.width() - 24)
        available_height = max(1, self._viewport_size.height() - 24)
        if self._base_pixmap.isNull():
            if self._placeholder_pixmap.isNull():
                return
            fit_scale = min(
                available_width / self._placeholder_pixmap.width(),
                available_height / self._placeholder_pixmap.height(),
            )
            scale = max(0.01, fit_scale)
            scaled = self._placeholder_pixmap.scaled(
                max(1, round(self._placeholder_pixmap.width() * scale)),
                max(1, round(self._placeholder_pixmap.height() * scale)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.resize(max(320, self._viewport_size.width()), max(180, self._viewport_size.height()))
            return
        fit_scale = min(
            available_width / self._base_pixmap.width(),
            available_height / self._base_pixmap.height(),
        )
        scale = max(0.01, fit_scale * (self._zoom_percent / 100.0))
        scaled = self._base_pixmap.scaled(
            max(1, round(self._base_pixmap.width() * scale)),
            max(1, round(self._base_pixmap.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.setPixmap(scaled)
        self.resize(max(scaled.width() + 24, self._viewport_size.width()), max(scaled.height() + 24, self._viewport_size.height()))


class PannableScrollArea(QScrollArea):
    scrolled = Signal(int, int)
    zoom_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_active = False
        self._last_pos = QPoint()
        self._preview_label: PreviewLabel | None = None
        self._suppress_scroll_signal = False
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.horizontalScrollBar().valueChanged.connect(self._emit_scroll_position)
        self.verticalScrollBar().valueChanged.connect(self._emit_scroll_position)

    def set_preview_widget(self, preview_label: PreviewLabel) -> None:
        self._preview_label = preview_label
        self.setWidget(preview_label)
        preview_label.set_viewport_size(self.viewport().size())

    def resizeEvent(self, event) -> None:  # pragma: no cover - GUI resize behavior
        super().resizeEvent(event)
        if self._preview_label is not None:
            self._preview_label.set_viewport_size(self.viewport().size())

    def set_scroll_position(self, x: int, y: int) -> None:
        self._suppress_scroll_signal = True
        try:
            self.horizontalScrollBar().setValue(x)
            self.verticalScrollBar().setValue(y)
        finally:
            self._suppress_scroll_signal = False

    def _emit_scroll_position(self) -> None:
        if self._suppress_scroll_signal:
            return
        self.scrolled.emit(self.horizontalScrollBar().value(), self.verticalScrollBar().value())

    def mousePressEvent(self, event) -> None:  # pragma: no cover - GUI interaction
        if event.button() == Qt.MouseButton.LeftButton and self.widget() is not None:
            self._drag_active = True
            self._last_pos = event.position().toPoint()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - GUI interaction
        if self._drag_active:
            delta = event.position().toPoint() - self._last_pos
            self._last_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - GUI interaction
        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:  # pragma: no cover - GUI interaction
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta_y = event.angleDelta().y()
            if delta_y != 0:
                self.zoom_requested.emit(delta_y)
                event.accept()
                return
        super().wheelEvent(event)


class DeviceSelectionDialog(QDialog):
    """Simple picker for visible Bluetooth devices."""

    def __init__(self, devices, translate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translate
        self.setWindowTitle(self._t("dialog.device.title", default="Visible Bluetooth Devices"))
        self.resize(560, 360)
        self._devices = list(devices)
        self.selected_mac = ""
        self.selected_label = ""

        layout = QVBoxLayout(self)
        intro = QLabel(self._t("printer.dialog_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        for device in self._devices:
            label = f"{device.name} ({device.mac})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, device)
            if first_matching_name(KATASYMBOL_E10_PROFILE, device.name):
                item.setText(f"{label}  {self._t('printer.candidate_suffix')}")
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._accept_current_item)
        layout.addWidget(self.list_widget, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_button = QPushButton(self._t("action.cancel"))
        cancel_button.clicked.connect(self.reject)
        choose_button = QPushButton(self._t("action.choose_printer"))
        choose_button.clicked.connect(self._accept_current_item)
        choose_button.setDefault(True)
        button_row.addWidget(cancel_button)
        button_row.addWidget(choose_button)
        layout.addLayout(button_row)

    def _accept_current_item(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.information(
                self,
                self._t("dialog.info.no_selection_title"),
                self._t("dialog.info.no_selection_message"),
            )
            return
        device = item.data(Qt.ItemDataRole.UserRole)
        self.selected_mac = device.mac
        self.selected_label = f"{device.name} ({device.mac})"
        self.accept()


class TaskWorker(QObject):
    """Run blocking Bluetooth and rendering tasks off the UI thread."""

    finished = Signal(int, object)
    failed = Signal(int, str, str)

    def __init__(self, task_id: int, fn, *, error_title: str) -> None:
        super().__init__()
        self._task_id = task_id
        self._fn = fn
        self._error_title = error_title

    def run(self) -> None:
        try:
            result = self._fn()
        except PermissionError:
            self.failed.emit(
                self._task_id,
                "Bluetooth permission denied",
                "RFCOMM open/connect was denied. Retry as a user with Bluetooth access or with sudo.",
            )
        except Exception as exc:  # pragma: no cover - GUI surface
            self.failed.emit(self._task_id, self._error_title, str(exc))
        else:
            self.finished.emit(self._task_id, result)


class SettingsDialog(QDialog):
    def __init__(
        self,
        *,
        translate,
        language_code: str,
        current_printer_label: str,
        channel: int,
        scan_seconds: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translate
        self.setWindowTitle(self._t("menu.settings", default="Settings"))
        self.resize(420, 200)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.printer_label = QLabel(current_printer_label)
        self.printer_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self._t("menu.printer"), self.printer_label)

        printer_actions = QHBoxLayout()
        self.search_button = QPushButton(self._t("action.search"))
        self.auto_select_button = QPushButton(self._t("action.auto_select"))
        printer_actions.addWidget(self.search_button)
        printer_actions.addWidget(self.auto_select_button)
        printer_actions.addStretch(1)
        form.addRow("", printer_actions)

        self.language_combo = QComboBox()
        self.language_combo.addItem(LANGUAGE_LABELS["en"], "en")
        self.language_combo.addItem(LANGUAGE_LABELS["de"], "de")
        index = max(0, self.language_combo.findData(language_code))
        self.language_combo.setCurrentIndex(index)
        form.addRow(self._t("menu.language"), self.language_combo)

        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 30)
        self.channel_spin.setValue(channel)
        form.addRow(self._t("label.transport_channel"), self.channel_spin)

        self.scan_seconds_spin = QSpinBox()
        self.scan_seconds_spin.setRange(0, 20)
        self.scan_seconds_spin.setValue(scan_seconds)
        form.addRow(self._t("label.scan_seconds"), self.scan_seconds_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_printer_label(self, label: str) -> None:
        self.printer_label.setText(label)


class AboutInkOtterDialog(QDialog):
    def __init__(self, translate, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translate
        self.setWindowTitle(self._t("about.dialog_title"))
        self.resize(760, 560)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_about_tab(), self._t("about.about"))
        tabs.addTab(self._build_credits_tab(), self._t("about.credits"))
        tabs.addTab(self._build_license_tab(), self._t("about.license"))
        tabs.addTab(self._build_libraries_tab(), self._t("about.libraries"))
        tabs.addTab(self._build_privacy_tab(), self._t("about.privacy"))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_about_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        hero = QFrame()
        hero.setStyleSheet(
            "QFrame {"
            " background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f8f8f8, stop:1 #ececec);"
            " border: 1px solid palette(mid);"
            " border-radius: 16px;"
            " padding: 16px;"
            "}"
        )
        hero_layout = QVBoxLayout(hero)
        hero_logo = QLabel()
        pixmap = QPixmap(str(ABOUT_LOGO_PATH))
        if not pixmap.isNull():
            hero_logo.setPixmap(pixmap.scaledToHeight(128, Qt.TransformationMode.SmoothTransformation))
            hero_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(hero_logo)
        layout.addWidget(hero)

        credits_link = QLabel(f'<a href="https://github.com/dasarne/inkotter">{self._t("about.credits.link")}</a>')
        credits_link.setOpenExternalLinks(True)
        credits_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(credits_link)

        form = QFormLayout()
        for label, value in self._about_rows():
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, value_label)
        layout.addLayout(form)

        copy_button = QPushButton(self._t("about.copy"))
        copy_button.clicked.connect(self._copy_about_to_clipboard)
        layout.addWidget(copy_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return tab

    def _build_credits_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setPlainText(self._t("about.credits.body"))
        return self._wrap_browser(browser)

    def _build_license_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setPlainText(self._t("about.license.body"))
        return self._wrap_browser(browser)

    def _build_libraries_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setPlainText(self._t("about.libraries.body"))
        return self._wrap_browser(browser)

    def _build_privacy_tab(self) -> QWidget:
        browser = QTextBrowser()
        browser.setPlainText(self._t("about.privacy.body"))
        return self._wrap_browser(browser)

    def _wrap_browser(self, browser: QTextBrowser) -> QWidget:
        browser.setOpenExternalLinks(True)
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(browser)
        return tab

    def _about_rows(self) -> list[tuple[str, str]]:
        return [
            (self._t("about.version"), _resolve_app_version()),
            (self._t("about.revision"), _resolve_git_revision()),
            (self._t("about.python"), platform.python_version()),
            (self._t("about.qt"), qVersion()),
            (self._t("about.operating_system"), platform.platform()),
            (self._t("about.architecture"), platform.machine()),
            (self._t("about.printer_profile"), KATASYMBOL_E10_PROFILE.display_name),
        ]

    def _copy_about_to_clipboard(self) -> None:
        text = "\n".join(f"{label}: {value}" for label, value in self._about_rows())
        QApplication.clipboard().setText(text)


class InkOtterWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1080, 780)

        self.settings = self._load_settings()
        self.language_code = _resolve_initial_language(self.settings)
        self.base_catalog = _load_language_catalog("en")
        self.catalog = self._merged_catalog(self.language_code)
        self.selected_mac = ""
        self.current_printer_label = ""
        self.current_document_path = ""
        self.recent_documents = self._load_recent_documents()
        self._settings_dialog: SettingsDialog | None = None
        self._recent_file_actions: list[QAction] = []
        self._tasks: list[tuple[QThread, TaskWorker]] = []
        self._next_task_id = 1
        self._task_callbacks: dict[int, tuple[object, object]] = {}
        self._preview_generation = 0
        self._watched_document_dir = ""
        self._watched_document_mtime_ns = 0

        self._build_ui()
        self._build_menu_bar()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._document_watch_timer = QTimer(self)
        self._document_watch_timer.setSingleShot(True)
        self._document_watch_timer.timeout.connect(self._reload_changed_document)
        self._document_watcher = QFileSystemWatcher(self)
        self._document_watcher.fileChanged.connect(self._on_document_file_changed)
        self._document_watcher.directoryChanged.connect(self._on_document_directory_changed)

        self._update_threshold_label()
        self._set_threshold_enabled()
        self._on_zoom_changed()
        self._refresh_file_menu()
        self._sync_menu_state_from_controls()
        self._apply_translations()
        self._update_window_title()
        self._set_printer_display(self._t("label.no_printer"))
        self._set_preview_placeholder(self._t("placeholder.preview.choose"), use_logo=True)
        self._update_status(self._t("status.ready"))
        QTimer.singleShot(0, self._auto_select_printer_on_startup)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        brand_column = QVBoxLayout()
        brand_column.setContentsMargins(0, 0, 0, 0)
        brand_column.setSpacing(2)
        self.title_label = QLabel(APP_NAME)
        title_font = self.title_label.font()
        title_font.setPointSize(title_font.pointSize() + 8)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet("color: palette(mid);")
        brand_column.addWidget(self.title_label)
        brand_column.addWidget(self.subtitle_label)
        header_layout.addLayout(brand_column, stretch=1)

        logo_label = QLabel()
        logo_pixmap = _resolve_header_logo_pixmap()
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(logo_label, stretch=0, alignment=Qt.AlignmentFlag.AlignRight)
        outer.addWidget(header)

        self.preview_group = QGroupBox()
        preview_layout = QVBoxLayout(self.preview_group)

        self.no_scale_checkbox = QCheckBox("Use actual document size for SVG files")
        self.no_scale_checkbox.setVisible(False)
        self.no_scale_checkbox.toggled.connect(self._schedule_preview_refresh)
        self.no_scale_checkbox.toggled.connect(self._sync_menu_state_from_controls)

        self.monochrome_mode_combo = QComboBox()
        self.monochrome_mode_combo.setVisible(False)
        self.monochrome_mode_combo.addItem("Threshold", MonochromeStrategy.THRESHOLD)
        self.monochrome_mode_combo.addItem("Dither", MonochromeStrategy.FLOYD_STEINBERG)
        self.monochrome_mode_combo.currentIndexChanged.connect(self._on_preview_controls_changed)
        self.monochrome_mode_combo.currentIndexChanged.connect(self._sync_menu_state_from_controls)

        self.preview_controls_widget = QWidget()
        preview_controls = QFormLayout(self.preview_controls_widget)
        preview_controls.setContentsMargins(0, 0, 0, 0)
        threshold_row = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(0, 255)
        self.threshold_slider.setValue(DEFAULT_MONOCHROME_THRESHOLD)
        self.threshold_slider.valueChanged.connect(self._on_preview_controls_changed)
        self.threshold_value_label = QLabel()
        self.threshold_value_label.setMinimumWidth(40)
        threshold_row.addWidget(self.threshold_slider, stretch=1)
        threshold_row.addWidget(self.threshold_value_label)
        self.threshold_row_widget = QWidget()
        self.threshold_row_widget.setLayout(threshold_row)

        zoom_row = QHBoxLayout()
        self.preview_zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.preview_zoom_slider.setRange(100, 1200)
        self.preview_zoom_slider.setSingleStep(50)
        self.preview_zoom_slider.setPageStep(100)
        self.preview_zoom_slider.setValue(DEFAULT_PREVIEW_ZOOM_PERCENT)
        self.preview_zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self.preview_zoom_label = QLabel()
        self.preview_zoom_label.setMinimumWidth(56)
        zoom_row.addWidget(self.preview_zoom_slider, stretch=1)
        zoom_row.addWidget(self.preview_zoom_label)
        self.zoom_row_widget = QWidget()
        self.zoom_row_widget.setLayout(zoom_row)

        self.threshold_row_label = QLabel()
        self.zoom_row_label = QLabel()
        preview_controls.addRow(self.threshold_row_label, self.threshold_row_widget)
        preview_controls.addRow(self.zoom_row_label, self.zoom_row_widget)
        self.sync_previews_checkbox = QCheckBox("Sync both previews")
        self.sync_previews_checkbox.setVisible(False)
        self.sync_previews_checkbox.setChecked(True)
        self.sync_previews_checkbox.toggled.connect(self._sync_menu_state_from_controls)

        preview_grid = QGridLayout()
        preview_grid.setColumnStretch(0, 1)
        preview_grid.setColumnStretch(1, 1)
        self.graphic_header_label = QLabel()
        self.print_header_label = QLabel()
        preview_grid.addWidget(self.graphic_header_label, 0, 0)
        preview_grid.addWidget(self.print_header_label, 0, 1)

        self.graphic_preview = PreviewLabel("The normalized placed graphic will appear here.")
        self.print_preview = PreviewLabel("The device-ready monochrome result will appear here.")

        self.graphic_scroll = PannableScrollArea()
        self.graphic_scroll.set_preview_widget(self.graphic_preview)
        self.print_scroll = PannableScrollArea()
        self.print_scroll.set_preview_widget(self.print_preview)
        self.graphic_scroll.scrolled.connect(self._sync_from_graphic_scroll)
        self.print_scroll.scrolled.connect(self._sync_from_print_scroll)
        self.graphic_scroll.zoom_requested.connect(self._adjust_preview_zoom_from_wheel)
        self.print_scroll.zoom_requested.connect(self._adjust_preview_zoom_from_wheel)

        preview_grid.addWidget(self.graphic_scroll, 1, 0)
        preview_grid.addWidget(self.print_scroll, 1, 1)
        preview_layout.addLayout(preview_grid)

        self.preview_info_label = QLabel()
        self.preview_info_label.setWordWrap(True)
        self.preview_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview_info_label.setStyleSheet("color: palette(dark);")
        preview_layout.addWidget(self.preview_info_label)

        preview_layout.addWidget(self.preview_controls_widget)
        outer.addWidget(self.preview_group, stretch=1)

        self.channel_spin = QSpinBox()
        self.channel_spin.setRange(1, 30)
        self.channel_spin.setValue(1)
        self.scan_seconds_spin = QSpinBox()
        self.scan_seconds_spin.setRange(0, 20)
        self.scan_seconds_spin.setValue(4)

        action_row = QHBoxLayout()
        self.print_button = QPushButton()
        self.print_button.clicked.connect(self._print)
        self.print_button.setAutoDefault(True)
        action_row.addStretch(1)
        action_row.addWidget(self.print_button)
        outer.addLayout(action_row)

        self.summary_group = QGroupBox()
        summary_layout = QVBoxLayout(self.summary_group)
        self.summary_output = QPlainTextEdit()
        self.summary_output.setReadOnly(True)
        self.summary_output.setPlaceholderText("Preview and printer details will appear here.")
        summary_layout.addWidget(self.summary_output)
        self.summary_group.setVisible(False)
        outer.addWidget(self.summary_group, stretch=0)

        self.setStatusBar(QStatusBar())

    def _load_recent_documents(self) -> list[str]:
        try:
            payload = json.loads(RECENT_DOCUMENTS_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []
        if not isinstance(payload, list):
            return []
        recent: list[str] = []
        for entry in payload:
            if isinstance(entry, str) and entry and entry not in recent:
                recent.append(entry)
        return recent[:MAX_RECENT_DOCUMENTS]

    def _load_settings(self) -> dict[str, str]:
        try:
            payload = json.loads(GUI_SETTINGS_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_settings(self) -> None:
        GUI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        GUI_SETTINGS_PATH.write_text(
            json.dumps({"language": self.language_code}, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _merged_catalog(self, language_code: str) -> dict[str, str]:
        merged = dict(self.base_catalog)
        merged.update(_load_language_catalog(language_code))
        return merged

    def _t(self, key: str, *, default: str | None = None, **kwargs) -> str:
        text = self.catalog.get(key, default if default is not None else key)
        return text.format(**kwargs) if kwargs else text

    def _set_language(self, language_code: str) -> None:
        if language_code not in SUPPORTED_LANGUAGES or language_code == self.language_code:
            return
        self.language_code = language_code
        self.catalog = self._merged_catalog(language_code)
        self._save_settings()
        self._apply_translations()
        self._refresh_file_menu()
        self._sync_menu_state_from_controls()
        self._update_window_title()
        self._set_printer_display(self.current_printer_label or self._t("label.no_printer"))
        if self.current_document_path.strip():
            self._schedule_preview_refresh()
        elif self.graphic_preview.pixmap().isNull() and self.print_preview.pixmap().isNull():
            self._set_preview_placeholder(self._t("placeholder.preview.choose"), use_logo=True)

    def _apply_translations(self) -> None:
        self.subtitle_label.setText(self._t("header.tagline"))
        self.preview_group.setTitle("")
        self.graphic_header_label.setText(self._t("label.graphic"))
        self.print_header_label.setText(self._t("label.print_image"))
        self.threshold_row_label.setText(self._t("label.preview_threshold"))
        self.zoom_row_label.setText(self._t("label.preview_zoom"))
        self.print_button.setText(self._t("action.print"))
        self.summary_group.setTitle(self._t("action.summary"))
        self.summary_output.setPlaceholderText(self._t("placeholder.summary"))
        self.file_menu.setTitle(self._t("menu.file"))
        self.open_action.setText(self._t("action.open"))
        self.clear_history_action.setText(self._t("action.clear"))
        self.print_action.setText(self._t("action.print"))
        self.quit_action.setText(self._t("action.quit"))
        self.view_menu.setTitle(self._t("menu.view"))
        self.actual_size_action.setText(self._t("option.actual_size_svg"))
        self.raster_menu.setTitle(self._t("menu.rastering"))
        self.raster_threshold_action.setText(self._t("action.threshold"))
        self.raster_dither_action.setText(self._t("action.dither"))
        self.sync_previews_action.setText(self._t("option.sync_previews"))
        self.zoom_in_action.setText(self._t("view.zoom_in"))
        self.zoom_out_action.setText(self._t("view.zoom_out"))
        self.reset_zoom_action.setText(self._t("view.reset_zoom"))
        self.settings_menu.setTitle(self._t("menu.settings", default="Settings"))
        self.settings_action.setText(self._t("menu.settings", default="Settings") + "…")
        self.info_menu.setTitle(self._t("menu.info"))
        self.show_summary_action.setText(self._t("action.summary"))
        self.about_action.setText(self._t("about.dialog_title"))

    def _save_recent_documents(self) -> None:
        RECENT_DOCUMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECENT_DOCUMENTS_PATH.write_text(
            json.dumps(self.recent_documents[:MAX_RECENT_DOCUMENTS], ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def _document_mtime_ns(self, path: str) -> int:
        try:
            return Path(path).stat().st_mtime_ns
        except OSError:
            return 0

    def _update_document_watch(self) -> None:
        watched_files = self._document_watcher.files()
        if watched_files:
            self._document_watcher.removePaths(watched_files)
        watched_dirs = self._document_watcher.directories()
        if watched_dirs:
            self._document_watcher.removePaths(watched_dirs)

        self._watched_document_dir = ""
        self._watched_document_mtime_ns = 0
        if not self.current_document_path:
            return

        document_path = Path(self.current_document_path)
        if document_path.exists():
            self._document_watcher.addPath(str(document_path))
            self._watched_document_mtime_ns = self._document_mtime_ns(self.current_document_path)

        document_dir = str(document_path.parent)
        if document_dir and Path(document_dir).exists():
            self._document_watcher.addPath(document_dir)
            self._watched_document_dir = document_dir

    def _on_document_file_changed(self, path: str) -> None:
        if path != self.current_document_path:
            return
        self._document_watch_timer.start(280)

    def _on_document_directory_changed(self, path: str) -> None:
        if path != self._watched_document_dir:
            return
        self._document_watch_timer.start(280)

    def _reload_changed_document(self) -> None:
        if not self.current_document_path:
            return
        document_path = Path(self.current_document_path)
        if not document_path.exists():
            return

        current_mtime = self._document_mtime_ns(self.current_document_path)
        if current_mtime == self._watched_document_mtime_ns:
            self._update_document_watch()
            return

        self._watched_document_mtime_ns = current_mtime
        self._update_document_watch()
        self._schedule_preview_refresh()
        self._update_status(self._t("status.document_reloaded"))

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        self.file_menu = menu_bar.addMenu("")
        self.open_action = QAction("", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self._choose_file)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addSeparator()
        self.recent_file_separator = self.file_menu.addSeparator()
        self.clear_history_action = QAction("", self)
        self.clear_history_action.triggered.connect(self._clear_recent_documents)
        self.file_menu.addAction(self.clear_history_action)
        self.file_menu.addSeparator()
        self.print_action = QAction("", self)
        self.print_action.setShortcut("Ctrl+P")
        self.print_action.triggered.connect(self._print)
        self.file_menu.addAction(self.print_action)
        self.file_menu.addSeparator()
        self.quit_action = QAction("", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.quit_action)

        self.view_menu = menu_bar.addMenu("")
        self.actual_size_action = QAction("", self)
        self.actual_size_action.setCheckable(True)
        self.actual_size_action.setShortcut("Ctrl+Shift+U")
        self.actual_size_action.toggled.connect(self.no_scale_checkbox.setChecked)
        self.view_menu.addAction(self.actual_size_action)

        self.raster_menu = self.view_menu.addMenu("")
        self.raster_action_group = QActionGroup(self)
        self.raster_action_group.setExclusive(True)
        self.raster_threshold_action = QAction("", self)
        self.raster_threshold_action.setCheckable(True)
        self.raster_threshold_action.setShortcut("Ctrl+1")
        self.raster_threshold_action.triggered.connect(lambda: self.monochrome_mode_combo.setCurrentIndex(0))
        self.raster_dither_action = QAction("", self)
        self.raster_dither_action.setCheckable(True)
        self.raster_dither_action.setShortcut("Ctrl+2")
        self.raster_dither_action.triggered.connect(lambda: self.monochrome_mode_combo.setCurrentIndex(1))
        self.raster_action_group.addAction(self.raster_threshold_action)
        self.raster_action_group.addAction(self.raster_dither_action)
        self.raster_menu.addAction(self.raster_threshold_action)
        self.raster_menu.addAction(self.raster_dither_action)

        self.sync_previews_action = QAction("", self)
        self.sync_previews_action.setCheckable(True)
        self.sync_previews_action.setShortcut("Ctrl+Shift+Y")
        self.sync_previews_action.toggled.connect(self.sync_previews_checkbox.setChecked)
        self.view_menu.addAction(self.sync_previews_action)
        self.view_menu.addSeparator()
        self.zoom_in_action = QAction("", self)
        self.zoom_in_action.setShortcut("Ctrl++")
        self.zoom_in_action.triggered.connect(lambda: self._step_preview_zoom(+1))
        self.view_menu.addAction(self.zoom_in_action)
        self.zoom_out_action = QAction("", self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.zoom_out_action.triggered.connect(lambda: self._step_preview_zoom(-1))
        self.view_menu.addAction(self.zoom_out_action)
        self.reset_zoom_action = QAction("", self)
        self.reset_zoom_action.setShortcut("Ctrl+0")
        self.reset_zoom_action.triggered.connect(lambda: self.preview_zoom_slider.setValue(DEFAULT_PREVIEW_ZOOM_PERCENT))
        self.view_menu.addAction(self.reset_zoom_action)

        self.settings_menu = menu_bar.addMenu("")
        self.settings_action = QAction("", self)
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.triggered.connect(self._show_settings_dialog)
        self.settings_menu.addAction(self.settings_action)

        self.info_menu = menu_bar.addMenu("")
        self.show_summary_action = QAction("", self)
        self.show_summary_action.setCheckable(True)
        self.show_summary_action.setShortcut("Ctrl+I")
        self.show_summary_action.toggled.connect(self.summary_group.setVisible)
        self.show_summary_action.toggled.connect(lambda _checked: self._update_status(self._t("status.summary_visible")))
        self.info_menu.addAction(self.show_summary_action)
        self.info_menu.addSeparator()
        self.about_action = QAction("", self)
        self.about_action.setShortcut("F1")
        self.about_action.triggered.connect(self._show_about_dialog)
        self.info_menu.addAction(self.about_action)

    def _refresh_file_menu(self) -> None:
        for action in getattr(self, "_recent_file_actions", []):
            self.file_menu.removeAction(action)
        self._recent_file_actions = []

        insert_before = self.clear_history_action
        if self.recent_documents:
            self.recent_file_separator.setVisible(True)
            for path in self.recent_documents[:MAX_RECENT_DOCUMENTS]:
                action = QAction(Path(path).name, self)
                action.setToolTip(path)
                action.triggered.connect(
                    lambda _checked=False, recent_path=path: self._open_recent_document(recent_path)
                )
                self.file_menu.insertAction(insert_before, action)
                self._recent_file_actions.append(action)
        else:
            self.recent_file_separator.setVisible(False)
        self.clear_history_action.setEnabled(bool(self.recent_documents))

    def _update_window_title(self) -> None:
        if self.current_document_path:
            self.setWindowTitle(Path(self.current_document_path).name)
            return
        self.setWindowTitle(APP_NAME)

    def _update_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _set_printer_display(self, label: str) -> None:
        self.current_printer_label = label
        if self._settings_dialog is not None:
            self._settings_dialog.set_printer_label(label)

    def _sync_menu_state_from_controls(self) -> None:
        self.actual_size_action.setChecked(self.no_scale_checkbox.isChecked())
        self.sync_previews_action.setChecked(self.sync_previews_checkbox.isChecked())
        is_threshold = self.monochrome_mode_combo.currentData() == MonochromeStrategy.THRESHOLD
        self.raster_threshold_action.setChecked(is_threshold)
        self.raster_dither_action.setChecked(not is_threshold)

    def _show_error(self, title: str, message: str) -> None:
        self._update_status(message)
        QMessageBox.critical(self, title, message)

    def _show_info(self, title: str, message: str) -> None:
        self._update_status(message)
        QMessageBox.information(self, title, message)

    def _choose_file(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            self._t("dialog.file.select"),
            "",
            self._t("dialog.file.filter"),
        )
        if path:
            self._set_current_document(path)

    def _open_recent_document(self, path: str) -> None:
        if not Path(path).exists():
            self.recent_documents = [entry for entry in self.recent_documents if entry != path]
            self._save_recent_documents()
            self._refresh_file_menu()
            self._show_error(
                self._t("dialog.missing_recent.title"),
                self._t("dialog.missing_recent.message", path=path),
            )
            return
        self._set_current_document(path)

    def _clear_recent_documents(self) -> None:
        self.recent_documents = []
        self._save_recent_documents()
        self._refresh_file_menu()
        self._update_status(self._t("status.history_cleared"))

    def _set_current_document(self, path: str) -> None:
        normalized_path = str(Path(path).expanduser().resolve())
        self.current_document_path = normalized_path
        self.recent_documents = [entry for entry in self.recent_documents if entry != normalized_path]
        self.recent_documents.insert(0, normalized_path)
        self.recent_documents = self.recent_documents[:MAX_RECENT_DOCUMENTS]
        self._save_recent_documents()
        self._refresh_file_menu()
        self._update_window_title()
        self._update_document_watch()
        self._schedule_preview_refresh()
        self._update_status(self._t("status.document_selected"))

    def _require_image(self) -> Path | None:
        raw = self.current_document_path.strip()
        if not raw:
            self._show_error(self._t("dialog.missing_document.title"), self._t("dialog.missing_document.message"))
            return None
        return Path(raw)

    def _selected_monochrome_strategy(self) -> MonochromeStrategy:
        return MonochromeStrategy(self.monochrome_mode_combo.currentData())

    def _selected_threshold(self) -> int:
        return self.threshold_slider.value()

    def _update_threshold_label(self) -> None:
        self.threshold_value_label.setText(str(self.threshold_slider.value()))

    def _set_threshold_enabled(self) -> None:
        visible = self._selected_monochrome_strategy() == MonochromeStrategy.THRESHOLD
        self.threshold_slider.setEnabled(visible)
        self.threshold_value_label.setEnabled(visible)
        self.threshold_row_label.setVisible(visible)
        self.threshold_row_widget.setVisible(visible)

    def _on_preview_controls_changed(self) -> None:
        self._update_threshold_label()
        self._set_threshold_enabled()
        self._sync_menu_state_from_controls()
        self._schedule_preview_refresh()

    def _on_zoom_changed(self) -> None:
        zoom_percent = self.preview_zoom_slider.value()
        self.preview_zoom_label.setText(f"{zoom_percent}%")
        self.graphic_preview.set_zoom_percent(zoom_percent)
        self.print_preview.set_zoom_percent(zoom_percent)
        if self.sync_previews_checkbox.isChecked():
            self._sync_scroll_positions(
                self.graphic_scroll.horizontalScrollBar().value(),
                self.graphic_scroll.verticalScrollBar().value(),
            )

    def _sync_scroll_positions(self, x: int, y: int) -> None:
        self.graphic_scroll.set_scroll_position(x, y)
        self.print_scroll.set_scroll_position(x, y)

    def _sync_from_graphic_scroll(self, x: int, y: int) -> None:
        if self.sync_previews_checkbox.isChecked():
            self.print_scroll.set_scroll_position(x, y)

    def _sync_from_print_scroll(self, x: int, y: int) -> None:
        if self.sync_previews_checkbox.isChecked():
            self.graphic_scroll.set_scroll_position(x, y)

    def _adjust_preview_zoom_from_wheel(self, delta_y: int) -> None:
        self._step_preview_zoom(1 if delta_y > 0 else -1)

    def _step_preview_zoom(self, direction: int) -> None:
        step = self.preview_zoom_slider.singleStep()
        new_value = self.preview_zoom_slider.value() + (direction * step)
        new_value = max(self.preview_zoom_slider.minimum(), min(self.preview_zoom_slider.maximum(), new_value))
        self.preview_zoom_slider.setValue(new_value)

    def _set_summary_text(self, text: str) -> None:
        self.summary_output.setPlainText(text)

    def _render_preview_info_text(self, summary, physical_preview_width_px: int, physical_preview_height_px: int, right_margin_px: int) -> str:
        mode = self._selected_monochrome_strategy().value
        if self._selected_monochrome_strategy() == MonochromeStrategy.THRESHOLD:
            mode = f"{mode} {self._selected_threshold()}"
        return " | ".join(
            (
                f"{self._t('summary.layout')}: {summary.layout_mode}",
                f"{self._t('summary.canvas')}: {summary.canvas_width_px}x{summary.canvas_height_px}px",
                f"{self._t('summary.pages')}: {summary.page_count}",
                f"{self._t('summary.rastering')}: {mode}",
                f"{self._t('summary.strip')}: {physical_preview_width_px}x{physical_preview_height_px}px",
                f"{self._t('summary.end_margin')}: {right_margin_px}px",
            )
        )

    def _render_summary_text(self, summary) -> str:
        mode = self._selected_monochrome_strategy().value
        threshold_line = (
            f"{self._t('summary.threshold')}: {self._selected_threshold()}\n"
            if self._selected_monochrome_strategy() == MonochromeStrategy.THRESHOLD
            else ""
        )
        return (
            f"{self._t('summary.device')}: {summary.device_name}\n"
            f"{self._t('summary.document')}: {summary.document_path}\n"
            f"{self._t('summary.layout')}: {summary.layout_mode}\n"
            f"{self._t('summary.canvas')}: {summary.canvas_width_px}x{summary.canvas_height_px}\n"
            f"{self._t('summary.pages')}: {summary.page_count}\n"
            f"{self._t('summary.frames')}: {summary.frame_count}\n"
            f"{self._t('summary.chunks')}: {list(summary.chunks_per_page)}\n"
            f"{self._t('summary.rastering')}: {mode}\n"
            f"{threshold_line}"
        ).rstrip()

    def _pil_to_preview_pixmap(self, image_bytes: bytes) -> QPixmap:
        qimage = QImage.fromData(image_bytes, "PNG")
        if qimage.isNull():
            return QPixmap()
        return QPixmap.fromImage(qimage)

    def _decorate_strip_preview(
        self,
        pixmap: QPixmap,
        *,
        target_size: QSize | None = None,
        show_shadow: bool = True,
    ) -> QPixmap:
        if pixmap.isNull():
            return QPixmap()

        margin = 28
        shadow_offset = 10 if show_shadow else 0
        shadow_blur = 18 if show_shadow else 0
        strip_width = pixmap.width()
        strip_height = pixmap.height()
        natural_width = strip_width + margin * 2 + shadow_offset + shadow_blur
        natural_height = strip_height + margin * 2 + shadow_offset + shadow_blur
        canvas_width = natural_width if target_size is None else max(natural_width, target_size.width())
        canvas_height = natural_height if target_size is None else max(natural_height, target_size.height())
        content_rect_x = (canvas_width - (strip_width + shadow_offset + shadow_blur)) // 2
        content_rect_y = (canvas_height - (strip_height + shadow_offset + shadow_blur)) // 2
        decorated = QPixmap(canvas_width, canvas_height)
        decorated.fill(QColor(242, 242, 242))

        painter = QPainter(decorated)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if show_shadow:
            shadow_rect = (
                content_rect_x + shadow_offset,
                content_rect_y + shadow_offset,
                strip_width,
                strip_height,
            )
            for alpha, grow in ((38, 0), (20, 4), (10, 8)):
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, alpha))
                painter.drawRoundedRect(
                    shadow_rect[0] - grow,
                    shadow_rect[1] - grow,
                    shadow_rect[2] + grow * 2,
                    shadow_rect[3] + grow * 2,
                    8,
                    8,
                )

        painter.setPen(QPen(QColor(170, 170, 170), 1))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRect(content_rect_x, content_rect_y, strip_width, strip_height)
        painter.drawPixmap(content_rect_x, content_rect_y, pixmap)
        painter.end()
        return decorated

    def _set_preview_placeholder(self, text: str, *, use_logo: bool = False) -> None:
        placeholder_pixmap = _resolve_placeholder_logo_pixmap() if use_logo else QPixmap()
        self.graphic_preview.show_placeholder(text, pixmap=placeholder_pixmap)
        self.print_preview.show_placeholder(text, pixmap=placeholder_pixmap)
        self.preview_info_label.clear()

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(
            translate=self._t,
            language_code=self.language_code,
            current_printer_label=self.current_printer_label or self._t("label.no_printer"),
            channel=self.channel_spin.value(),
            scan_seconds=self.scan_seconds_spin.value(),
            parent=self,
        )
        dialog.search_button.clicked.connect(self._search_printers)
        dialog.auto_select_button.clicked.connect(self._auto_select_printer)
        self._settings_dialog = dialog
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        finally:
            self._settings_dialog = None
        selected_language = str(dialog.language_combo.currentData())
        if selected_language != self.language_code:
            self._set_language(selected_language)
        self.channel_spin.setValue(dialog.channel_spin.value())
        self.scan_seconds_spin.setValue(dialog.scan_seconds_spin.value())
        self._update_status(self._t("status.transport_updated"))

    def _show_about_dialog(self) -> None:
        dialog = AboutInkOtterDialog(self._t, self)
        dialog.exec()

    def _schedule_preview_refresh(self) -> None:
        if not self.current_document_path.strip():
            self._update_document_watch()
            self._set_preview_placeholder(self._t("placeholder.preview.choose"), use_logo=True)
            self.summary_output.clear()
            return
        self._preview_timer.start(180)

    def _refresh_preview(self) -> None:
        image = self.current_document_path.strip()
        if not image:
            return
        preview_generation = self._preview_generation = self._preview_generation + 1

        def build_preview():
            job = prepare_print_job(
                image,
                KATASYMBOL_E10_PROFILE,
                no_scale=self.no_scale_checkbox.isChecked(),
                monochrome_strategy=self._selected_monochrome_strategy(),
                monochrome_threshold=self._selected_threshold(),
            )
            summary = summarize_print_job(job)
            previews = build_preview_images(job)
            return preview_generation, PreviewPayload(
                summary_text=self._render_summary_text(summary),
                preview_info_text=self._render_preview_info_text(
                    summary,
                    previews.strip_width_px,
                    previews.strip_height_px,
                    previews.right_margin_px,
                ),
                graphic_png=encode_preview_png(previews.graphic_image),
                physical_print_png=encode_preview_png(previews.physical_print_image),
            )

        def apply_preview(result) -> None:
            generation, payload = result
            if generation != self._preview_generation:
                return
            graphic_pixmap = self._pil_to_preview_pixmap(payload.graphic_png)
            physical_pixmap = self._pil_to_preview_pixmap(payload.physical_print_png)
            if graphic_pixmap.isNull() or physical_pixmap.isNull():
                self._set_preview_placeholder(self._t("placeholder.preview.unavailable"))
                self._set_summary_text(payload.summary_text)
                self._update_status(self._t("task.preview_error"))
                return
            shared_target_size = QSize(
                max(graphic_pixmap.width(), physical_pixmap.width()),
                max(graphic_pixmap.height(), physical_pixmap.height()),
            )
            self.graphic_preview.show_pixmap(
                self._decorate_strip_preview(
                    graphic_pixmap,
                    target_size=shared_target_size,
                    show_shadow=False,
                )
            )
            self.print_preview.show_pixmap(
                self._decorate_strip_preview(
                    physical_pixmap,
                    target_size=shared_target_size,
                    show_shadow=False,
                )
            )
            self.preview_info_label.setText(payload.preview_info_text)
            self._set_summary_text(payload.summary_text)
            self._update_status(self._t("status.preview_updated"))

        def handle_preview_failure(title: str, message: str) -> None:
            if preview_generation != self._preview_generation:
                return
            self._set_preview_placeholder(self._t("placeholder.preview.unavailable"))
            self._set_summary_text(f"{title}\n\n{message}")
            self._update_status(message)

        self._start_task(
            build_preview,
            status_message=self._t("task.preview_status"),
            error_title=self._t("task.preview_error"),
            on_success=apply_preview,
            on_failure=handle_preview_failure,
        )

    def _dispatch_task_success(self, task_id: int, result) -> None:
        callbacks = self._task_callbacks.pop(task_id, None)
        if callbacks is None:
            return
        on_success, _on_failure = callbacks
        on_success(result)

    def _dispatch_task_failure(self, task_id: int, title: str, message: str) -> None:
        callbacks = self._task_callbacks.pop(task_id, None)
        if callbacks is None:
            return
        _on_success, on_failure = callbacks
        on_failure(title, message)

    def _start_task(self, fn, *, status_message: str, error_title: str, on_success, on_failure=None) -> None:
        self._update_status(status_message)
        thread = QThread(self)
        task_id = self._next_task_id
        self._next_task_id += 1
        failure_handler = self._show_error if on_failure is None else on_failure
        self._task_callbacks[task_id] = (on_success, failure_handler)
        worker = TaskWorker(task_id, fn, error_title=error_title)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._dispatch_task_success)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self._dispatch_task_failure)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._release_task(thread))
        self._tasks.append((thread, worker))
        thread.start()

    def _release_task(self, finished_thread: QThread) -> None:
        self._tasks = [task for task in self._tasks if task[0] is not finished_thread]

    def _search_printers(self) -> None:
        def run_scan():
            return list_visible_devices(scan_seconds=self.scan_seconds_spin.value())

        def show_scan_results(devices) -> None:
            if not devices:
                self._show_info(self._t("dialog.info.no_printers_title"), self._t("dialog.info.no_printers_message"))
                return
            dialog = DeviceSelectionDialog(devices, self._t, parent=self)
            lines = []
            for device in devices:
                suffix = (
                    f"  {self._t('printer.candidate_suffix')}"
                    if first_matching_name(KATASYMBOL_E10_PROFILE, device.name)
                    else ""
                )
                lines.append(f"{device.mac}  {device.name}{suffix}")
            self._set_summary_text(self._t("summary.device_scan") + ":\n\n" + "\n".join(lines))
            self._update_status(self._t("status.scan_finished"))
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.selected_mac = dialog.selected_mac
                self._set_printer_display(dialog.selected_label)
                self._update_status(self._t("status.printer_selected"))

        self._start_task(
            run_scan,
            status_message=self._t("task.discovery_status"),
            error_title=self._t("task.discovery_error"),
            on_success=show_scan_results,
        )

    def _auto_select_printer(self) -> None:
        def run_selection():
            return auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=self.scan_seconds_spin.value())

        def apply_selection(selected) -> None:
            self.selected_mac = selected.mac
            self._set_printer_display(f"{selected.name} ({selected.mac})")
            self._update_status(self._t("status.printer_selected"))

        self._start_task(
            run_selection,
            status_message=self._t("task.printer_select_status"),
            error_title=self._t("task.printer_auto_error"),
            on_success=apply_selection,
        )

    def _auto_select_printer_on_startup(self) -> None:
        def run_selection():
            return auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=self.scan_seconds_spin.value())

        def apply_selection(selected) -> None:
            self.selected_mac = selected.mac
            self._set_printer_display(f"{selected.name} ({selected.mac})")
            self._update_status(self._t("status.printer_auto_selected"))

        def ignore_failure(_title: str, _message: str) -> None:
            self._update_status(self._t("status.ready"))

        self._start_task(
            run_selection,
            status_message=self._t("task.printer_startup_status"),
            error_title=self._t("task.printer_select_error"),
            on_success=apply_selection,
            on_failure=ignore_failure,
        )

    def _dry_run(self) -> None:
        image = self._require_image()
        if image is None:
            return
        self._preview_generation += 1
        self._refresh_preview()

    def _print(self) -> None:
        image = self._require_image()
        if image is None:
            return

        def run_print():
            job = prepare_print_job(
                image,
                KATASYMBOL_E10_PROFILE,
                no_scale=self.no_scale_checkbox.isChecked(),
                monochrome_strategy=self._selected_monochrome_strategy(),
                monochrome_threshold=self._selected_threshold(),
            )
            summary = summarize_print_job(job)
            target_mac = self.selected_mac
            printer_label = self.current_printer_label or self._t("label.no_printer")
            if not target_mac:
                selected = auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=self.scan_seconds_spin.value())
                target_mac = selected.mac
                printer_label = f"{selected.name} ({selected.mac})"
            send_packets(
                mac=target_mac,
                channel=self.channel_spin.value(),
                packets=job.frames,
            )
            return summary, target_mac, printer_label

        def finish_print(result) -> None:
            summary, target_mac, printer_label = result
            self.selected_mac = target_mac
            self._set_printer_display(printer_label)
            self._set_summary_text(
                self._render_summary_text(summary) + f"\n\n{self._t('summary.printed_via')}: {printer_label}"
            )
            self._update_status(self._t("status.print_sent"))

        self._start_task(
            run_print,
            status_message=self._t("task.print_status"),
            error_title=self._t("task.print_error"),
            on_success=finish_print,
        )


def _resolve_window_icon() -> QIcon:
    icon = QIcon.fromTheme("inkotter")
    if not icon.isNull():
        return icon

    project_root = Path(__file__).resolve().parents[3]
    icon_path = project_root / "assets" / "icons" / "inkotter.svg"
    return QIcon(str(icon_path))


def _resolve_header_logo_pixmap() -> QPixmap:
    project_root = Path(__file__).resolve().parents[3]
    for icon_name in ("Inkotter.svg", "inkotter.svg"):
        icon_path = project_root / "assets" / "icons" / icon_name
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                return pixmap.scaledToHeight(72, Qt.TransformationMode.SmoothTransformation)
    return QPixmap()


def _resolve_placeholder_logo_pixmap() -> QPixmap:
    if not PLACEHOLDER_LOGO_PATH.exists():
        return QPixmap()
    return QPixmap(str(PLACEHOLDER_LOGO_PATH))


def _resolve_app_version() -> str:
    try:
        return package_version("inkotter")
    except PackageNotFoundError:
        return "0.1.0"


def _resolve_git_revision() -> str:
    head_path = Path(__file__).resolve().parents[3] / ".git" / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    if not head.startswith("ref: "):
        return head[:12]
    ref_path = Path(__file__).resolve().parents[3] / ".git" / head[5:]
    try:
        return ref_path.read_text(encoding="utf-8").strip()[:12]
    except OSError:
        return "unknown"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("InkOtter")
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("inkotter")
    app.setWindowIcon(_resolve_window_icon())

    window = InkOtterWindow()
    window.setWindowIcon(app.windowIcon())
    window.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
