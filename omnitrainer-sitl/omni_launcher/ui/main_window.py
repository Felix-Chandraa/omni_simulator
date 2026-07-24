from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME
from ..aviation_overlay import build_aviation_overlay, load_initial_overlay
from ..config import DEFAULT_PROFILE, LauncherProfile, ProfileError, find_ardupilot_root, load_profile
from ..efi_process import build_efi_command
from ..location_writer import write_location
from ..process_utils import is_tcp_port_open, parse_tcp_endpoint
from ..rangefinder_process import build_rangefinder_command
from ..sitl_process import ProcessRunner, build_docker_sitl_command, build_sitl_command
from ..terrain import fetch_terrain_altitude_m
from ..validation import validate_docker_setup, validate_setup
from .map_widget import MapWidget
from .styles import apply_styles


M_TO_FT = 3.280839895013123


def altitude_to_unit(value_m: float, unit: str) -> float:
    return value_m * M_TO_FT if unit == "ft" else value_m


def altitude_to_meters(value: float, unit: str) -> float:
    return value / M_TO_FT if unit == "ft" else value


class AviationWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)

    def __init__(self, lat: float, lng: float, radius_km: float, max_age_days: int):
        super().__init__()
        self.lat = lat
        self.lng = lng
        self.radius_km = radius_km
        self.max_age_days = max_age_days
        self.cancelled = False

    @pyqtSlot()
    def run(self) -> None:
        data = build_aviation_overlay(
            self.lat,
            self.lng,
            self.radius_km,
            self.max_age_days,
            force_refresh=True,
            progress_callback=self.progress.emit,
            should_stop=lambda: self.cancelled,
        )
        self.finished.emit(data)


