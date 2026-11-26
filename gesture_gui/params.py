"""Parameters: defaults + the two small load/save functions (JSON)."""
import copy
import json
import os

PARAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_params.json")

# ---- the 6 supported gestures: 1..5 fingers + closed palm (=10) ----
GESTURES = ["one", "two", "three", "four", "five", "fist"]
GESTURE_NAMES = {
    "one": "One finger", "two": "Two fingers", "three": "Three fingers",
    "four": "Four fingers", "five": "Five fingers", "fist": "Closed palm",
}

DEFAULTS = {
    "general": {
        "show_confirmation": True,   # show gesture confirmation message
        "hide_camera": False,        # hide the small live preview
        "lock_windows": False,       # True = windows locked in place, False = movable
        "show_gesture_map": True,    # gesture map window on / off
    },
    "windows": {"hud_pos": None, "camera_pos": None, "map_pos": None},   # remembered positions [x, y]

    # Applications mode: gesture -> open program
    "applications": [
        {"gesture": "five",  "name": "Chrome",   "path": ""},
        {"gesture": "two",   "name": "Telegram", "path": ""},
        {"gesture": "one",   "name": "Discord",  "path": ""},
        {"gesture": "fist",  "name": "Microsoft Edge", "path": ""},
        {"gesture": "three", "name": "Steam",    "path": ""},
        {"gesture": "four",  "name": "Firefox",  "path": ""},
    ],
    # Video player mode: gesture -> key shortcut
    "video_player": [
        {"gesture": "five",  "key": "Space", "action": "Play / Pause"},
        {"gesture": "one",   "key": "→",     "action": "Seek forward 10s"},
        {"gesture": "two",   "key": "←",     "action": "Seek back 10s"},
        {"gesture": "three", "key": "↑",     "action": "Volume up"},
        {"gesture": "four",  "key": "↓",     "action": "Volume down"},
        {"gesture": "fist",  "key": "F",     "action": "Fullscreen"},
    ],

    # ---- developer settings: only things that exist in classic_detector.py / skinDetect.py ----
    "camera": {
        "index": 0,                                  # cv2.VideoCapture(0)
        "auto_white_balance": False,                 # cap.set(CAP_PROP_AUTO_WB, 0)
        "auto_exposure": False,                      # cap.set(CAP_PROP_AUTO_EXPOSURE, 0.25)
        "show_fps": True, "show_landmarks": True, "show_hand_box": True,   # GUI drawing options
    },
    # classic_detector.py
    "tracking": {
        "blur_kernel": 5,                            # cv2.GaussianBlur(frame, (5, 5), 0)
        "motion_history": 500, "motion_var_threshold": 5,   # createBackgroundSubtractorMOG2(...)
        "seed_dilate": 3, "skin_close": 1, "join_k": 5, "outline_sigma": 3,
        "min_area": 600,                             # MIN_AREA
    },
    # skinDetect.py (SkinDetector arguments)
    "skin": {
        "rebuild_interval": 100,
        "coverage": 0.07, "cov_min": 0.05, "cov_max": 0.40, "step": 0.15,
        "frac_lo": 0.20, "frac_hi": 0.70, "pct_lo": 4, "pct_hi": 94,
    },
}


def _merge(base, over):
    """Defaults overlaid with user values (unknown keys ignored, missing keys filled)."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k not in out:
            continue
        if isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_parameters(path=PARAMS_FILE):
    """Return the user's saved parameters, or the defaults if no/invalid file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
    except (OSError, ValueError):
        return copy.deepcopy(DEFAULTS)
    return _merge(DEFAULTS, user)


def save_parameters(params, path=PARAMS_FILE):
    """Write the parameters dict to the JSON file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(params, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
