from shared_camera import Camera
import cv2

c = Camera(camera_index=0)  # default is 0, if using a usb its probably 1

print("Launch this in several terminals, check that you can NOT access camera "
      "in multiple python processes")
print("Once the process handling camera dies another should takeover, "
      "for an actual shared camera try RedisCamera or ZMQCamera")
while True:
    frame = c.get()

    cv2.imshow("cam", frame)
    cv2.waitKey(1)