class TerrainWorker(QObject):
    finished = pyqtSignal(float)
    failed = pyqtSignal(str)

    def __init__(self, lat: float, lng: float):
        super().__init__()
        self.lat = lat
        self.lng = lng

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.finished.emit(fetch_terrain_altitude_m(self.lat, self.lng))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, profile_path: str | Path = DEFAULT_PROFILE):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1220, 780)
        self.setMinimumSize(760, 520)

        self.profile = load_profile(profile_path)
        start = self.profile.start_location
        self.aviation_data = load_initial_overlay(
            start.lat,
            start.lng,
            self.profile.map.aviation_radius_km,
            self.profile.map.cache_max_age_days,
        )
        self.sitl_runner = ProcessRunner("SITL")
        self.efi_runner = ProcessRunner("EFI")
        self.rangefinder_runner = ProcessRunner("RANGEFINDER")
        self.sitl_runner.output.connect(self.log)
        self.efi_runner.output.connect(self.log)
        self.rangefinder_runner.output.connect(self.log)
        self.sitl_runner.started.connect(lambda _name: self.set_sitl_status("running"))
        self.efi_runner.started.connect(lambda _name: self.set_efi_status("running"))
        self.rangefinder_runner.started.connect(lambda _name: self.set_rangefinder_status("running"))
        self.sitl_runner.failed_to_start.connect(lambda _name: self.set_sitl_status("crashed"))
        self.efi_runner.failed_to_start.connect(lambda _name: self.set_efi_status("crashed"))
        self.rangefinder_runner.failed_to_start.connect(lambda _name: self.set_rangefinder_status("crashed"))
        self.sitl_runner.finished.connect(self.on_process_finished)
        self.efi_runner.finished.connect(self.on_process_finished)
        self.rangefinder_runner.finished.connect(self.on_process_finished)

        self.aviation_thread: QThread | None = None
        self.aviation_worker: AviationWorker | None = None
        self.terrain_thread: QThread | None = None
        self.terrain_worker: TerrainWorker | None = None
        self.wait_efi_timer = QTimer(self)
        self.wait_efi_timer.setInterval(500)
        self.wait_efi_timer.timeout.connect(self.check_telemetry_port_ready)
        self.efi_wait_ticks = 0
        self._updating_from_map = False
        self._altitude_unit = self.profile.start_location.altitude_unit

        self._build_ui()
        self.apply_profile_to_ui()
        self.update_aviation_status("cached")
        self.log(f"[APP] Loaded profile: {self.profile.path}")

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("mainSurface")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 12)
        outer.setSpacing(12)

        outer.addWidget(self._build_header())

        self.map_widget = MapWidget(self.profile, self.aviation_data)
        self.map_widget.setMinimumSize(420, 300)
        self.map_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.map_widget.location_changed.connect(self.on_map_location)

        map_card = QFrame()
        map_card.setObjectName("mapCard")
        map_layout = QVBoxLayout(map_card)
        map_layout.setContentsMargins(1, 1, 1, 1)
        map_layout.addWidget(self.map_widget)

        side_panel = self._build_side_panel()
        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(map_card)
        top_splitter.addWidget(side_panel)
        top_splitter.setStretchFactor(0, 3)
        top_splitter.setStretchFactor(1, 2)
        top_splitter.setSizes([760, 460])

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumBlockCount(2500)

        log_box = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self.log_box)

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(log_box)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setSizes([560, 220])
        outer.addWidget(main_splitter)
        self.setCentralWidget(root)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("brandBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("brandLogo")
        logo_path = Path(__file__).resolve().parent / "assets" / "betawhite.png"
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(48, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setFixedSize(54, 38)
        logo.setAlignment(Qt.AlignCenter)

        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")

        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        for button in (self.start_btn, self.stop_btn):
            button.setMinimumHeight(38)
            button.setMinimumWidth(128)
        self.start_btn.setObjectName("primaryAction")
        self.stop_btn.setObjectName("dangerAction")
        self.start_btn.clicked.connect(self.start_all_clicked)
        self.stop_btn.clicked.connect(self.stop_all)

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        return header

    def _make_collapsible(self, group: QGroupBox, expanded: bool = False) -> QWidget:
        title = group.title()
        group.setTitle("")

        container = QWidget()
        container.setObjectName("collapsibleSection")
        section_layout = QVBoxLayout(container)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)

        header = QToolButton()
        header.setObjectName("collapsibleHeader")
        header.setText(title)
        header.setCheckable(True)
        header.setChecked(expanded)
        header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        def apply_collapsed_state(checked: bool) -> None:
            header.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            group.setVisible(checked)

        header.toggled.connect(apply_collapsed_state)
        section_layout.addWidget(header)
        section_layout.addWidget(group)
        apply_collapsed_state(expanded)
        return container

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("sidePanel")
        panel.setMinimumWidth(300)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(10)

        start_box = QGroupBox("Start Location")
        start_grid = QGridLayout(start_box)
        self.location_name = QLineEdit()
        self.lat = QDoubleSpinBox()
        self.lng = QDoubleSpinBox()
        self.alt_msl = QDoubleSpinBox()
        self.heading = QDoubleSpinBox()
        self.alt_offset = QDoubleSpinBox()
        self.altitude_unit = QComboBox()
        self.altitude_unit.addItems(["m", "ft"])
        for spin in (self.lat, self.lng):
            spin.setDecimals(7)
            spin.setSingleStep(0.0001)
        self.lat.setRange(-90.0, 90.0)
        self.lng.setRange(-180.0, 180.0)
        self.configure_altitude_spinboxes("m")
        self.heading.setRange(0.0, 359.9)
        self.heading.setDecimals(1)
        self.lat.valueChanged.connect(self.on_location_spin_changed)
        self.lng.valueChanged.connect(self.on_location_spin_changed)
        self.altitude_unit.currentTextChanged.connect(self.on_altitude_unit_changed)
        terrain_btn = QPushButton("Fetch Terrain Altitude")
        terrain_btn.clicked.connect(self.fetch_terrain_clicked)
        self.terrain_btn = terrain_btn
        start_grid.addWidget(QLabel("Name"), 0, 0)
        start_grid.addWidget(self.location_name, 0, 1)
        start_grid.addWidget(QLabel("Latitude"), 1, 0)
        start_grid.addWidget(self.lat, 1, 1)
        start_grid.addWidget(QLabel("Longitude"), 2, 0)
        start_grid.addWidget(self.lng, 2, 1)
        start_grid.addWidget(QLabel("Altitude unit"), 3, 0)
        start_grid.addWidget(self.altitude_unit, 3, 1)
        start_grid.addWidget(QLabel("Home alt MSL"), 4, 0)
        start_grid.addWidget(self.alt_msl, 4, 1)
        start_grid.addWidget(QLabel("Heading, deg"), 5, 0)
        start_grid.addWidget(self.heading, 5, 1)
        start_grid.addWidget(QLabel("Alt offset"), 6, 0)
        start_grid.addWidget(self.alt_offset, 6, 1)
        start_grid.addWidget(terrain_btn, 7, 0, 1, 2)
        layout.addWidget(self._make_collapsible(start_box, expanded=True))

        profile_box = QGroupBox("Aircraft Profile")
        profile_grid = QGridLayout(profile_box)
        self.profile_path = QLineEdit()
        self.profile_path.setReadOnly(True)
        self.aircraft_label = QLabel()
        self.geometry_label = QLabel()
        self.engine_label = QLabel()
        for label in (self.aircraft_label, self.geometry_label, self.engine_label):
            label.setWordWrap(True)
        load_btn = QPushButton("Load Profile")
        load_btn.clicked.connect(self.choose_profile)
        validate_btn = QPushButton("Validate Setup")
        validate_btn.clicked.connect(self.validate_setup_clicked)
        profile_grid.addWidget(QLabel("Profile"), 0, 0)
        profile_grid.addWidget(self.profile_path, 0, 1)
        profile_grid.addWidget(load_btn, 0, 2)
        profile_grid.addWidget(self.aircraft_label, 1, 0, 1, 3)
        profile_grid.addWidget(self.geometry_label, 2, 0, 1, 3)
        profile_grid.addWidget(self.engine_label, 3, 0, 1, 3)
        profile_grid.addWidget(validate_btn, 4, 0, 1, 3)
        layout.addWidget(self._make_collapsible(profile_box, expanded=False))

        sitl_box = QGroupBox("SITL Options")
        sitl_grid = QGridLayout(sitl_box)
        self.ardupilot_root = QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_ardupilot)
        self.console_enabled = QCheckBox("Console")
        self.mavproxy_map_enabled = QCheckBox("MAVProxy map")
        self.wipe_params_enabled = QCheckBox("Reset params")
        self.docker_sitl_enabled = QCheckBox("Docker SITL")
        self.docker_sitl_enabled.toggled.connect(self.on_docker_sitl_toggled)
        self.gcs_out = QLineEdit()
        sitl_grid.addWidget(QLabel("ArduPilot root"), 0, 0)
        sitl_grid.addWidget(self.ardupilot_root, 0, 1)
        sitl_grid.addWidget(browse_btn, 0, 2)
        sitl_grid.addWidget(self.console_enabled, 1, 0)
        sitl_grid.addWidget(self.mavproxy_map_enabled, 1, 1)
        sitl_grid.addWidget(self.wipe_params_enabled, 1, 2)
        sitl_grid.addWidget(self.docker_sitl_enabled, 2, 0)
        sitl_grid.addWidget(QLabel("GCS out"), 3, 0)
        sitl_grid.addWidget(self.gcs_out, 3, 1, 1, 2)
        layout.addWidget(self._make_collapsible(sitl_box, expanded=False))

        efi_box = QGroupBox("EFI Options")
        efi_grid = QGridLayout(efi_box)
        self.efi_enabled = QCheckBox("EFI injector")
        self.efi_connect = QLineEdit()
        self.telemetry_gcs_out = QLineEdit()
        self.efi_rate = QSpinBox()
        self.efi_print_rate = QSpinBox()
        self.efi_rate.setRange(1, 100)
        self.efi_print_rate.setRange(1, 20)
        efi_grid.addWidget(self.efi_enabled, 0, 0, 1, 2)
        efi_grid.addWidget(QLabel("Connect"), 1, 0)
        efi_grid.addWidget(self.efi_connect, 1, 1)
        efi_grid.addWidget(QLabel("QGC mirror"), 2, 0)
        efi_grid.addWidget(self.telemetry_gcs_out, 2, 1)
        efi_grid.addWidget(QLabel("Rate Hz"), 3, 0)
        efi_grid.addWidget(self.efi_rate, 3, 1)
        efi_grid.addWidget(QLabel("Print Hz"), 4, 0)
        efi_grid.addWidget(self.efi_print_rate, 4, 1)
        layout.addWidget(self._make_collapsible(efi_box, expanded=False))

        rangefinder_box = QGroupBox("Rangefinder Options")
        rangefinder_grid = QGridLayout(rangefinder_box)
        self.rangefinder_enabled = QCheckBox("Terrain rangefinder")
        self.rangefinder_rate = QSpinBox()
        self.rangefinder_print_rate = QSpinBox()
        self.rangefinder_min_cm = QSpinBox()
        self.rangefinder_max_cm = QSpinBox()
        self.rangefinder_rate.setRange(1, 100)
        self.rangefinder_print_rate.setRange(1, 20)
        self.rangefinder_min_cm.setRange(1, 10000)
        self.rangefinder_max_cm.setRange(1, 100000)
        rangefinder_grid.addWidget(self.rangefinder_enabled, 0, 0, 1, 2)
        rangefinder_grid.addWidget(QLabel("Rate Hz"), 1, 0)
        rangefinder_grid.addWidget(self.rangefinder_rate, 1, 1)
        rangefinder_grid.addWidget(QLabel("Print Hz"), 2, 0)
        rangefinder_grid.addWidget(self.rangefinder_print_rate, 2, 1)
        rangefinder_grid.addWidget(QLabel("Min cm"), 3, 0)
        rangefinder_grid.addWidget(self.rangefinder_min_cm, 3, 1)
        rangefinder_grid.addWidget(QLabel("Max cm"), 4, 0)
        rangefinder_grid.addWidget(self.rangefinder_max_cm, 4, 1)
        layout.addWidget(self._make_collapsible(rangefinder_box, expanded=False))

        aviation_box = QGroupBox("Aviation Overlay")
        aviation_layout = QVBoxLayout(aviation_box)
        self.aviation_status = QLabel("cached")
        self.refresh_aviation_btn = QPushButton("Refresh Aviation Overlay")
        self.refresh_aviation_btn.clicked.connect(self.refresh_aviation_overlay)
        aviation_layout.addWidget(self.aviation_status)
        aviation_layout.addWidget(self.refresh_aviation_btn)
        layout.addWidget(self._make_collapsible(aviation_box, expanded=False))

        status_box = QGroupBox("Process Status")
        status_grid = QGridLayout(status_box)
        self.sitl_status = QLabel("stopped")
        self.efi_status = QLabel("stopped")
        self.rangefinder_status = QLabel("stopped")
        for label in (self.sitl_status, self.efi_status, self.rangefinder_status):
            label.setObjectName("statusPill")
        status_grid.addWidget(QLabel("SITL"), 0, 0)
        status_grid.addWidget(self.sitl_status, 0, 1)
        status_grid.addWidget(QLabel("EFI"), 1, 0)
        status_grid.addWidget(self.efi_status, 1, 1)
        status_grid.addWidget(QLabel("Rangefinder"), 2, 0)
        status_grid.addWidget(self.rangefinder_status, 2, 1)
        layout.addWidget(self._make_collapsible(status_box, expanded=False))
        self.set_sitl_status("stopped")
        self.set_efi_status("stopped")
        self.set_rangefinder_status("stopped")

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(380)
        scroll.setMaximumWidth(560)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        return scroll

    def apply_profile_to_ui(self) -> None:
        p = self.profile
        self.profile_path.setText(str(p.path))
        self.aircraft_label.setText(f"{p.aircraft.name} | {p.aircraft.vehicle} | {p.aircraft.frame}")
        self.geometry_label.setText(
            f"{p.geometry.weight_kg:g} kg, wing {p.geometry.wing_area_m2:g} m2, cruise {p.geometry.cruise_speed_mps:g} m/s"
        )
        self.engine_label.setText(f"{p.engine.name}, {p.engine.propeller_inch} inch prop")
        self.location_name.setText(p.start_location.name)
        self.lat.setValue(p.start_location.lat)
        self.lng.setValue(p.start_location.lng)
        self.set_altitude_unit(p.start_location.altitude_unit, convert_current=False)
        self.alt_msl.setValue(altitude_to_unit(p.start_location.alt_msl_m, self._altitude_unit))
        self.heading.setValue(p.start_location.heading_deg)
        self.alt_offset.setValue(altitude_to_unit(p.start_location.alt_offset_m, self._altitude_unit))
        self.ardupilot_root.setText(str(p.paths.ardupilot_root))
        self.console_enabled.setChecked(True)
        self.mavproxy_map_enabled.setChecked(True)
        self.wipe_params_enabled.setChecked(False)
        self.docker_sitl_enabled.setChecked(False)
        self.gcs_out.setText(p.network.gcs_out)
        self.efi_enabled.setChecked(p.engine.efi_enabled)
        self.efi_connect.setText(p.network.efi_connect)
        self.telemetry_gcs_out.setText(p.network.telemetry_gcs_out)
        self.efi_rate.setValue(p.efi.rate_hz)
        self.efi_print_rate.setValue(p.efi.print_rate_hz)
        self.rangefinder_enabled.setChecked(p.rangefinder.enabled)
        self.rangefinder_rate.setValue(p.rangefinder.rate_hz)
        self.rangefinder_print_rate.setValue(p.rangefinder.print_rate_hz)
        self.rangefinder_min_cm.setValue(p.rangefinder.min_cm)
        self.rangefinder_max_cm.setValue(p.rangefinder.max_cm)
        self.map_widget.set_marker(p.start_location.lat, p.start_location.lng)
        self.map_widget.set_altitude_unit(self._altitude_unit)

    def update_profile_from_ui(self) -> None:
        p = self.profile
        p.paths.ardupilot_root = find_ardupilot_root(self.ardupilot_root.text())
        p.network.gcs_out = self.gcs_out.text().strip()
        p.network.efi_connect = self.efi_connect.text().strip()
        p.network.telemetry_gcs_out = self.telemetry_gcs_out.text().strip()
        p.engine.efi_enabled = self.efi_enabled.isChecked()
        p.rangefinder.enabled = self.rangefinder_enabled.isChecked()
        p.start_location.name = self.location_name.text().strip() or "GUI_OMNI"
        p.start_location.lat = self.lat.value()
        p.start_location.lng = self.lng.value()
        p.start_location.alt_msl_m = altitude_to_meters(self.alt_msl.value(), self._altitude_unit)
        p.start_location.heading_deg = self.heading.value()
        p.start_location.alt_offset_m = altitude_to_meters(self.alt_offset.value(), self._altitude_unit)
        p.start_location.altitude_unit = self._altitude_unit
        p.efi.rate_hz = self.efi_rate.value()
        p.efi.print_rate_hz = self.efi_print_rate.value()
        p.rangefinder.rate_hz = self.rangefinder_rate.value()
        p.rangefinder.print_rate_hz = self.rangefinder_print_rate.value()
        p.rangefinder.min_cm = self.rangefinder_min_cm.value()
        p.rangefinder.max_cm = self.rangefinder_max_cm.value()

    def choose_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load launcher profile", str(self.profile.path.parent), "YAML (*.yaml *.yml)")
        if not path:
            return
        try:
            self.profile = load_profile(path)
            start = self.profile.start_location
            self.aviation_data = load_initial_overlay(start.lat, start.lng, self.profile.map.aviation_radius_km, self.profile.map.cache_max_age_days)
            self.map_widget.reload(self.profile, self.aviation_data)
            self.apply_profile_to_ui()
            self.update_aviation_status("cached")
            self.log(f"[APP] Loaded profile: {path}")
        except ProfileError as exc:
            QMessageBox.critical(self, "Invalid profile", str(exc))

    def browse_ardupilot(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select ArduPilot root", self.ardupilot_root.text())
        if path:
            self.ardupilot_root.setText(path)

    def on_docker_sitl_toggled(self, enabled: bool) -> None:
        if enabled:
            self.mavproxy_map_enabled.setChecked(False)

    def validate_setup_clicked(self) -> bool:
        self.update_profile_from_ui()
        if self.docker_sitl_enabled.isChecked():
            result = validate_docker_setup(self.profile, self.efi_enabled.isChecked())
        else:
            result = validate_setup(self.profile, self.efi_enabled.isChecked())
        self.log("[VALIDATION]\n" + result.summary())
        if result.ok:
            QMessageBox.information(self, "Validation passed", result.summary())
        else:
            QMessageBox.warning(self, "Validation found problems", result.summary())
        return result.ok

    def on_location_spin_changed(self) -> None:
        if self._updating_from_map:
            return
        self.map_widget.set_marker(self.lat.value(), self.lng.value())

    def on_map_location(self, lat: float, lng: float) -> None:
        self._updating_from_map = True
        self.lat.setValue(lat)
        self.lng.setValue(lng)
        self._updating_from_map = False

    def configure_altitude_spinboxes(self, unit: str) -> None:
        if unit == "ft":
            self.alt_msl.setRange(altitude_to_unit(-500.0, "ft"), altitude_to_unit(12000.0, "ft"))
            self.alt_offset.setRange(altitude_to_unit(-1000.0, "ft"), altitude_to_unit(3000.0, "ft"))
            self.alt_msl.setDecimals(1)
            self.alt_offset.setDecimals(1)
            self.alt_msl.setSingleStep(10.0)
            self.alt_offset.setSingleStep(10.0)
        else:
            self.alt_msl.setRange(-500.0, 12000.0)
            self.alt_offset.setRange(-1000.0, 3000.0)
            self.alt_msl.setDecimals(2)
            self.alt_offset.setDecimals(1)
            self.alt_msl.setSingleStep(1.0)
            self.alt_offset.setSingleStep(1.0)
        self.alt_msl.setSuffix(f" {unit}")
        self.alt_offset.setSuffix(f" {unit}")

    def set_altitude_unit(self, unit: str, convert_current: bool = True) -> None:
        unit = "ft" if unit == "ft" else "m"
        if convert_current and unit == self._altitude_unit:
            return
        alt_m = altitude_to_meters(self.alt_msl.value(), self._altitude_unit) if convert_current else 0.0
        offset_m = altitude_to_meters(self.alt_offset.value(), self._altitude_unit) if convert_current else 0.0
        previous = self.altitude_unit.blockSignals(True)
        self.altitude_unit.setCurrentText(unit)
        self.altitude_unit.blockSignals(previous)
        self._altitude_unit = unit
        self.configure_altitude_spinboxes(unit)
        self.map_widget.set_altitude_unit(unit)
        if convert_current:
            self.alt_msl.setValue(altitude_to_unit(alt_m, unit))
            self.alt_offset.setValue(altitude_to_unit(offset_m, unit))

    def on_altitude_unit_changed(self, unit: str) -> None:
        self.set_altitude_unit(unit, convert_current=True)

    def fetch_terrain_clicked(self) -> None:
        if self.terrain_thread and self.terrain_thread.isRunning():
            self.log("[TERRAIN] Lookup already running.")
            return
        self.terrain_btn.setEnabled(False)
        self.statusBar().showMessage("Fetching terrain altitude...")
        self.terrain_thread = QThread(self)
        self.terrain_worker = TerrainWorker(self.lat.value(), self.lng.value())
        self.terrain_worker.moveToThread(self.terrain_thread)
        self.terrain_thread.started.connect(self.terrain_worker.run)
        self.terrain_worker.finished.connect(self.on_terrain_finished)
        self.terrain_worker.failed.connect(self.on_terrain_failed)
        self.terrain_worker.finished.connect(self.terrain_thread.quit)
        self.terrain_worker.failed.connect(self.terrain_thread.quit)
        self.terrain_worker.finished.connect(self.terrain_worker.deleteLater)
        self.terrain_worker.failed.connect(self.terrain_worker.deleteLater)
        self.terrain_thread.finished.connect(self.terrain_thread.deleteLater)
        self.terrain_thread.start()

    def on_terrain_finished(self, terrain_m: float) -> None:
        offset_m = altitude_to_meters(self.alt_offset.value(), self._altitude_unit)
        msl_m = terrain_m + offset_m
        self.alt_msl.setValue(altitude_to_unit(msl_m, self._altitude_unit))
        offset_display = altitude_to_unit(offset_m, self._altitude_unit)
        msl_display = altitude_to_unit(msl_m, self._altitude_unit)
        self.log(
            f"[TERRAIN] elevation={terrain_m:.1f} m, offset={offset_display:.1f} {self._altitude_unit}, "
            f"home={msl_display:.1f} {self._altitude_unit} MSL"
        )
        self.statusBar().showMessage("Terrain altitude updated.")
        self.terrain_btn.setEnabled(True)
        self.terrain_thread = None
        self.terrain_worker = None

    def on_terrain_failed(self, error: str) -> None:
        self.log(f"[TERRAIN] ERROR: {error}")
        self.statusBar().showMessage("Terrain lookup failed. Enter altitude manually.")
        self.terrain_btn.setEnabled(True)
        self.terrain_thread = None
        self.terrain_worker = None
        QMessageBox.warning(self, "Terrain lookup failed", f"Could not fetch terrain altitude.\n\nManual altitude entry is still available.\n\n{error}")

    def refresh_aviation_overlay(self) -> None:
        if self.aviation_thread and self.aviation_thread.isRunning():
            self.log("[AVIATION] Refresh already running.")
            return
        self.update_profile_from_ui()
        self.update_aviation_status("updating")
        self.refresh_aviation_btn.setEnabled(False)
        self.aviation_thread = QThread(self)
        self.aviation_worker = AviationWorker(
            self.lat.value(),
            self.lng.value(),
            self.profile.map.aviation_radius_km,
            self.profile.map.cache_max_age_days,
        )
        self.aviation_worker.moveToThread(self.aviation_thread)
        self.aviation_thread.started.connect(self.aviation_worker.run)
        self.aviation_worker.progress.connect(lambda text: self.log(f"[AVIATION] {text}"))
        self.aviation_worker.finished.connect(self.on_aviation_finished)
        self.aviation_worker.finished.connect(self.aviation_thread.quit)
        self.aviation_worker.finished.connect(self.aviation_worker.deleteLater)
        self.aviation_thread.finished.connect(self.aviation_thread.deleteLater)
        self.aviation_thread.start()

    def on_aviation_finished(self, data: dict[str, Any]) -> None:
        self.aviation_data = data
        self.map_widget.reload(self.profile, data)
        self.map_widget.set_marker(self.lat.value(), self.lng.value())
        self.map_widget.set_altitude_unit(self._altitude_unit)
        stats = data.get("stats", {})
        self.log(f"[AVIATION] Overlay ready. airports={stats.get('airports_kept', len(data.get('airports', [])))}, navaids={stats.get('navaids_kept', len(data.get('navaids', [])))}")
        if data.get("warnings"):
            self.update_aviation_status("failed" if data.get("source") == "Fallback marker" else "updated")
            for warning in data["warnings"]:
                self.log(f"[AVIATION] WARNING: {warning}")
        else:
            self.update_aviation_status("updated")
        self.refresh_aviation_btn.setEnabled(True)
        self.aviation_thread = None
        self.aviation_worker = None

    def start_sitl_clicked(self) -> None:
        self.start_sitl(start_support_after_ready=False)

    def start_all_clicked(self) -> None:
        self.start_sitl(start_support_after_ready=self.efi_enabled.isChecked() or self.rangefinder_enabled.isChecked())

    def start_sitl(self, start_support_after_ready: bool) -> None:
        self.update_profile_from_ui()
        docker_mode = self.docker_sitl_enabled.isChecked()
        if docker_mode:
            result = validate_docker_setup(self.profile, self.efi_enabled.isChecked() and start_support_after_ready)
        else:
            result = validate_setup(self.profile, self.efi_enabled.isChecked() and start_support_after_ready)
        if not result.ok:
            self.log("[VALIDATION]\n" + result.summary())
            QMessageBox.warning(self, "Cannot start SITL", result.summary())
            return
        if docker_mode:
            line = (
                f"{self.profile.start_location.name}={self.lat.value():.7f},"
                f"{self.lng.value():.7f},{self.profile.start_location.alt_msl_m:.2f},{self.heading.value():.1f}"
            )
        else:
            try:
                line = write_location(
                    self.profile.paths.ardupilot_root,
                    self.profile.start_location.name,
                    self.lat.value(),
                    self.lng.value(),
                    self.profile.start_location.alt_msl_m,
                    self.heading.value(),
                )
            except Exception as exc:
                QMessageBox.critical(self, "Cannot write start location", str(exc))
                return
        self.log_box.clear()
        if docker_mode:
            self.log(f"[APP] Passing Docker start location: {line}")
        else:
            self.log(f"[APP] Wrote start location: {line}")
        self.set_sitl_status("starting")
        if docker_mode:
            cmd, cwd = build_docker_sitl_command(
                self.profile,
                self.console_enabled.isChecked(),
                self.mavproxy_map_enabled.isChecked(),
                self.gcs_out.text(),
                self.wipe_params_enabled.isChecked(),
            )
        else:
            cmd, cwd = build_sitl_command(
                self.profile,
                self.console_enabled.isChecked(),
                self.mavproxy_map_enabled.isChecked(),
                self.gcs_out.text(),
                self.wipe_params_enabled.isChecked(),
            )
        if not self.sitl_runner.start(cmd, cwd):
            self.set_sitl_status("crashed")
            return
        if start_support_after_ready:
            if self.efi_enabled.isChecked():
                self.set_efi_status("waiting")
            if self.rangefinder_enabled.isChecked():
                self.set_rangefinder_status("waiting")
            self.efi_wait_ticks = 0
            self.wait_efi_timer.start()

    def start_efi_clicked(self) -> None:
        self.start_efi()

    def start_efi(self) -> None:
        self.update_profile_from_ui()
        if self.docker_sitl_enabled.isChecked():
            result = validate_docker_setup(self.profile, True)
        else:
            result = validate_setup(self.profile, True)
        if not result.ok:
            self.log("[VALIDATION]\n" + result.summary())
            QMessageBox.warning(self, "Cannot start EFI", result.summary())
            return
        self.set_efi_status("starting")
        cmd, cwd = build_efi_command(
            self.profile,
            self.efi_connect.text(),
            self.telemetry_gcs_out.text(),
            self.efi_rate.value(),
            self.efi_print_rate.value(),
        )
        if not self.efi_runner.start(cmd, cwd):
            self.set_efi_status("crashed")

    def start_rangefinder_clicked(self) -> None:
        self.start_rangefinder()

    def start_rangefinder(self) -> None:
        self.update_profile_from_ui()
        if self.docker_sitl_enabled.isChecked():
            result = validate_docker_setup(self.profile, self.efi_enabled.isChecked())
        else:
            result = validate_setup(self.profile, self.efi_enabled.isChecked())
        if not result.ok:
            self.log("[VALIDATION]\n" + result.summary())
            QMessageBox.warning(self, "Cannot start rangefinder", result.summary())
            return
        self.set_rangefinder_status("starting")
        cmd, cwd = build_rangefinder_command(
            self.profile,
            self.efi_connect.text(),
            self.telemetry_gcs_out.text(),
            self.rangefinder_rate.value(),
            self.rangefinder_print_rate.value(),
            self.rangefinder_min_cm.value(),
            self.rangefinder_max_cm.value(),
            self.profile.rangefinder.sensor_id,
        )
        if not self.rangefinder_runner.start(cmd, cwd):
            self.set_rangefinder_status("crashed")

    def check_telemetry_port_ready(self) -> None:
        self.efi_wait_ticks += 1
        endpoint = parse_tcp_endpoint(self.efi_connect.text())
        if endpoint is None:
            self.wait_efi_timer.stop()
            self.set_efi_status("crashed")
            self.set_rangefinder_status("crashed")
            QMessageBox.warning(self, "Invalid EFI connection", "EFI connection must look like tcp:127.0.0.1:5762")
            return
        if is_tcp_port_open(endpoint):
            self.wait_efi_timer.stop()
            self.log(f"[TELEMETRY] TCP port ready: {endpoint.host}:{endpoint.port}")
            if self.efi_enabled.isChecked():
                self.start_efi()
            if self.rangefinder_enabled.isChecked():
                self.start_rangefinder()
            return
        if self.efi_wait_ticks >= 120:
            self.wait_efi_timer.stop()
            self.set_efi_status("crashed")
            self.set_rangefinder_status("crashed")
            self.log(f"[EFI] Timed out waiting for TCP port {endpoint.host}:{endpoint.port}. SITL is still running.")
            QMessageBox.warning(self, "Telemetry not started", "Timed out waiting for SITL telemetry TCP port. SITL is still running.")

    def stop_all(self) -> None:
        self.wait_efi_timer.stop()
        self.set_efi_status("stopped")
        self.set_rangefinder_status("stopped")
        self.set_sitl_status("stopped")
        self.rangefinder_runner.stop()
        self.efi_runner.stop()
        self.sitl_runner.stop()
        try:
            subprocess.run(
                ["bash", "-lc", "pkill -f arduplane || true; pkill -f sim_vehicle.py || true"],
                check=False,
            )
            subprocess.run(
                ["bash", "-lc", "docker rm -f omnitrainer-sitl >/dev/null 2>&1 || true"],
                check=False,
            )
        except Exception:
            pass
        self.statusBar().showMessage("Stopped launched processes.")

    def on_process_finished(self, name: str, exit_code: int) -> None:
        if name == "SITL":
            self.set_sitl_status("stopped" if exit_code == 0 else "crashed")
        elif name == "EFI":
            self.set_efi_status("stopped" if exit_code == 0 else "crashed")
        elif name == "RANGEFINDER":
            self.set_rangefinder_status("stopped" if exit_code == 0 else "crashed")

    def set_sitl_status(self, status: str) -> None:
        self._set_process_status(self.sitl_status, status)

    def set_efi_status(self, status: str) -> None:
        self._set_process_status(self.efi_status, status)

    def set_rangefinder_status(self, status: str) -> None:
        self._set_process_status(self.rangefinder_status, status)

    def _set_process_status(self, label: QLabel, status: str) -> None:
        label.setText(status.upper())
        if status in {"running", "starting", "waiting"}:
            state = "ok"
        elif status == "crashed":
            state = "error"
        else:
            state = "idle"
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    def update_aviation_status(self, status: str) -> None:
        self.aviation_status.setText(status)

    def log(self, text: str) -> None:
        self.log_box.appendPlainText(text.rstrip())

    def closeEvent(self, event) -> None:
        if self.aviation_worker is not None:
            self.aviation_worker.cancelled = True
        self.stop_all()
        event.accept()


def run_app(profile_path: str | Path = DEFAULT_PROFILE) -> int:
    import sys

    app = QApplication(sys.argv)
    apply_styles(app)
    window = MainWindow(profile_path)
    window.show()
    return app.exec_()
