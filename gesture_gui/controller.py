"""GestureGui: creates all windows and wires them to the parameters.
This is the only object the rest of the project needs to talk to."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtGui import QGuiApplication, QImage

from dev_settings import DeveloperSettingsDialog
from overlay import CameraPreviewWindow, HudWindow, ToastWindow
from params import load_parameters, save_parameters
from user_settings import UserSettingsDialog


class GestureGui(QObject):
    parametersApplied = Signal(dict)     # emitted after Apply / Reset (params already saved to json)
    quitRequested = Signal()

    def __init__(self, params=None):
        super().__init__()
        self.params = params or load_parameters()      # user json if present, else defaults
        locked = lambda: self.params["general"]["lock_windows"]

        self.hud, self.preview, self.toast = HudWindow(), CameraPreviewWindow(), ToastWindow()
        self.user_dlg = UserSettingsDialog(self.params)
        self.dev_dlg = DeveloperSettingsDialog(self.params)
        for w in (self.hud, self.preview, self.toast):
            w.enable_drag(locked)

        self.hud.userSettingsRequested.connect(lambda: self._open("user"))
        self.hud.developerSettingsRequested.connect(lambda: self._open("dev"))
        self.hud.quitRequested.connect(self.quitRequested)
        self.user_dlg.applied.connect(self._on_applied)
        self.dev_dlg.applied.connect(self._on_applied)
        self.user_dlg.closed.connect(self._dialog_closed)
        self.dev_dlg.closed.connect(self._dialog_closed)
        self.user_dlg.modeChanged.connect(lambda m: self.hud.set_legend(m, self.params))
        self.hud.moved.connect(lambda p: self._remember("hud_pos", p))
        self.preview.moved.connect(lambda p: self._remember("camera_pos", p))
        self._apply_params()

    # ------------------------------------------------------------ public API for the project
    def show(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w = self.params["windows"]
        self.hud.move(self._pos(w["hud_pos"], QPoint(scr.left() + 24, scr.top() + 24)))
        self.preview.move(self._pos(w["camera_pos"],
                                    QPoint(scr.right() - self.preview.width() - 24, scr.top() + 24)))
        self.hud.show()
        self._update_preview_visibility()

    def set_frame(self, img: QImage):
        self.preview.view.set_frame(img)
        self.dev_dlg.view.set_frame(img)

    def set_mask(self, img: QImage):
        self.dev_dlg.test.set_mask(img)

    def set_fps(self, fps: float):
        self.preview.view.set_fps(fps)
        self.dev_dlg.view.set_fps(fps)

    def set_detection(self, box=None, landmarks=None, confidence=None, label=""):
        """box=(x,y,w,h) and landmarks=[(x,y)..] normalised 0..1 of the frame."""
        for v in (self.preview.view, self.dev_dlg.view):
            v.set_detection(box, landmarks, confidence, label)

    def set_mode(self, mode):
        """'applications' or 'video_player' -> changes what the gesture list shows."""
        self.hud.set_legend(mode, self.params)

    def show_gesture(self, gesture_id, action_text, hold_seconds=None):
        if self.params["general"]["show_confirmation"]:
            self.toast.show_gesture(gesture_id, action_text,
                                    hold_seconds or self.params["detection"]["hold_time"])

    def update_countdown(self, remaining):
        self.toast.set_remaining(remaining)

    def hide_gesture(self):
        self.toast.hide_toast()

    # ------------------------------------------------------------ internals
    @staticmethod
    def _pos(saved, default):
        if saved:
            p = QPoint(*saved)
            for s in QGuiApplication.screens():
                if s.availableGeometry().contains(p):
                    return p
        return default

    def _remember(self, key, pos):
        self.params["windows"][key] = [pos.x(), pos.y()]

    def save_now(self):
        save_parameters(self.params)

    def _open(self, which):
        dlg, other = (self.user_dlg, self.dev_dlg) if which == "user" else (self.dev_dlg, self.user_dlg)
        other.hide()
        dlg.open_dialog()
        self.hud.set_active_item(which)
        self.hud.raise_()
        self._update_preview_visibility()

    def _dialog_closed(self):
        if not (self.user_dlg.isVisible() or self.dev_dlg.isVisible()):
            self.hud.set_menu_open(False)
        self._apply_params()                       # drop un-applied live previews
        self.hud.set_legend(self.hud.mode, self.params)
        self._update_preview_visibility()

    def _on_applied(self, _):
        self._apply_params()
        self.parametersApplied.emit(self.params)

    def _update_preview_visibility(self):
        show = not self.params["general"]["hide_camera"] and not self.dev_dlg.isVisible()
        self.preview.setVisible(show and self.hud.isVisible())

    def _apply_params(self):
        c, d = self.params["camera"], self.params["detection"]
        for v in (self.preview.view, self.dev_dlg.view):
            v.set_options(c["show_fps"], c["show_landmarks"], c["show_hand_box"], d["show_accuracy"])
        self.hud.set_legend(self.hud.mode, self.params)
        self._update_preview_visibility()
