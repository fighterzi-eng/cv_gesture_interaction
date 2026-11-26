"""Developer settings dialog: live camera + test window + collapsible parameter sections."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from params import DEFAULTS, save_parameters
from widgets import (CameraView, CollapsibleSection, DialogWindow, TestWindow, Toggle, make_spin)

# (group, key, label, type, ...)  type: bool | int lo hi step | float lo hi step dec | choice [options]
# ("#", "Title") is a sub heading.
SECTIONS = [
    ("Camera", True, [
        ("camera", "index", "Camera index (VideoCapture)", "int", 0, 10, 1),
        ("camera", "auto_white_balance", "Auto white balance (AUTO_WB)", "bool"),
        ("camera", "auto_exposure", "Auto exposure (AUTO_EXPOSURE)", "bool"),
    ]),
    ("Camera view display (GUI only)", True, [
        ("camera", "show_fps", "Show FPS", "bool"),
        ("camera", "show_landmarks", "Show points: centroid, fingertips, valleys", "bool"),
        ("camera", "show_hand_box", "Show hand outline and hull lines", "bool"),
        ("@", "test"),                                   # 'Show test window' button
    ]),
    ("Hand detection (classic_detector.py)", False, [
        ("#", "Preprocessing"),
        ("tracking", "blur_kernel", "Blur size (GaussianBlur)", "int", 1, 31, 2),
        ("tracking", "motion_history", "Motion history (MOG2 history)", "int", 1, 5000, 10),
        ("tracking", "motion_var_threshold", "Motion sensitivity (MOG2 varThreshold)", "int", 1, 255, 1),
        ("#", "Mask clean-up"),
        ("tracking", "seed_dilate", "Motion dilate (SEED_DILATE)", "int", 1, 31, 1),
        ("tracking", "skin_close", "Skin close (SKIN_CLOSE)", "int", 1, 31, 1),
        ("tracking", "join_k", "Join gaps (JOIN_K)", "int", 1, 31, 1),
        ("tracking", "outline_sigma", "Outline smoothing (OUTLINE_SIGMA)", "int", 1, 20, 1),
        ("tracking", "min_area", "Smallest hand size, px² (MIN_AREA)", "int", 0, 100000, 50),
    ]),
    ("Skin detection (skinDetect.py)", False, [
        ("skin", "rebuild_interval", "Rebuild every N frames (rebuild_interval)", "int", 1, 1000, 10),
        ("skin", "coverage", "Skin coverage (coverage)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "cov_min", "Coverage min (cov_min)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "cov_max", "Coverage max (cov_max)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "step", "Coverage step (step)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "frac_lo", "Skin fraction low (frac_lo)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "frac_hi", "Skin fraction high (frac_hi)", "float", 0.0, 1.0, 0.01, 2),
        ("skin", "pct_lo", "Brightness percentile low (pct_lo)", "int", 0, 100, 1),
        ("skin", "pct_hi", "Brightness percentile high (pct_hi)", "int", 0, 100, 1),
    ]),
]
LIVE_OPTIONS = {("camera", "show_fps"), ("camera", "show_landmarks"), ("camera", "show_hand_box")}


class DeveloperSettingsDialog(DialogWindow):
    applied = Signal(dict)
    W, H = 1400, 690
    MIN = (940, 500)

    def __init__(self, params):
        super().__init__()
        self._params = params
        self._w = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("panel")
        outer.addWidget(panel)
        h = QHBoxLayout(panel)
        h.setContentsMargins(14, 14, 24, 20)
        h.setSpacing(14)

        self.view = CameraView(radius=12, scale=1.1)
        self.view.setMinimumWidth(360)
        self.test = TestWindow()
        self.test.hide()
        self.test.closed.connect(self._test_closed)
        h.addWidget(self.view, 1)
        sep = QFrame()
        sep.setObjectName("vline")
        sep.setFixedWidth(1)
        h.addWidget(sep)

        right = QVBoxLayout()
        right.setSpacing(10)
        title = QLabel("Developer settings")
        title.setObjectName("devTitle")
        right.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setAutoFillBackground(False)
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 8, 0)
        bv.setSpacing(8)
        for name, expanded, fields in SECTIONS:
            bv.addWidget(self._section(name, expanded, fields))
        bv.addStretch()
        scroll.setWidget(body)
        right.addWidget(scroll, 1)

        foot = QHBoxLayout()
        foot.setSpacing(14)
        foot.addStretch()
        for text, name, slot in (("Reset", "pill", self._reset), ("Close", "pill", self.close),
                                 ("Apply", "primary", self._apply)):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            foot.addWidget(b)
        right.addLayout(foot)
        rw = QWidget()
        rw.setFixedWidth(500)
        rw.setLayout(right)
        right.setContentsMargins(10, 0, 0, 0)
        h.addWidget(rw)
        self._load()

    # ---------------------------------------------------------------- build
    def _section(self, name, expanded, fields):
        sec = CollapsibleSection(name, expanded)
        for f in fields:
            if f[0] == "#":
                sec.add_sub(f[1])
                continue
            if f[0] == "@":
                self.btn_test = QPushButton("Show test window")
                self.btn_test.setObjectName("outlineBtn")
                self.btn_test.setCursor(Qt.PointingHandCursor)
                self.btn_test.clicked.connect(self._toggle_test)
                row = QHBoxLayout()
                row.addStretch()
                row.addWidget(self.btn_test)
                sec.form.addLayout(row)
                continue
            group, key, label, kind = f[:4]
            if kind == "bool":
                w = Toggle()
            elif kind == "choice":
                w = QComboBox()
                w.setObjectName("plainCombo")
                w.addItems(f[4])
                w.setFixedSize(120, 30)
            else:
                w = make_spin(kind, *f[4:])
            self._w[(group, key)] = w
            if (group, key) in LIVE_OPTIONS:
                w.toggled.connect(lambda _=None: self._preview_options())
            sec.add_row(label, w)
        return sec

    # ---------------------------------------------------------------- values
    def _load(self):
        for (g, k), w in self._w.items():
            v = self._params[g][k]
            if isinstance(w, Toggle):
                w.setChecked(bool(v))
            elif isinstance(w, QComboBox):
                w.setCurrentText(str(v))
            else:
                w.setValue(v)

    def _collect(self):
        for (g, k), w in self._w.items():
            if isinstance(w, Toggle):
                v = w.isChecked()
            elif isinstance(w, QComboBox):
                v = w.currentText()
            else:
                v = w.value()
            self._params[g][k] = v

    def _preview_options(self):
        g = lambda a, b: self._w[(a, b)].isChecked()
        self.view.set_options(g("camera", "show_fps"), g("camera", "show_landmarks"),
                              g("camera", "show_hand_box"))

    def open_dialog(self):
        self._load()
        self._preview_options()
        self.show_centered()

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.test.isVisible():          # test window follows the developer dialog
            self.test.close()

    # ---------------------------------------------------------------- test window
    def _toggle_test(self):
        if self.test.isVisible():
            self.test.hide()
            self._test_closed()
        else:
            if not self.test.isVisible() and not getattr(self, "_test_placed", False):
                self._test_placed = True
                self.test.move(self.x() + 40, self.y() + self.height() - self.test.height() - 40)
            self.test.show()
            self.test.raise_()                 # opens above the dialog; later clicks reorder them normally
            self.test.activateWindow()
            self.btn_test.setText("Hide test window")

    def _test_closed(self):
        self.btn_test.setText("Show test window")

    # ---------------------------------------------------------------- apply / reset
    def _apply(self):
        self._collect()
        save_parameters(self._params)
        self.applied.emit(self._params)

    def _reset(self):
        for g in ("camera", "tracking", "skin"):
            self._params[g] = copy.deepcopy(DEFAULTS[g])
        self._load()
        save_parameters(self._params)       # defaults written to the json straight away
        self.applied.emit(self._params)
