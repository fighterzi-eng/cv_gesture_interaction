"""Reusable widgets: toggle, gesture/app icons, key capture, gesture combo,
collapsible section, camera view, test window, draggable overlay window."""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import (QPointF, QEvent, QFileInfo, QObject, QPoint, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication, QIcon, QImage,
                           QKeySequence, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF, QTransform)
from PySide6.QtWidgets import (QAbstractScrollArea, QSizeGrip, QComboBox, QFileIconProvider, QLineEdit,
                               QFrame, QHBoxLayout, QLabel, QPushButton,
                               QStyle, QStyledItemDelegate, QToolButton, QVBoxLayout,
                               QWidget, QAbstractButton)

import theme
from params import GESTURES, GESTURE_NAMES


# ----------------------------------------------------------------- frames -> QImage
def bgr_to_qimage(arr):
    """numpy BGR uint8 (H,W,3) -> QImage (copy). Glue for the cv2 pipeline."""
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, 3 * w, QImage.Format_BGR888).copy()


def gray_to_qimage(arr):
    """numpy uint8 (H,W) mask -> QImage (copy)."""
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, w, QImage.Format_Grayscale8).copy()


# ----------------------------------------------------------------- overlay windows
class DragFilter(QObject):
    """Starts a native window move when the user drags (if not locked)."""

    def __init__(self, window, is_locked):
        super().__init__(window)
        self._w, self._locked, self._press = window, is_locked, None

    def eventFilter(self, obj, e):
        t = e.type()
        if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
            self._press = e.globalPosition().toPoint()
        elif t == QEvent.MouseButtonRelease:
            self._press = None
        elif t == QEvent.MouseMove and self._press is not None and (e.buttons() & Qt.LeftButton):
            if (e.globalPosition().toPoint() - self._press).manhattanLength() > 8:
                self._press = None
                if not self._locked():
                    h = self._w.windowHandle()
                    if h:
                        h.startSystemMove()
        return False


