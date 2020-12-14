from imutils.video import VideoStream
import cv2
# baseline using opencv
stream = VideoStream()
stream.start()

while True:
    frame = stream.read()

    cv2.imshow("cam", frame)
    cv2.waitKey(1)
