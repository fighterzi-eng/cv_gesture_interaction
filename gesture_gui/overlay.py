"""On-screen overlay windows: menu + gesture list (HUD), camera preview, confirmation toast."""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QLayout,
                               QMenu, QPushButton, QVBoxLayout, QWidget)

import theme
from params import GESTURE_NAMES
from widgets import CameraView, OverlayWindow, app_pixmap, gesture_pixmap


class HamburgerButton(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setFixedSize(52, 52)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setBrush(QColor("#000"))
        p.setPen(QPen(QColor("white"), 3))
        p.drawEllipse(r)
        p.setPen(QPen(QColor("white"), 3, Qt.SolidLine, Qt.RoundCap))
        c = r.center()
        for dy in (-8, 0, 8):
            p.drawLine(int(c.x() - 10), int(c.y() + dy), int(c.x() + 10), int(c.y() + dy))


class HudWindow(OverlayWindow):
    """Hamburger menu (User / Developer settings) + gesture legend list."""
    userSettingsRequested = Signal()
    developerSettingsRequested = Signal()
    quitRequested = Signal()

    def __init__(self):
        super().__init__()
        self.mode = "applications"
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.setSizeConstraint(QLayout.SetFixedSize)

        # --- menu
        self.menu = QFrame()
        self.menu.setObjectName("menuPanel")
        mh = QHBoxLayout(self.menu)
        mh.setContentsMargins(10, 10, 10, 10)
        mh.setSpacing(12)
        self.burger = HamburgerButton()
        self.burger.clicked.connect(lambda: self.set_menu_open(not self._open))
        self.sep = QFrame()
        self.sep.setObjectName("vline")
        self.sep.setFixedWidth(1)
        self.items = QWidget()
        iv = QVBoxLayout(self.items)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(4)
        self.btn_user = self._item("⚙   User settings")
        self.btn_dev = self._item("🛠   Developer settings")
        self.btn_user.clicked.connect(self.userSettingsRequested)
        self.btn_dev.clicked.connect(self.developerSettingsRequested)
        iv.addWidget(self.btn_user)
        iv.addWidget(self.btn_dev)
        mh.addWidget(self.burger)
        mh.addWidget(self.sep)
        mh.addWidget(self.items)
        root.addWidget(self.menu, 0, Qt.AlignLeft)

        # --- legend
        self.legend = QFrame()
        self.legend.setObjectName("legendPanel")
        self._lv = QVBoxLayout(self.legend)
        self._lv.setContentsMargins(8, 8, 8, 8)
        self._lv.setSpacing(6)
        root.addWidget(self.legend, 0, Qt.AlignLeft)
        self.set_menu_open(False)

    def _item(self, text):
        b = QPushButton(text)
        b.setObjectName("menuItem")
        b.setCursor(Qt.PointingHandCursor)
        return b

    _open = False

    def set_menu_open(self, on):
        self._open = on
        self.sep.setVisible(on)
        self.items.setVisible(on)
        self.menu.setProperty("collapsed", "false" if on else "true")
        self.menu.style().unpolish(self.menu)
        self.menu.style().polish(self.menu)
        self.adjustSize()
        if not on:
            self.set_active_item(None)

    def set_active_item(self, which):
        for b, k in ((self.btn_user, "user"), (self.btn_dev, "dev")):
            b.setProperty("active", "true" if which == k else "false")
            b.style().unpolish(b)
            b.style().polish(b)

    def set_legend(self, mode, params):
        """mode: 'applications' (gesture -> app icon) or 'video_player' (gesture -> key)."""
        self.mode = mode
        while self._lv.count():
            w = self._lv.takeAt(0).widget()
            if w:
                w.deleteLater()
        items = params["applications" if mode == "applications" else "video_player"]
        for it in items:
            row = QFrame()
            row.setObjectName("legendRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(8, 4, 8, 4)
            h.setSpacing(10)
            g = QLabel()
            g.setPixmap(gesture_pixmap(it["gesture"], 28))
            g.setToolTip(GESTURE_NAMES[it["gesture"]])
            h.addWidget(g)
            if mode == "applications":
                a = QLabel()
                a.setPixmap(app_pixmap(it.get("name", ""), it.get("path", ""), 26))
                a.setToolTip(it.get("name", ""))
                h.addWidget(a)
            else:
                k = QLabel(it.get("key", ""))
                k.setObjectName("legendKey")
                k.setAlignment(Qt.AlignCenter)
                k.setToolTip(it.get("action", ""))
                h.addWidget(k)
            self._lv.addWidget(row)
        self.legend.setVisible(bool(items))
        self.adjustSize()
        self.refresh_drag()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.addAction("Quit").triggered.connect(self.quitRequested)
        m.exec(e.globalPos())


class CameraPreviewWindow(OverlayWindow):
    """Small LIVE preview, top-right."""

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.view = CameraView(radius=14, scale=0.8)
        self.view.setFixedSize(210, 208)
        v.addWidget(self.view)


class CountdownRing(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(66, 66)
        self._rem, self._tot = 3.0, 3.0

    def set_value(self, remaining, total):
        self._rem, self._tot = remaining, max(total, 0.001)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#2e2e36"), 5))
        p.drawEllipse(r)
        p.setPen(QPen(QColor(theme.ORANGE2), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 90 * 16, int(-360 * 16 * max(0.0, min(1.0, self._rem / self._tot))))
        f = QFont("Segoe UI")
        f.setPixelSize(24)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(0, 12, self.width(), 30), Qt.AlignCenter, str(max(0, math.ceil(self._rem))))
        f.setPixelSize(9)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(0, 40, self.width(), 14), Qt.AlignCenter, "sec")


class ToastWindow(OverlayWindow):
    """'GESTURE DETECTED' confirmation: HOLD to confirm / RELEASE to cancel + countdown ring."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(700, 110)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("toastPanel")
        outer.addWidget(panel)
        h = QHBoxLayout(panel)
        h.setContentsMargins(18, 14, 24, 14)
        h.setSpacing(18)
        self.icon = QLabel()
        self.icon.setFixedSize(80, 80)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet("background:#1c1c22;border:1px solid #2e2e36;border-radius:14px;")
        h.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.head = QLabel()
        self.head.setStyleSheet(f"color:{theme.AMBER};font-size:11px;font-weight:700;")
        self.title = QLabel()
        self.title.setStyleSheet("font-size:21px;font-weight:700;")
        pills = QHBoxLayout()
        pills.setSpacing(10)
        for text, bg, bd in (("HOLD: confirm", "#0f3a24", theme.GREEN), ("RELEASE: cancel", "#4a1512", "#b3342b")):
            l = QLabel(text)
            l.setStyleSheet(f"background:{bg};border:2px solid {bd};border-radius:14px;"
                            "padding:3px 16px;font-weight:700;font-size:13px;")
            pills.addWidget(l)
        pills.addStretch()
        col.addWidget(self.head)
        col.addWidget(self.title)
        col.addLayout(pills)
        h.addLayout(col, 1)
        self.ring = CountdownRing()
        h.addWidget(self.ring)
        self._total = 3.0

    def show_gesture(self, gid, action_text, total_seconds):
        self._total = float(total_seconds)
        self.icon.setPixmap(gesture_pixmap(gid, 54))
        self.head.setText("GESTURE DETECTED: " + GESTURE_NAMES[gid].upper())
        self.title.setText(action_text)
        self.ring.set_value(self._total, self._total)
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.bottom() - self.height() - 20)
        self.show()
        self.raise_()

    def set_remaining(self, remaining):
        self.ring.set_value(remaining, self._total)

    def hide_toast(self):
        self.hide()
