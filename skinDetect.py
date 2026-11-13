# skin_detector.py
import cv2
import numpy as np

class SkinDetector:

    #Dynamic YCbCr skin detector based on Brancati et al.'s trapezoidal model.

    CR_MIN = 137          # fixed lower bound for Cr
    CB_MAX = 126          # fixed upper bound for Cb

    def __init__(self, rebuild_interval=60,pct_lo=1, pct_hi=98, coverage=0.12):
        self.rebuild_interval = rebuild_interval
        self.pct_lo = pct_lo
        self.pct_hi = pct_hi
        self.coverage = coverage
        self.params = None
        self._frame = 0
        self._kernel = np.ones((9, 9), np.uint8)

    def process(self, bgr):
        #Return (mask, params) for a BGR frame.
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)

        if self.params is None or self._frame % self.rebuild_interval == 0:
            self.params = self._build_params(ycrcb)

        y, cr, cb = cv2.split(ycrcb)
        cr_up, cb_lo = self._thresholds(y, self.params)

        mask = ((cr >= self.CR_MIN) & (cr <= cr_up) &
                (cb >= cb_lo) & (cb <= self.CB_MAX)).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=3)

        self._frame += 1
        return mask, self.params

    # -------- internals --------
    def _build_params(self, ycrcb):
        y, cr, cb = cv2.split(ycrcb)
        total = y.size

        # Cr_max: highest Cr in [133,183] covering >= coverage of pixels
        vals = cr[(cr >= 133) & (cr <= 183)]
        if vals.size == 0:
            cr_max = 173
        else:
            h, _ = np.histogram(vals, bins=256, range=(0, 256))
            idx = np.searchsorted(np.cumsum(h[::-1]), self.coverage * total)
            cr_max = int(np.clip(255 - idx if idx < len(h) else 183, 133, 183))

        # Cb_min: lowest Cb in [77,128] covering >= coverage of pixels
        vals = cb[(cb >= 77) & (cb <= 128)]
        if vals.size == 0:
            cb_min = 77
        else:
            h, _ = np.histogram(vals, bins=256, range=(0, 256))
            idx = np.searchsorted(np.cumsum(h), self.coverage * total)
            cb_min = int(np.clip(idx if idx < 256 else 128, 77, 128))

        y0, y1 = self._y_percentiles(y, cr, cr_max)
        y2, y3 = self._y_percentiles(y, cb, cb_min)

        return {"cr_max": cr_max, "cb_min": cb_min,
                "y0": y0, "y1": y1, "y2": y2, "y3": y3}

    def _y_percentiles(self, y, channel, center):
        # sees the values close tto the calculated max
        mask = np.abs(channel.astype(np.int16) - center) <= 2
        ys = y[mask]
        if ys.size < 10:
            return 80, 180
        lo = int(np.percentile(ys, self.pct_lo))
        hi = int(np.percentile(ys, self.pct_hi))
        return (lo, hi) if hi > lo else (80, 180)

    def _thresholds(self, y_channel, p):
        Y = y_channel.astype(np.float32)
        cr_max, cb_min = float(p["cr_max"]), float(p["cb_min"])
        y0, y1 = float(p["y0"]), float(p["y1"])
        y2, y3 = float(p["y2"]), float(p["y3"])
        cr_min, cb_max = float(self.CR_MIN), float(self.CB_MAX)
        d_cr, d_cb = cr_max - cr_min, cb_max - cb_min

        cr_up = np.where(
            Y < y0, cr_min + d_cr * Y / max(y0, 1.0),
            np.where(Y <= y1, cr_max,
                     cr_max - d_cr * (Y - y1) / max(255.0 - y1, 1.0)))

        cb_lo = np.where(
            Y < y2, cb_max - d_cb * Y / max(y2, 1.0),
            np.where(Y <= y3, cb_min,
                     cb_min + d_cb * (Y - y3) / max(255.0 - y3, 1.0)))

        return cr_up, cb_lo