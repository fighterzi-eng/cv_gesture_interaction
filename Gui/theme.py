"""Colours + global stylesheet (matched to the design screenshots)."""
import tempfile
from pathlib import Path
from string import Template

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QPolygonF

ORANGE = "#ff6a2a"      # panel borders
ORANGE2 = "#ff9a3c"     # gradient end / values
AMBER = "#f5a524"       # column headers
RED = "#ff4b3e"         # LIVE border
BG = "#0e0e13"
BG_FIELD = "#0b0b0f"
ROW = "#15151b"
ROWB = "#2a2a32"
TEXT = "#f2f2f5"
MUTED = "#8b8b96"
GREEN = "#1f9d55"

QSS = Template(r"""
* { font-family: "Segoe UI","Inter","DejaVu Sans","Noto Sans",sans-serif; color:$TEXT; }
QWidget { outline:0; }
QLabel { background:transparent; }
#panel, #menuPanel, #legendPanel, #toastPanel { background:$BG; border:2px solid $ORANGE; border-radius:18px; }
#menuPanel[collapsed="true"] { border-radius:38px; }
#legendPanel { border-radius:14px; }
#title { font-size:24px; font-weight:700; }
#devTitle { font-size:22px; font-weight:700; }
#settingLabel { font-size:15px; }
#note { color:$MUTED; font-size:12px; }
#colHead { color:$AMBER; font-size:11px; font-weight:700; }
#subHead { color:$AMBER; font-size:11px; font-weight:700; padding-top:6px; }
#hline { background:#2a2a32; border:none; }
#vline { background:#33333c; border:none; }
#row { background:$ROW; border:1px solid $ROWB; border-radius:12px; }
#legendRow { background:$ROW; border:1px solid $ROWB; border-radius:9px; }
#legendKey { color:$AMBER; border:1px solid $ORANGE; border-radius:6px; padding:2px 6px; font-size:11px; font-weight:700; }
#keyBadge { color:$AMBER; background:$BG_FIELD; border:1px solid $ORANGE; border-radius:7px; padding:4px 12px; min-width:36px; font-weight:700; font-size:13px; }
#keyBadge:hover { background:#2a1a12; }

QPushButton#tab { background:$ROW; border:1px solid #33333c; border-radius:16px; padding:9px 26px; font-weight:700; font-size:13px; }
QPushButton#tab:hover { border-color:$ORANGE; }
QPushButton#tab:checked { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff4d2e,stop:1 #ff9a3c); border:1px solid transparent; color:white; }
QPushButton#pill { background:#1c1c22; border:1px solid #3a3a44; border-radius:17px; padding:9px 30px; font-weight:700; font-size:14px; }
QPushButton#pill:hover { border-color:$ORANGE; }
QPushButton#primary { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff4d2e,stop:1 #ff9a3c); border:none; border-radius:17px; padding:9px 34px; font-weight:700; font-size:14px; color:white; }
QPushButton#primary:hover { background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #ff6a4e,stop:1 #ffb05c); }
QPushButton#outlineBtn { background:transparent; border:1px solid $ORANGE; border-radius:16px; padding:8px 20px; color:$ORANGE2; font-weight:700; font-size:12px; }
QPushButton#outlineBtn:hover { background:#2a1a12; }
QPushButton#menuItem { background:transparent; border:none; border-radius:8px; padding:7px 14px; text-align:left; font-size:15px; min-width:190px; }
QPushButton#menuItem:hover { background:#1d1d24; }
QPushButton#menuItem[active="true"] { background:#3a2216; color:#ffb070; }
QPushButton#sectionHeader { background:#1c1c22; border:none; border-radius:6px; padding:8px 12px; text-align:left; font-weight:700; font-size:13px; }
QPushButton#sectionHeader:hover { background:#24242c; }
QPushButton#appBtn { background:transparent; border:none; padding:2px; text-align:left; }
QPushButton#appBtn[empty="true"] { background:$BG_FIELD; border:1px solid #3a3a44; border-radius:10px; padding:8px 14px; color:#b9b9c4; font-size:13px; }
QPushButton#appBtn[empty="true"]:hover { border-color:$ORANGE; }
QPushButton#appBtn[empty="true"]:disabled { color:#5d5d68; border-color:#2a2a32; }
QToolButton#removeBtn { color:$MUTED; border:none; font-size:14px; padding:4px 8px; background:transparent; }
QToolButton#removeBtn:hover { color:$ORANGE; }
QToolButton#testClose { color:#cfcfd6; border:none; font-size:13px; background:transparent; }

QLineEdit#field { background:$BG_FIELD; border:1px solid #33333c; border-radius:8px; color:$AMBER; font-weight:700; font-size:13px; padding:2px 6px; selection-background-color:$ORANGE; }
QLineEdit#field:focus { border-color:$ORANGE; }
QLineEdit#cell { background:transparent; border:none; border-bottom:1px solid transparent; font-size:15px; padding:6px 0; selection-background-color:$ORANGE; }
QLineEdit#cell:focus { border-bottom:1px solid $ORANGE; }
QComboBox#plainCombo { background:$BG_FIELD; border:1px solid #33333c; border-radius:8px; color:$AMBER; font-weight:700; padding:3px 10px; }
QComboBox#plainCombo::drop-down { border:none; width:22px; }
QComboBox#plainCombo::down-arrow { image:url($ARROW); width:10px; height:10px; }

QComboBox#gestureCombo { padding:6px 12px; }
QComboBox#gestureCombo[slot="empty"] { background:$BG_FIELD; border:1px solid #3a3a44; border-radius:10px; color:#b9b9c4; }
QComboBox#gestureCombo[slot="empty"]:on { border:1px solid $ORANGE; }
QComboBox#gestureCombo[slot="filled"] { background:transparent; border:none; font-weight:700; font-size:13px; padding:0 0 0 2px; }
QComboBox#gestureCombo::drop-down { border:none; width:22px; }
QComboBox#gestureCombo[slot="filled"]::drop-down { width:0px; }
QComboBox#gestureCombo::down-arrow { image:url($ARROW); width:10px; height:10px; }
QComboBox#gestureCombo[slot="filled"]::down-arrow { image:none; }
QComboBox QAbstractItemView { background:$BG; border:2px solid $ORANGE; border-radius:12px; padding:4px; selection-background-color:transparent; }

#testWin { background:#0d0d10; }
#testHead { background:#1b1b20; border-top-left-radius:6px; border-top-right-radius:6px; }

QScrollArea { background:transparent; border:none; }
QScrollArea > QWidget > QWidget { background:transparent; }
QScrollBar:vertical { width:8px; background:transparent; margin:0; }
QScrollBar::handle:vertical { background:#3a3a44; border-radius:4px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background:transparent; }
QToolTip { background:$BG; color:$TEXT; border:1px solid $ORANGE; padding:4px; }
""")


def build_qss():
    assets = Path(tempfile.gettempdir()) / "gesture_gui_assets"
    assets.mkdir(exist_ok=True)
    arrow = assets / "arrow_down.png"
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#9a9aa6"))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(5, 7), QPointF(15, 7), QPointF(10, 13)]))
    p.end()
    pm.save(str(arrow))
    return QSS.substitute(
        TEXT=TEXT, BG=BG, BG_FIELD=BG_FIELD, ORANGE=ORANGE, ORANGE2=ORANGE2, AMBER=AMBER,
        MUTED=MUTED, ROW=ROW, ROWB=ROWB, ARROW=arrow.as_posix())


def apply_theme(app):
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(build_qss())
