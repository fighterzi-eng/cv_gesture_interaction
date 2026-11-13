# main.py
import cv2
import numpy as np

from skinDetect import SkinDetector

cap = cv2.VideoCapture(0)
detector = SkinDetector(rebuild_interval=60)
#note toself tone down the dilation or use  closing

while True:
    ret, frame = cap.read()
    # frame=cv2.imread("images.jpeg")

    frame = cv2.flip(frame, 1)

    mask, params = detector.process(frame)

    cv2.imshow("frame", frame)
    cv2.imshow("skin", mask)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()