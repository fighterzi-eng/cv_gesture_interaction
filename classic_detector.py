import cv2
import numpy as np
from skinDetect import SkinDetector
from bgsub import FrozenBackground



SEED_DILATE    = 3     
SKIN_CLOSE = 1     
MIN_AREA       = 600   
OUTLINE_SIGMA  =3
JOIN_K=5   


K_SEED = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SEED_DILATE, SEED_DILATE))
K_SKIN = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (SKIN_CLOSE, SKIN_CLOSE))
K_JOIN = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (JOIN_K, JOIN_K))


def fill_enclosed(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = np.zeros_like(mask)
    cv2.drawContours(out, cnts, -1, 255, thickness=cv2.FILLED)
    return out


def smooth_contour(cnt, sigma):
    """Circular Gaussian smoothing of contour points (removes pixel jaggies)."""
    pts = cnt[:, 0, :].astype(np.float32)
    r = int(3 * sigma)
    if len(pts) <= 2 * r + 2:
        return cnt
    k = cv2.getGaussianKernel(2 * r + 1, sigma).ravel()
    padded = np.concatenate([pts[-r:], pts, pts[:r]])      # wrap around
    x = np.convolve(padded[:, 0], k, mode="valid")
    y = np.convolve(padded[:, 1], k, mode="valid")
    return np.stack([x, y], axis=1).round().astype(np.int32).reshape(-1, 1, 2)


def clean_hand_contour(mask):
    """mask -> (single clean contour or None, cleaned mask)"""
    m = fill_enclosed(mask)                                  # 1. enclosed holes
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, K_JOIN)  # 2. join fragments/notches
    m = fill_enclosed(m)                                     # 3. holes the join created
                      
    m = cv2.medianBlur(m, 3)                                 # 5. de-jag the edge
    
    return  m             


def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)   # V4L2 manual mode
    detector = SkinDetector(rebuild_interval=100,coverage=0.07)
    #backSub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=5, detectShadows=False)
    background = FrozenBackground(alpha=0.01, diff_thresh=20, protect_k=31)
    hand_prev = None 


    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        blur = cv2.GaussianBlur(frame, (5, 5), 0)

        # ---- the two raw cues ----
        skin, _ = detector.process(blur)
        #fg = backSub.apply(blur, learningRate=-1)

        # ---- motion minor preprocessing ----
        motion, protected = background.apply(blur, hand_prev)
        seed = cv2.dilate(motion, K_SEED)
        seed = cv2.bitwise_or(seed, protected) 

        # ---- skin with motion ----
        skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, K_SKIN)
        combined = cv2.bitwise_and(skin, seed)

   
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, K_SKIN)
        combined=clean_hand_contour(combined)
    
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)


        for cnt in contours:
            area = cv2.contourArea(cnt)
            cnt=smooth_contour(cnt,OUTLINE_SIGMA)
            
            if area < MIN_AREA:
                continue  # skip speckle
            hull = cv2.convexHull(cnt,returnPoints = False)
            defects = cv2.convexityDefects(cnt,hull)
 
           
            if defects is not None:
                defects = defects.reshape(-1, 4)      # (N,1,4) or (N,4) -> (N,4)
            for s, e, f, d in defects:
                if d / 256.0 < 5:                 # ignore shallow dents
                    continue
                start=tuple(cnt[s][0]) #start of defect
                end=tuple(cnt[e][0]) # end of defect
                far=tuple(cnt[f][0]) #deepes point in the defect (between fingers)
                cv2.line(frame, start,end, (255, 255, 0), 2)
                cv2.circle(frame, far, 5, (0, 0, 255), -1)
                cv2.circle(frame, start, 10, (125, 0, 255), -1)
                cv2.circle(frame, end, 10, (125, 0, 255), -1)
            

            cv2.drawContours(frame, [cnt], -1, (0, 255, 0), 3)




        # ---- one clean contour ----
     

        out = frame.copy()
       

        cv2.imshow("frame", out)
        cv2.imshow("skin", skin)
        cv2.imshow("seed (motion)", seed)
     
        cv2.imshow("hand_mask", combined)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()