import cv2
import numpy as np
from collections import deque
from scipy.signal import find_peaks
from skinDetect import SkinDetector
from bgsub import FrozenBackground

# ---------------- parameters ----------------
SEED_DILATE  = 5        # how far motion reaches to claim a skin blob
MIN_SEED_PX  = 30       # motion pixels a skin blob needs to count as the hand
SKIN_CLOSE   = 3
JOIN_K       = 7
MASK_KEEP    = 0.6      # temporal averaging: higher = steadier but laggier
MIN_AREA     = 600
HOLD_FRAMES  = 5        # keep the last contour this many frames after losing the hand

SMOOTH_SIGMA = 3
MIN_REACH    = 1.5
PROMINENCE   = 0.4

def kernel(n):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))

K_SEED, K_SKIN, K_JOIN = kernel(SEED_DILATE), kernel(SKIN_CLOSE), kernel(JOIN_K)


# ---------------- mask helpers ----------------
def fill_enclosed(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def grow_from_seed(skin, seed, min_seed):
    """Keep only skin blobs containing enough seed pixels."""
    n, labels = cv2.connectedComponents(skin, connectivity=8)
    counts = np.bincount(labels[seed > 0], minlength=n)
    keep = counts >= min_seed
    keep[0] = False
    return keep[labels].astype(np.uint8) * 255


def clean_hand_mask(mask):
    mask = fill_enclosed(mask)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, K_JOIN)
    mask = fill_enclosed(mask)
    return cv2.medianBlur(mask, 5)


def largest_contour(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) >= MIN_AREA]
    return max(contours, key=cv2.contourArea) if contours else None


# ---------------- fingertips ----------------
def smooth_circular(signal, sigma):
    radius = int(3 * sigma)
    k = cv2.getGaussianKernel(2 * radius + 1, sigma).ravel()
    return np.convolve(np.pad(signal, radius, mode="wrap"), k, mode="valid")


def find_fingertips(contour, mask):
    points = contour.reshape(-1, 2)

    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    row, col = np.unravel_index(np.argmax(dist_map), dist_map.shape)
    center, radius = (int(col), int(row)), float(dist_map[row, col])

    distances = np.linalg.norm(points - np.array(center), axis=1)
    distances = smooth_circular(distances, SMOOTH_SIGMA)
    peaks, _ = find_peaks(distances,
                          height=MIN_REACH * radius,
                          prominence=PROMINENCE * radius,
                          distance=max(5, len(points) // 20))
    return points[peaks], center, radius


# ---------------- main loop ----------------
def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

    detector = SkinDetector(rebuild_interval=10, coverage=0.08)
    background = FrozenBackground(alpha=0.01, diff_thresh=20, protect_k=31)

    hand_prev = None          # last hand mask: latches the hand and freezes the background
    acc = None                # temporally averaged mask
    last = None               # (contour, tips, center, radius), held across short dropouts
    miss = 0
    counts = deque(maxlen=7)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)

        if acc is None:
            acc = np.zeros(frame.shape[:2], np.float32)

        # ---- motion (separate class) ----
        motion, protected = background.apply(blurred, hand_prev)
        seed = cv2.dilate(motion, K_SEED)
        seed = cv2.bitwise_or(seed, protected)       # latch: skin near the old hand stays seeded

        # ---- skin gives the shape; motion picks the blob ----
        skin, _ = detector.process(blurred)
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, K_SKIN)
        grown = grow_from_seed(skin, seed, MIN_SEED_PX)

        # ---- temporal averaging, then cleanup ----
        acc = MASK_KEEP * acc + (1 - MASK_KEEP) * (grown > 0)
        hand_mask = clean_hand_mask((acc > 0.5).astype(np.uint8) * 255)

        # ---- contour + fingertips, with a short hold on dropouts ----
        contour = largest_contour(hand_mask)
        if contour is not None:
            tips, center, radius = find_fingertips(contour, hand_mask)
            last, miss = (contour, tips, center, radius), 0
            hand_prev = hand_mask
        else:
            miss += 1
            if miss > HOLD_FRAMES:
                last, hand_prev = None, None

        out = frame.copy()
        if last is not None:
            contour, tips, center, radius = last
            counts.append(len(tips))
            cv2.drawContours(out, [contour], -1, (0, 255, 0), 2)
            cv2.circle(out, center, int(radius), (255, 255, 0), 1)
            for x, y in tips:
                cv2.circle(out, (int(x), int(y)), 6, (0, 0, 255), -1)
        else:
            counts.append(0)

        cv2.putText(out, f"fingers: {int(np.median(counts))}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("frame", out)
        cv2.imshow("skin", skin)
        cv2.imshow("seed", seed)
        cv2.imshow("hand_mask", hand_mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('b'):                          # recapture background, hand out of view
            background.reset(blurred)
            hand_prev, last, acc[:] = None, None, 0

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()