"""User settings dialog: Applications / Video player tabs."""
from __future__ import annotations

import copy
import os
from functools import partial

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from Src.params import DEFAULTS, GESTURES, save_parameters
from Gui.widgets import (DialogWindow, GestureCombo, KeyCaptureButton, Toggle, app_pixmap)
from PySide6.QtGui import QIcon

COL1, COL2 = 210, 230


def _line(name):
    f = QFrame()
    f.setObjectName(name)
    f.setFixedHeight(1)
    return f


class UserSettingsDialog(DialogWindow):
    applied = Signal(dict)
    modeChanged = Signal(str)
    W, H = 880, 740
    MIN = (760, 520)

    TOGGLES = [("show_confirmation", "Show gesture confirmation message"),
               ("show_gesture_map", "Show gesture map"),
               ("hide_camera", "Hide camera"),
               ("lock_windows", "Lock windows in place")]

    def __init__(self, params):
        super().__init__()
        self._params = params
        self._mode = "applications"
        self._toggles = {}
        self._load_working()
        self._build()
        self._rebuild()

    # ---------------------------------------------------------------- model
    def _load_working(self):
        p = self._params
        self._general = dict(p["general"])
        self._apps = copy.deepcopy(p["applications"])
        self._video = copy.deepcopy(p["video_player"])

    def _items(self):
        return self._apps if self._mode == "applications" else self._video

    def open_dialog(self):
        """Discard unsaved edits, reload from params, show."""
        self._load_working()
        self._sync_toggles()
        self._rebuild()
        self.show_centered()

    def _sync_toggles(self):
        for k, t in self._toggles.items():
            t.setChecked(self._general[k])

    # ---------------------------------------------------------------- build
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("panel")
        outer.addWidget(panel)
        v = QVBoxLayout(panel)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(14)
        t = QLabel("User settings")
        t.setObjectName("title")
        head.addWidget(t)
        head.addSpacing(30)
        grp = QButtonGroup(self)
        self.tab_apps = QPushButton("Applications")
        self.tab_video = QPushButton("Video player")
        for b, m in ((self.tab_apps, "applications"), (self.tab_video, "video_player")):
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            grp.addButton(b)
            b.clicked.connect(partial(self._set_mode, m))
            head.addWidget(b)
        self.tab_apps.setChecked(True)
        head.addStretch()
        v.addLayout(head)
        v.addSpacing(8)

        for key, text in self.TOGGLES:
            h = QHBoxLayout()
            h.setContentsMargins(0, 2, 16, 2)
            lab = QLabel(text)
            lab.setObjectName("settingLabel")
            tg = Toggle(self._general[key])
            tg.toggled.connect(lambda on, k=key: self._general.__setitem__(k, on))
            self._toggles[key] = tg
            h.addWidget(lab, 1)
            h.addWidget(tg)
            v.addLayout(h)

        self.note = QLabel()
        self.note.setObjectName("note")
        v.addWidget(self.note)
        n2 = QLabel("Lock off: drag the menu, camera preview or confirmation message to move them.")
        n2.setObjectName("note")
        v.addWidget(n2)
        v.addSpacing(4)
        v.addWidget(_line("hline"))

        hh = QHBoxLayout()
        hh.setContentsMargins(14, 4, 12, 0)
        hh.setSpacing(0)
        self.h1, self.h2, self.h3 = QLabel(), QLabel(), QLabel()
        for l in (self.h1, self.h2, self.h3):
            l.setObjectName("colHead")
        self.h1.setFixedWidth(COL1)
        self.h2.setFixedWidth(COL2)
        hh.addWidget(self.h1)
        hh.addWidget(self.h2)
        hh.addWidget(self.h3, 1)
        v.addLayout(hh)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.rows = QWidget()
        self.rows.setAutoFillBackground(False)
        self.rv = QVBoxLayout(self.rows)
        self.rv.setContentsMargins(0, 0, 6, 0)
        self.rv.setSpacing(8)
        self.scroll.setWidget(self.rows)
        v.addWidget(self.scroll, 1)

        foot = QHBoxLayout()
        foot.setSpacing(14)
        n = QLabel("Changes take effect after Apply")
        n.setObjectName("note")
        foot.addWidget(n)
        foot.addStretch()
        for text, name, slot in (("Reset", "pill", self._reset), ("Close", "pill", self.close),
                                 ("Apply", "primary", self._apply)):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            foot.addWidget(b)
        v.addLayout(foot)

    # ---------------------------------------------------------------- rows
    def _set_mode(self, mode):
        self._mode = mode
        self._rebuild()
        self.modeChanged.emit(mode)

    def _rebuild(self):
        apps = self._mode == "applications"
        self.note.setText("Applications mode: opens the program.  Video player mode: sends a key shortcut.")
        self.h1.setText("GESTURE")
        self.h2.setText("APP" if apps else "KEY SHORTCUT")
        self.h3.setText("NAME" if apps else "ACTION")
        while self.rv.count():
            w = self.rv.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = self._items()
        for i in range(len(items)):
            self.rv.addWidget(self._make_row(i))
        used = {x["gesture"] for x in items}
        for _ in range(min(2, len(GESTURES) - len(used))):
            self.rv.addWidget(self._make_row(None))
        self.rv.addStretch()

    @staticmethod
    def _cell(widget, width):
        c = QWidget()
        c.setFixedWidth(width)
        h = QHBoxLayout(c)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(widget, 0, Qt.AlignLeft | Qt.AlignVCenter)
        return c

    def _make_row(self, idx):
        items = self._items()
        it = items[idx] if idx is not None else None
        apps = self._mode == "applications"
        f = QFrame()
        f.setObjectName("row")
        f.setFixedHeight(52)
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 0, 10, 0)
        h.setSpacing(0)

        combo = GestureCombo(it["gesture"] if it else None,
                             lambda: {x["gesture"] for x in self._items()})
        combo.setProperty("slot", "filled" if it else "empty")
        combo.setFixedSize(COL1 - 10 if it else 186, 38)
        if it:
            combo.setIconSize(QSize(34, 34))
        combo.gestureChosen.connect(partial(self._on_gesture, idx))
        h.addWidget(self._cell(combo, COL1))

        if apps:
            b = QPushButton()
            b.setObjectName("appBtn")
            b.setCursor(Qt.PointingHandCursor)
            if it:
                b.setProperty("empty", "false")
                b.setIcon(QIcon(app_pixmap(it["name"], it["path"], 30)))
                b.setIconSize(QSize(30, 30))
                b.setToolTip(it["path"] or "Click to choose the program")
            else:
                b.setProperty("empty", "true")
                b.setText("Choose app")
                b.setFixedWidth(186)
                b.setEnabled(False)
            b.clicked.connect(partial(self._choose_app, idx))
            h.addWidget(self._cell(b, COL2))
        else:
            if it:
                k = KeyCaptureButton(it["key"])
                k.changed.connect(lambda t, i=idx: items[i].__setitem__("key", t))
                h.addWidget(self._cell(k, COL2))
            else:
                h.addWidget(self._cell(QLabel(""), COL2))

        field = "name" if apps else "action"
        e = QLineEdit(it[field] if it else "")
        e.setObjectName("cell")
        e.setPlaceholderText("Name" if apps else "Action")
        e.setEnabled(bool(it))
        if it:
            e.textEdited.connect(lambda t, i=idx, fld=field: items[i].__setitem__(fld, t))
        h.addWidget(e, 1)

        if it:
            rm = QToolButton()
            rm.setObjectName("removeBtn")
            rm.setText("✕")
            rm.setToolTip("Remove")
            rm.setCursor(Qt.PointingHandCursor)
            rm.clicked.connect(partial(self._remove, idx))
            h.addWidget(rm)
        return f

    # ---------------------------------------------------------------- row actions
    def _later(self):
        QTimer.singleShot(0, self._rebuild)

    def _on_gesture(self, idx, g):
        items = self._items()
        if idx is None:
            if self._mode == "applications":
                items.append({"gesture": g, "name": "", "path": ""})
            else:
                items.append({"gesture": g, "key": "", "action": ""})
        else:
            cur = items[idx]["gesture"]
            if g == cur:
                return
            other = next((x for x in items if x["gesture"] == g and x is not items[idx]), None)
            if other:                       # picked a gesture already in use -> swap
                other["gesture"] = cur
            items[idx]["gesture"] = g
        self._later()

    def _remove(self, idx):
        del self._items()[idx]
        self._later()

    def _choose_app(self, idx):
        if idx is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose application", "",
            "Applications (*.exe *.lnk *.app *.desktop *.sh);;All files (*)")
        if path:
            it = self._apps[idx]
            it["path"] = path
            if not it["name"]:
                it["name"] = os.path.splitext(os.path.basename(path))[0]
            app_pixmap.cache_clear()
            self._later()

    # ---------------------------------------------------------------- apply / reset
    def _commit(self):
        p = self._params
        p["general"].update(self._general)
        p["applications"] = copy.deepcopy(self._apps)
        p["video_player"] = copy.deepcopy(self._video)
        save_parameters(p)
        self.applied.emit(p)

    def _apply(self):
        self._commit()

    def _reset(self):
        d = copy.deepcopy(DEFAULTS)
        self._general = d["general"]
        self._apps, self._video = d["applications"], d["video_player"]
        self._sync_toggles()
        self._rebuild()
        self._commit()          # defaults are written to the json straight away
