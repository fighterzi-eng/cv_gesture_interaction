import cv2
from skinDetect import SkinDetector
#i need to play more with morphological operators to see what fits best
#need to find a way to delay the decaying of the hand due to low movment (maybe reducing the threshold and relying on natural movment aka breathing and shaaking) or dump the background idea
# after achieving a stable mask contours will be used with hull convexity detection to find fingertips from which we can map limited action before the model 
#or as the plan use it ensure hand prescense per frame 
cap = cv2.VideoCapture(0)
detector = SkinDetector(rebuild_interval=60)
backSub = cv2.createBackgroundSubtractorMOG2(
    history=500, varThreshold=8, detectShadows=False)


k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)          


    fgMask = backSub.apply(frame, learningRate=-1)
    skinMask, params = detector.process(frame)
    fgMask_med = cv2.medianBlur(fgMask, 9)


    
    fgMask_clean = cv2.morphologyEx(fgMask_med, cv2.MORPH_DILATE, k3)

 
    combined = cv2.bitwise_and(skinMask, fgMask_clean)

   
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k3)

    cv2.imshow("frame",    frame)
    cv2.imshow("skin",     skinMask)
    cv2.imshow("movement", fgMask)
    cv2.imshow("combined", combined)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()