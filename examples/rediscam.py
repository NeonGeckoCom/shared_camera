from shared_camera import RedisCamera
import cv2


print("Redis server needs to be running")
print("Launch this in several terminals, check that you can access camera in multiple python processes")

c = RedisCamera(camera_index=0)  # default is 0, if using a usb its probably 1

while True:
    frame = c.get()

    cv2.imshow("cam", frame)
    cv2.waitKey(1)
