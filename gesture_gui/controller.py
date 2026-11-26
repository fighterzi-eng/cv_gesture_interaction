"""GestureGui: creates all windows and wires them to the parameters.
This is the only object the rest of the project needs to talk to."""
from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage

from dev_settings import DeveloperSettingsDialog
from overlay import CameraPreviewWindow, GestureMapWindow, HudWindow, ToastWindow
from params import load_parameters, save_parameters
from user_settings import UserSettingsDialog


class GestureGui(QObject):
    parametersApplied = Signal(dict)     # emitted after Apply / Reset (params already saved to json)
    quitRequested = Signal()

    def __init__(self, params=None):
        super().__init__()
        self.params = params or load_parameters()      # user json if present, else defaults
        locked = lambda: self.params["general"]["lock_windows"]

        self.hud, self.gmap = HudWindow(), GestureMapWindow()
        self.preview, self.toast = CameraPreviewWindow(), ToastWindow()
        self.user_dlg = UserSettingsDialog(self.params)
        self.dev_dlg = DeveloperSettingsDialog(self.params)
        for w in (self.hud, self.gmap, self.preview, self.toast):
            w.enable_drag(locked)

        self.hud.userSettingsRequested.connect(lambda: self._open("user"))
        self.hud.developerSettingsRequested.connect(lambda: self._open("dev"))
        self.hud.quitRequested.connect(self.quitRequested)
        self.user_dlg.applied.connect(self._on_applied)
        self.dev_dlg.applied.connect(self._on_applied)
        self.user_dlg.closed.connect(self._dialog_closed)
        self.dev_dlg.closed.connect(self._dialog_closed)
        self.user_dlg.modeChanged.connect(lambda m: self.gmap.set_legend(m, self.params))
        self.hud.moved.connect(lambda p: self._remember("hud_pos", p))
        self.preview.moved.connect(lambda p: self._remember("camera_pos", p))
        self.gmap.moved.connect(lambda p: self._remember("map_pos", p))
        self._backend = None
        self._apply_params()

    # ------------------------------------------------------------ public API for the project
    def show(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w = self.params["windows"]
        self.hud.move(self._pos(w["hud_pos"], QPoint(scr.left() + 24, scr.top() + 24)))
        self.preview.move(self._pos(w["camera_pos"],
                                    QPoint(scr.right() - self.preview.width() - 24, scr.top() + 24)))
        self.gmap.move(self._pos(w["map_pos"], QPoint(scr.left() + 24, scr.top() + 24 + 80)))
        self.hud.show()
        self._update_map_visibility()
        self._update_preview_visibility()

    def set_frame(self, img: QImage):
        self.preview.view.set_frame(img)
        self.dev_dlg.view.set_frame(img)

    def set_mask(self, img: QImage):
        """Hand mask only (kept for compatibility)."""
        self.dev_dlg.test.set_masks(hand=img)

    def set_masks(self, skin=None, motion=None, hand=None):
        """The three black/white views of classic_detector: skin, motion (seed), hand mask."""
        self.dev_dlg.test.set_masks(skin, motion, hand)

    def set_test_status(self, text: str):
        self.dev_dlg.test.set_status(text)

    def set_fps(self, fps: float):
        self.preview.view.set_fps(fps)
        self.dev_dlg.view.set_fps(fps)

    def set_shapes(self, contours=None, lines=None, points=None):
        """Hand outline / hull lines / points, normalised 0..1 (drawn like classic_detector.py)."""
        for v in (self.preview.view, self.dev_dlg.view):
            v.set_shapes(contours, lines, points)

    def set_detection(self, box=None, landmarks=None, confidence=None, label=""):
        """box=(x,y,w,h) and landmarks=[(x,y)..] normalised 0..1 of the frame."""
        for v in (self.preview.view, self.dev_dlg.view):
            v.set_detection(box, landmarks, confidence, label)

    def set_mode(self, mode):
        """'applications' or 'video_player' -> changes what the gesture list shows."""
        self.gmap.set_legend(mode, self.params)

    def show_gesture(self, gesture_id, action_text, hold_seconds):
        if self.params["general"]["show_confirmation"]:
            self.toast.show_gesture(gesture_id, action_text, hold_seconds)

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
        self._update_preview_visibility()

    def _on_applied(self, _):
        self._apply_params()
        self.parametersApplied.emit(self.params)

    def _update_map_visibility(self):
        on = self.params["general"]["show_gesture_map"]
        self.gmap.setVisible(on and self.hud.isVisible())

    def _update_preview_visibility(self):
        show = not self.params["general"]["hide_camera"] and not self.dev_dlg.isVisible()
        self.preview.setVisible(show and self.hud.isVisible())

    def _apply_params(self):
        c = self.params["camera"]
        for v in (self.preview.view, self.dev_dlg.view):
            v.set_options(c["show_fps"], c["show_landmarks"], c["show_hand_box"])
        if self._backend:
            self._apply_backend()
        self.gmap.set_legend(self.gmap.mode, self.params)
        self._update_map_visibility()
        self._update_preview_visibility()

    # ------------------------------------------------------------ calls into skinDetect.py / classic_detector.py
    def start_backend(self):
        """Feed the GUI by calling the functions that already exist in the two backend files:
        SkinDetector.process, classic_detector.clean_hand_contour and smooth_contour.
        Their files stay untouched; they are imported from this folder or the folder above it."""
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import cv2
        import classic_detector
        from skinDetect import SkinDetector
        from widgets import bgr_to_qimage, gray_to_qimage
        self._backend = dict(cv2=cv2, cd=classic_detector, skin=SkinDetector(), cap=None, cam=None,
                             bs=None, bs_key=None, t=time.time(), fps=0.0,
                             to_img=(bgr_to_qimage, gray_to_qimage))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._backend_frame)
        self._apply_backend()
        self._timer.start(1)

    def stop_backend(self):
        if self._backend and self._backend["cap"]:
            self._backend["cap"].release()

    def _apply_backend(self):
        b, p = self._backend, self.params
        cv2, cd, sd = b["cv2"], b["cd"], b["skin"]
        t, s, c = p["tracking"], p["skin"], p["camera"]
        # classic_detector.py constants and the kernels it builds from them
        cd.SEED_DILATE, cd.SKIN_CLOSE, cd.JOIN_K = t["seed_dilate"], t["skin_close"], t["join_k"]
        cd.OUTLINE_SIGMA, cd.MIN_AREA = t["outline_sigma"], t["min_area"]
        ell = lambda n: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))
        cd.K_SEED, cd.K_SKIN, cd.K_JOIN = ell(cd.SEED_DILATE), ell(cd.SKIN_CLOSE), ell(cd.JOIN_K)
        k = max(1, int(t["blur_kernel"]))
        b["blur"] = k if k % 2 else k + 1
        key = (t["motion_history"], t["motion_var_threshold"])
        if key != b["bs_key"]:
            b["bs_key"] = key
            b["bs"] = cv2.createBackgroundSubtractorMOG2(history=key[0], varThreshold=key[1],
                                                         detectShadows=False)
        # skinDetect.py SkinDetector arguments
        sd.rebuild_interval = s["rebuild_interval"]
        sd.coverage, sd.cov_min, sd.cov_max, sd.step = s["coverage"], s["cov_min"], s["cov_max"], s["step"]
        sd.frac_lo, sd.frac_hi, sd.pct_lo, sd.pct_hi = s["frac_lo"], s["frac_hi"], s["pct_lo"], s["pct_hi"]
        cam = (c["index"], c["auto_white_balance"], c["auto_exposure"])
        if cam != b["cam"]:
            b["cam"] = cam
            if b["cap"]:
                b["cap"].release()
            b["cap"] = cv2.VideoCapture(c["index"])
            b["cap"].set(cv2.CAP_PROP_AUTO_WB, 1 if c["auto_white_balance"] else 0)
            b["cap"].set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if c["auto_exposure"] else 0.25)

    def _backend_frame(self):
        """One pass of the classic_detector.main() loop; results go to the GUI."""
        b = self._backend
        cv2, cd = b["cv2"], b["cd"]
        if not b["cap"] or not b["cap"].isOpened():
            return
        ok, frame = b["cap"].read()
        if not ok:
            return
        to_img, to_gray = b["to_img"]
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        blur = cv2.GaussianBlur(frame, (b["blur"], b["blur"]), 0)
        skin, _ = b["skin"].process(blur)                                      # skinDetect.py
        seed = cv2.dilate(b["bs"].apply(blur, learningRate=-1), cd.K_SEED)
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, cd.K_SKIN)
        combined = cv2.morphologyEx(cv2.bitwise_and(skin, seed), cv2.MORPH_CLOSE, cd.K_SKIN)
        mask = cd.clean_hand_contour(combined)                                 # classic_detector.py
        self.set_frame(to_img(frame))
        self.set_masks(to_gray(skin), to_gray(seed), to_gray(mask))

        contours, lines, pts, found, biggest = [], [], [], 0, 0
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for cnt in cnts:
            area = cv2.contourArea(cnt)
            biggest = max(biggest, area)
            if area < cd.MIN_AREA:
                continue
            found += 1
            cnt = cd.smooth_contour(cnt, cd.OUTLINE_SIGMA)                     # classic_detector.py
            contours.append([(q[0][0] / w, q[0][1] / h) for q in cnt])
            M = cv2.moments(cnt)
            if M["m00"] <= 0:
                continue
            cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
            pts.append(((cx / w, cy / h), "centroid"))
            hull = cv2.convexHull(cnt, returnPoints=False)
            try:
                defects = cv2.convexityDefects(cnt, hull) if len(hull) > 3 else None
            except cv2.error:
                defects = None
            for s_, e_, f_, d_ in (defects.reshape(-1, 4) if defects is not None else []):
                if d_ / 256.0 < 5:
                    continue
                st, en, far = cnt[s_][0], cnt[e_][0], cnt[f_][0]
                if st[1] > cy or en[1] > cy:
                    continue
                lines.append(((st[0] / w, st[1] / h), (en[0] / w, en[1] / h)))
                pts += [((far[0] / w, far[1] / h), "far"), ((st[0] / w, st[1] / h), "tip"),
                        ((en[0] / w, en[1] / h), "tip")]
        self.set_shapes(contours, lines, pts)
        now = time.time()
        b["fps"] = 0.9 * b["fps"] + 0.1 / max(now - b["t"], 1e-3)
        b["t"] = now
        self.set_fps(b["fps"])
        self.set_test_status(f"{found} hand blob(s) found" if found else
                             f"no hand: biggest blob {int(biggest)} < MIN_AREA {cd.MIN_AREA}")
