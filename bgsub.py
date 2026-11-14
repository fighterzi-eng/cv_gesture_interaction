import cv2
import numpy as np


class FrozenBackground:
  

    def __init__(self, alpha=0.01, diff_thresh=20, protect_k=31, median_k=5):
        self.alpha = alpha                  # adaptation speed outside the hand
        self.diff_thresh = diff_thresh      # color difference that counts as changed
        self.median_k = median_k            # odd; removes isolated motion specks
        self._k_protect = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (protect_k, protect_k))
        self._bg = None

    @property
    def ready(self):
        return self._bg is not None

    def reset(self, frame=None):

        self._bg = None if frame is None else frame.astype(np.float32)

    def apply(self, frame, hand_mask=None):
   
        cur = frame.astype(np.float32)
        if self._bg is None:
            self._bg = cur.copy()

        # 1. foreground = where the frame differs from the clean background
        diff = np.abs(cur - self._bg).max(axis=2)
        motion = (diff > self.diff_thresh).astype(np.uint8) * 255
       

        # 2. freeze the background around the last known hand
        if hand_mask is None:
            protected = np.zeros(frame.shape[:2], np.uint8)
        else:
            protected = cv2.dilate(hand_mask, self._k_protect)

        # 3. update everywhere else
        cv2.accumulateWeighted(cur, self._bg, self.alpha,
                               mask=cv2.bitwise_not(protected))
        return motion, protected