class OverlayWindow(QWidget):
    """Frameless, always-on-top, translucent window."""
    moved = Signal(QPoint)
    closed = Signal()

    def __init__(self, activating=False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if not activating:
            self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._drag = None

    def enable_drag(self, is_locked):
        self._drag = DragFilter(self, is_locked)
        self.refresh_drag()

    def refresh_drag(self):
        if self._drag:
            for w in [self] + self.findChildren(QWidget):
                w.installEventFilter(self._drag)

    def moveEvent(self, e):
        super().moveEvent(e)
        self.moved.emit(self.pos())

    def closeEvent(self, e):
        super().closeEvent(e)
        self.closed.emit()


class DialogMoveFilter(QObject):
    """Drag a settings window by its empty areas (panel / labels). Buttons, fields, lists are ignored."""

    def __init__(self, window):
        super().__init__(window)
        self._w, self._press = window, None

    def eventFilter(self, obj, e):
        t = e.type()
        if t == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
            plain = isinstance(obj, (QLabel, QFrame)) and not isinstance(obj, QAbstractScrollArea)
            self._press = e.globalPosition().toPoint() if (plain or obj is self._w) else None
        elif t == QEvent.MouseButtonRelease:
            self._press = None
        elif t == QEvent.MouseMove and self._press is not None and (e.buttons() & Qt.LeftButton):
            if (e.globalPosition().toPoint() - self._press).manhattanLength() > 6:
                self._press = None
                h = self._w.windowHandle()
                if h:
                    h.startSystemMove()
        return False


class DialogWindow(OverlayWindow):
    """Big settings window: movable (drag empty areas), resizable (bottom-right grip),
    centred on the primary screen the first time it opens."""
    W, H = 880, 700
    MIN = (700, 480)

    def __init__(self):
        super().__init__(activating=True)
        self.setMinimumSize(*self.MIN)
        self._placed = False
        self._mover = DialogMoveFilter(self)
        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(20, 20)
        self._grip.setCursor(Qt.SizeFDiagCursor)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._grip.move(self.width() - 22, self.height() - 22)
        self._grip.raise_()

    def show_centered(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        if not self._placed:                       # size + position only the first time
            self._placed = True
            self.resize(min(self.W, scr.width() - 40), min(self.H, scr.height() - 40))
            self.move(scr.center() - QPoint(self.width() // 2, self.height() // 2))
        for wd in [self] + self.findChildren(QWidget):
            wd.installEventFilter(self._mover)
        self.show()
        self.raise_()
        self.activateWindow()
        self._grip.raise_()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


# ----------------------------------------------------------------- toggle
class Toggle(QAbstractButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 1.0 if checked else 0.0
        self.setChecked(checked)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.valueChanged.connect(self._set_pos)
        self.toggled.connect(self._animate)

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#3a3a42"))
        p.drawRoundedRect(r, 13, 13)
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, QColor("#ff4d2e"))
        g.setColorAt(1, QColor("#ff9a3c"))
        p.setOpacity(self._pos)
        p.setBrush(g)
        p.drawRoundedRect(r, 13, 13)
        p.setOpacity(1)
        p.setBrush(QColor("white"))
        x = 3 + self._pos * (r.width() - 26)
        p.drawEllipse(QRectF(x, 3, 20, 20))


# ----------------------------------------------------------------- icons
@lru_cache(maxsize=256)
def gesture_pixmap(gid: str, size: int) -> QPixmap:
    """Hand icon: 1..5 fingers or closed palm (drawn in code, no image files)."""
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 100, size / 100)

    n_up = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 4, "fist": 0}[gid]
    paths = []
    palm = QPainterPath()
    palm.addRoundedRect(QRectF(20, 46, 58, 46), 20, 20)
    paths.append(palm)
    tops = [12, 4, 10, 22]
    for i, x in enumerate([22, 37, 52, 67]):
        f = QPainterPath()
        if i < n_up:
            f.addRoundedRect(QRectF(x, tops[i], 13, 60 - tops[i]), 6.5, 6.5)
        else:                                   # folded finger = knuckle bump
            f.addRoundedRect(QRectF(x, 40, 13, 22), 6.5, 6.5)
        paths.append(f)
    if gid == "five":                            # thumb out
        t = QPainterPath()
        t.addRoundedRect(QRectF(-7, -30, 14, 42), 7, 7)
        tr = QTransform()
        tr.translate(22, 78)
        tr.rotate(-38)
        paths.append(tr.map(t))

    outline, fill = QColor("#8a5a12"), QColor("#ffc93c")
    p.setPen(QPen(outline, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(outline)
    for pa in paths:
        p.drawPath(pa)
    p.setPen(Qt.NoPen)
    p.setBrush(fill)
    for pa in paths:
        p.drawPath(pa)
    if gid != "five":                            # tucked thumb
        th = QPainterPath()
        th.addRoundedRect(QRectF(24, 62, 32, 14), 7, 7)
        p.setPen(QPen(outline, 2))
        p.setBrush(fill)
        p.drawPath(th)
    p.end()
    return pm


_BRANDS = {"chrome": ("#4285F4", "C"), "telegram": ("#2AABEE", "T"), "discord": ("#5865F2", "D"),
           "edge": ("#0F9D8A", "E"), "steam": ("#1B2838", "S"), "firefox": ("#FF7139", "F")}


@lru_cache(maxsize=256)
def app_pixmap(name: str, path: str, size: int) -> QPixmap:
    """Real file icon if a path is set, otherwise a coloured placeholder badge."""
    if path and QFileInfo(path).exists():
        pm = QFileIconProvider().icon(QFileInfo(path)).pixmap(size, size)
        if not pm.isNull():
            return pm
    color, letter = "#6b6b78", (name[:1].upper() or "?")
    for k, (c, l) in _BRANDS.items():
        if k in name.lower():
            color, letter = c, l
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.setPen(QColor("white"))
    f = QFont("Segoe UI")
    f.setPixelSize(int(size * 0.5))
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, letter)
    p.end()
    return pm


# ----------------------------------------------------------------- key capture
_KEYS = {int(Qt.Key_Space): "Space", int(Qt.Key_Left): "←", int(Qt.Key_Right): "→",
         int(Qt.Key_Up): "↑", int(Qt.Key_Down): "↓", int(Qt.Key_Return): "Enter",
         int(Qt.Key_Enter): "Enter", int(Qt.Key_Tab): "Tab", int(Qt.Key_Backspace): "Backspace",
         int(Qt.Key_Delete): "Delete"}


class KeyCaptureButton(QPushButton):
    """Orange key badge. Click, then press the key (Esc cancels)."""
    changed = Signal(str)

    def __init__(self, key="", parent=None):
        super().__init__(key or "Set key", parent)
        self.setObjectName("keyBadge")
        self.setCursor(Qt.PointingHandCursor)
        self._capturing, self._old = False, key
        self.clicked.connect(self._begin)

    def _begin(self):
        self._capturing, self._old = True, self.text()
        self.setText("Press a key…")
        self.setFocus()
        self.grabKeyboard()

    def _end(self, text):
        self._capturing = False
        self.releaseKeyboard()
        self.setText(text)

    def keyPressEvent(self, e):
        if not self._capturing:
            return super().keyPressEvent(e)
        k = e.key()
        if k in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            return
        if k == Qt.Key_Escape:
            return self._end(self._old)
        name = _KEYS.get(int(k)) or QKeySequence(int(k)).toString()
        m = e.modifiers()
        prefix = ("Ctrl+" if m & Qt.ControlModifier else "") + ("Alt+" if m & Qt.AltModifier else "") \
            + ("Shift+" if m & Qt.ShiftModifier else "")
        self._end(prefix + name)
        self.changed.emit(prefix + name)

    def focusOutEvent(self, e):
        if self._capturing:
            self._end(self._old)
        super().focusOutEvent(e)


# ----------------------------------------------------------------- gesture combo
class _GestureDelegate(QStyledItemDelegate):
    def __init__(self, combo):
        super().__init__(combo)
        self._combo = combo

    def sizeHint(self, option, index):
        return QSize(270, 34)

    def paint(self, p, opt, index):
        gid = index.data(Qt.UserRole)
        used = bool(index.data(Qt.UserRole + 1))
        current = index.row() == self._combo.currentIndex()
        hover = bool(opt.state & QStyle.State_MouseOver)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(opt.rect).adjusted(2, 1, -2, -1)
        if current or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#3a2216") if current else QColor("#1d1d24"))
            p.drawRoundedRect(r, 8, 8)
        p.drawPixmap(int(r.left() + 10), int(r.center().y() - 11), gesture_pixmap(gid, 22))
        f = QFont(opt.font)
        f.setPixelSize(14)
        f.setBold(current)
        p.setFont(f)
        p.setPen(QColor("#ff9a3c") if current else QColor(theme.TEXT))
        p.drawText(QRectF(r.left() + 44, r.top(), r.width() - 100, r.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, GESTURE_NAMES[gid])
        small = QFont(f)
        small.setPixelSize(10)
        small.setBold(False)
        p.setFont(small)
        if current:
            p.setPen(QColor("#ff9a3c"))
            p.drawText(QRectF(r.right() - 40, r.top(), 30, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, "✓")
        elif used:
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(r.right() - 60, r.top(), 50, r.height()),
                       Qt.AlignVCenter | Qt.AlignRight, "in use")
        p.restore()


class GestureCombo(QComboBox):
    """Dropdown listing the 6 gestures with an 'in use' marker."""
    gestureChosen = Signal(str)

    def __init__(self, current=None, used_provider=None, parent=None):
        super().__init__(parent)
        self.setObjectName("gestureCombo")
        self._used = used_provider or (lambda: set())
        self.setItemDelegate(_GestureDelegate(self))
        for g in GESTURES:
            self.addItem(QIcon(gesture_pixmap(g, 24)), GESTURE_NAMES[g])
            self.setItemData(self.count() - 1, g, Qt.UserRole)
        self.setPlaceholderText("+  Select gesture")
        self.setCurrentIndex(GESTURES.index(current) if current else -1)
        self.setCursor(Qt.PointingHandCursor)
        self.activated.connect(lambda i: self.gestureChosen.emit(self.itemData(i, Qt.UserRole)))
        w = self.view().window()
        w.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        w.setAttribute(Qt.WA_TranslucentBackground)

    def showPopup(self):
        used = self._used()
        for i, g in enumerate(GESTURES):
            self.setItemData(i, g in used, Qt.UserRole + 1)
        self.view().setMinimumWidth(max(self.width(), 270))
        super().showPopup()


# ----------------------------------------------------------------- number fields
class NumField(QLineEdit):
    """Number box (int or float) with the same value()/setValue() API as a spin box.
    Up/Down keys or the wheel (when focused) step the value."""

    def __init__(self, kind, lo, hi, step, decimals=2):
        super().__init__()
        self._int, self._lo, self._hi, self._step = kind == "int", lo, hi, step
        self._dec = 0 if self._int else decimals
        self.setObjectName("field")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(120, 30)
        self._v = lo
        self.editingFinished.connect(self._commit)

    def _fmt(self, v):
        return str(int(v)) if self._int else f"{v:.{self._dec}f}"

    def value(self):
        self._commit()
        return self._v

    def setValue(self, v):
        v = min(self._hi, max(self._lo, v))
        self._v = int(round(v)) if self._int else round(float(v), self._dec)
        self.setText(self._fmt(self._v))

    def _commit(self):
        try:
            self.setValue(float(self.text().replace(",", ".")))
        except ValueError:
            self.setValue(self._v)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Up, Qt.Key_Down):
            self._commit()
            self.setValue(self._v + (self._step if e.key() == Qt.Key_Up else -self._step))
        else:
            super().keyPressEvent(e)

    def wheelEvent(self, e):
        if self.hasFocus():
            self._commit()
            self.setValue(self._v + (self._step if e.angleDelta().y() > 0 else -self._step))
        else:
            e.ignore()


def make_spin(kind, lo, hi, step, decimals=2):
    return NumField(kind, lo, hi, step, decimals)


# ----------------------------------------------------------------- collapsible section
class CollapsibleSection(QWidget):
    def __init__(self, title, expanded=True):
        super().__init__()
        self._title = title
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.header = QPushButton()
        self.header.setObjectName("sectionHeader")
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.PointingHandCursor)
        self.body = QWidget()
        self.form = QVBoxLayout(self.body)
        self.form.setContentsMargins(12, 4, 6, 8)
        self.form.setSpacing(10)
        v.addWidget(self.header)
        v.addWidget(self.body)
        self.header.toggled.connect(self._toggle)
        self._toggle(expanded)

    def _toggle(self, on):
        self.body.setVisible(on)
        self.header.setText(("▾  " if on else "▸  ") + self._title)

    def add_row(self, label, widget):
        h = QHBoxLayout()
        h.addWidget(QLabel(label), 1)
        h.addWidget(widget, 0, Qt.AlignRight)
        self.form.addLayout(h)

    def add_sub(self, text):
        lab = QLabel(text.upper())
        lab.setObjectName("subHead")
        self.form.addWidget(lab)


# ----------------------------------------------------------------- camera view
HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10),
                    (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18),
                    (18, 19), (19, 20), (0, 17)]


