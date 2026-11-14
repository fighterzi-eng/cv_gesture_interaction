import cv2
import numpy as np
from collections import deque
from scipy.signal import find_peaks
from skinDetect import SkinDetector

# ---------------- parameters ----------------
SEED_DILATE = 3      
SKIN_CLOSE  = 3      
JOIN_K      = 5      
MIN_AREA    = 600    # ignore blobs smaller than this

SMOOTH_SIGMA = 3     # smoothing of the distance signal
MIN_REACH    = 1.5   # a tip must be this many palm radii from the palm center
PROMINENCE   = 0.4   # and stick out this many palm radii above its valleys

K_SEED = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SEED_DILATE, SEED_DILATE))
K_SKIN = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SKIN_CLOSE, SKIN_CLOSE))
K_JOIN = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (JOIN_K, JOIN_K))


# ---------------- mask cleanup ----------------
def fill_enclosed(mask):
    """Fill holes that are completely surrounded by the mask."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def clean_hand_mask(mask):
    mask = fill_enclosed(mask)                           # holes inside the hand
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, K_JOIN)  # small cracks
    mask = fill_enclosed(mask)                           # holes created by closing
    return cv2.medianBlur(mask, 3)                       # smooth jagged edges


def largest_contour(mask):
    """The biggest blob above MIN_AREA, or None. Assumed to be the hand."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) >= MIN_AREA]
    return max(contours, key=cv2.contourArea) if contours else None


# ---------------- fingertip detection ----------------
def smooth_circular(signal, sigma):
    radius = int(3 * sigma)
    kernel = cv2.getGaussianKernel(2 * radius + 1, sigma).ravel()
    padded = np.pad(signal, radius, mode="wrap")
    return np.convolve(padded, kernel, mode="valid")


def find_fingertips(contour, mask):
    points = contour.reshape(-1, 2)

    # 1. Palm center = the point deepest inside the hand.
    #    Its distance to the edge is also the palm radius.
    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    _, palm_radius, _, palm_center = cv2.minMaxLoc(dist_map)

    # 2. Distance from every outline point to the palm center.
    distances = np.linalg.norm(points - palm_center, axis=1)

    # 3. Smooth it so pixel noise doesn't create fake peaks.
    distances = smooth_circular(distances, SMOOTH_SIGMA)

    # 4. Peaks of the signal are the fingertips.
    peaks, _ = find_peaks(distances,
                          height=MIN_REACH * palm_radius,
                          prominence=PROMINENCE * palm_radius)

    return points[peaks], palm_center, palm_radius


# ---------------- main loop ----------------
def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # V4L2 manual mode

    detector = SkinDetector(rebuild_interval=10, coverage=0.08)
    back_sub = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=5, detectShadows=False)
    recent_counts = deque(maxlen=7)             # median of last 7 frames

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)

        # two cues: skin color (shape) and motion (which blob is the hand)
        skin, _ = detector.process(blurred)
        motion = back_sub.apply(blurred, learningRate=-1)
        seed = cv2.dilate(cv2.medianBlur(motion, 5), K_SEED)

        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, K_SKIN)
        combined = cv2.bitwise_and(skin, seed)
        hand_mask = clean_hand_mask(combined)

        # find the hand and its fingertips
        out = frame.copy()
        contour = largest_contour(hand_mask)
        if contour is not None:
            tips, center, radius = find_fingertips(contour, hand_mask)
            recent_counts.append(len(tips))

            cv2.drawContours(out, [contour], -1, (0, 255, 0), 2)
            cv2.circle(out, center, int(radius), (255, 255, 0), 1)   # palm circle
            for x, y in tips:
                cv2.circle(out, (int(x), int(y)), 6, (0, 0, 255), -1)
        else:
            recent_counts.append(0)

        cv2.putText(out, f"fingers: {int(np.median(recent_counts))}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        cv2.imshow("frame", out)
        cv2.imshow("skin", skin)
        cv2.imshow("seed (motion)", seed)
        cv2.imshow("hand_mask", hand_mask)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()