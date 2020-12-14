from shared_camera import ZMQCamera
import cv2

print("Launch this in several terminals, check that you can access camera in multiple python processes")

c = ZMQCamera(camera_index=-1)  # default is 0, if using a usb its probably 1

while True:
    frame = c.get()

    cv2.imshow("cam", frame)
    cv2.waitKey(1)