class CameraView(QWidget):
    """Live preview: frame + LIVE badge + optional FPS / hand square / landmarks / accuracy."""

    def __init__(self, radius=14, scale=0.8, parent=None):
        super().__init__(parent)
        self._radius, self._scale = radius, scale
        self._frame = None
        self._fps = 0.0
        self._box = None            # (x, y, w, h) normalised 0..1
        self._lm = []               # [(x, y)] normalised
        self._conf = None
        self._label = ""
        self._shapes = None         # (contours, lines, points) normalised, drawn like classic_detector
        self.show_fps = self.show_landmarks = self.show_box = True

    # ---- feed (called by the project)
    def set_frame(self, img: QImage):
        self._frame = img
        self.update()

    def set_fps(self, fps):
        self._fps = fps
        self.update()

    def set_detection(self, box=None, landmarks=None, confidence=None, label=""):
        self._box, self._lm, self._conf, self._label = box, landmarks or [], confidence, label
        self.update()

    def set_shapes(self, contours=None, lines=None, points=None):
        """contours=[[(x,y)..]], lines=[((x,y),(x,y))], points=[((x,y), kind)] with kind in
        'centroid' | 'tip' | 'far'; all normalised 0..1. Same drawing as classic_detector.py."""
        self._shapes = (contours or [], lines or [], points or []) if (contours or lines or points) else None
        self.update()

    def set_options(self, show_fps, show_landmarks, show_box):
        self.show_fps, self.show_landmarks, self.show_box = show_fps, show_landmarks, show_box
        self.update()

    # ---- painting
    def _pill(self, p, x, y, text, fg, bg, dot=None, right=False):
        f = QFont("Segoe UI")
        f.setPixelSize(int(11 * self._scale * 1.25))
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        pad, h = 9 * self._scale, 22 * self._scale
        w = fm.horizontalAdvance(text) + 2 * pad + (14 * self._scale if dot else 0)
        if right:
            x -= w
        r = QRectF(x, y, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, h / 2, h / 2)
        tx = r.left() + pad
        if dot:
            p.setBrush(dot)
            d = 7 * self._scale
            p.drawEllipse(QRectF(tx, r.center().y() - d / 2, d, d))
            tx += 14 * self._scale
        p.setPen(fg)
        p.drawText(QRectF(tx, r.top(), w, h), Qt.AlignVCenter | Qt.AlignLeft, text)
        return r

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(r, self._radius, self._radius)
        p.save()
        p.setClipPath(clip)
        fw, fh = (self._frame.width(), self._frame.height()) if self._frame else (4, 3)
        s = max(r.width() / fw, r.height() / fh)
        dw, dh = fw * s, fh * s
        ox, oy = r.center().x() - dw / 2, r.center().y() - dh / 2
        if self._frame:
            p.drawImage(QRectF(ox, oy, dw, dh), self._frame)
        else:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor("#1b1b22"))
            g.setColorAt(1, QColor("#0c0c10"))
            p.fillRect(r, g)
            p.setPen(QColor(theme.MUTED))
            p.drawText(r, Qt.AlignCenter, "Waiting for camera…")
        mp = lambda x, y: (ox + x * dw, oy + y * dh)

        if self._shapes:
            contours, lines, pts_ = self._shapes
            if self.show_box:                                  # hand outline + hull lines
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(0, 255, 0), 2))
                for c in contours:
                    p.drawPolygon(QPolygonF([QPointF(*mp(*q)) for q in c]))
                p.setPen(QPen(QColor(0, 255, 255), 2))
                for a, b in lines:
                    (x1, y1), (x2, y2) = mp(*a), mp(*b)
                    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            if self.show_landmarks:                            # centroid / fingertips / valleys
                cols = {"centroid": (QColor(255, 0, 255), 5), "tip": (QColor(255, 0, 125), 5),
                        "far": (QColor(255, 0, 0), 3.5)}
                p.setPen(Qt.NoPen)
                for q, kind in pts_:
                    col, rad = cols[kind]
                    x, y = mp(*q)
                    p.setBrush(col)
                    p.drawEllipse(QPointF(x, y), rad, rad)
        if self.show_box and self._box and not self._shapes:
            x, y = mp(self._box[0], self._box[1])
            bw, bh = self._box[2] * dw, self._box[3] * dh
            p.setPen(QPen(QColor(theme.ORANGE2), 2))
            p.setBrush(QColor(255, 154, 60, 30))
            p.drawRoundedRect(QRectF(x, y, bw, bh), 6, 6)
            parts = [t for t in (self._label,
                                 f"{self._conf * 100:.0f}%" if self._conf is not None else "")
                     if t]
            if parts:
                self._pill(p, x, max(r.top() + 4, y - 24 * self._scale), "  ".join(parts),
                           QColor("black"), QColor(theme.ORANGE2))
        if self.show_landmarks and self._lm:
            pts = [mp(*q) for q in self._lm]
            if len(pts) == 21:
                p.setPen(QPen(QColor("#37d67a"), 2))
                for a, b in HAND_CONNECTIONS:
                    p.drawLine(int(pts[a][0]), int(pts[a][1]), int(pts[b][0]), int(pts[b][1]))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ff3b7a"))
            for x, y in pts:
                p.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
        p.restore()

        m = 10 * self._scale
        self._pill(p, r.left() + m, r.top() + m, "LIVE", QColor("white"), QColor(0, 0, 0, 230),
                   dot=QColor("#ff3b30"))
        if self.show_fps:
            self._pill(p, r.right() - m, r.top() + m, f"{self._fps:.0f} FPS", QColor(theme.ORANGE2),
                       QColor(0, 0, 0, 200), right=True)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.RED), 2))
        p.drawPath(clip)


# ----------------------------------------------------------------- test window
class TestWindow(QWidget):
    """Normal standalone window (own title bar, movable anywhere on screen, not bound to the camera view)
    showing the three black/white views of classic_detector.py: Skin / Motion seed / Hand mask."""
    closed = Signal()
    VIEWS = (("skin", "Skin"), ("motion", "Motion (seed)"), ("hand", "Hand mask"))

    def __init__(self, parent=None):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowTitleHint
                         | Qt.WindowCloseButtonHint)
        self.setWindowTitle("Test window")
        self.setObjectName("testWin")
        self.resize(660, 270)
        self.setMinimumSize(420, 200)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(4)
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{theme.MUTED};font-size:11px;")
        v.addWidget(self.status)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.views = {}
        for key, title in self.VIEWS:
            col = QVBoxLayout()
            col.setSpacing(2)
            cap = QLabel(title)
            cap.setAlignment(Qt.AlignCenter)
            cap.setStyleSheet(f"color:{theme.AMBER};font-size:11px;font-weight:700;")
            lab = QLabel("No data yet")
            lab.setAlignment(Qt.AlignCenter)
            lab.setMinimumSize(120, 120)
            lab.setStyleSheet(f"background:#000;color:{theme.MUTED};")
            col.addWidget(cap)
            col.addWidget(lab, 1)
            row.addLayout(col, 1)
            self.views[key] = lab
        v.addLayout(row, 1)

    def closeEvent(self, e):
        super().closeEvent(e)
        self.closed.emit()

    def set_masks(self, skin=None, motion=None, hand=None):
        if not self.isVisible():
            return
        for key, img in (("skin", skin), ("motion", motion), ("hand", hand)):
            if img is not None:
                lab = self.views[key]
                lab.setPixmap(QPixmap.fromImage(img).scaled(
                    lab.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

    def set_mask(self, img: QImage):
        self.set_masks(hand=img)

    def set_status(self, text):
        self.status.setText(text)
