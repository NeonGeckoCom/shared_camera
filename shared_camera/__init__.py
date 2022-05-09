# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os

# disable excessive opencv logging, needs to be set before import cv2
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import cv2
import struct
import numpy as np
from os.path import join, dirname
from imutils.video import VideoStream
import threading
import imagezmq
from zmq.error import ZMQError


class Camera:
    """
    Camera interface that can be instantiated multiple times, keeps trying
    to access camera until it succeeds
    """
    _stock = join(dirname(__file__), "no_feed.jpg")

    def __init__(self, camera_index=0, autotakeover=False,
                 name="shared_camera"):
        self.stream = None
        self._last_frame = cv2.imread(self._stock)
        self._prev_fame = None
        self.controlling_camera = False
        self.camera_index = camera_index
        self.autotakeover = autotakeover
        self.name = name
        self.maybe_takeover()

    def _transmit(self, frame):
        return None

    def _receive(self):
        raise TimeoutError

    def get(self):
        # convenience
        return self.read()

    def get_frame(self):
        # convenience
        return self.read()

    def read(self):
        try:
            self._prev_fame = self._last_frame.copy()
            if self.controlling_camera:
                self._last_frame = self.stream.read()
                self._transmit(self._last_frame)
            else:
                self._last_frame = self._receive()
        except TimeoutError:
            # failed to receive frame
            if self.autotakeover:
                self.maybe_takeover()
        return self._last_frame

    def maybe_takeover(self):
        # naively keep trying to grab cam
        self.open_camera()

    def open_camera(self):
        if self.stream is None:
            self.stream = VideoStream(self.camera_index)
            if self.stream.stream.grabbed:
                self.controlling_camera = True
                self.stream.start()
            else:
                self.controlling_camera = False
                self.stream = None

    def stop(self):
        if self.stream:
            self.stream.stop()


class RedisCamera(Camera):
    """
    Camera interface that can be instantiated multiple times, frames are
    brokered by redis server (needs to be running in host!)
    """

    def __init__(self, camera_index=0, autotakeover=True,
                 name="shared_camera", host="127.0.0.1", port=6379):
        # Redis connection
        import redis
        self.r = redis.Redis(host=host, port=port)
        self.r.ping()
        super().__init__(camera_index, autotakeover, name)

    def _transmit(self, frame):
        """Store given Numpy array 'a' in Redis under key 'n'"""
        h, w = frame.shape[:2]
        shape = struct.pack('>II', h, w)
        encoded = shape + frame.tobytes()
        # Store encoded data in Redis
        self.r.set(self.name, encoded)
        return

    def _receive(self):
        """Retrieve Numpy array from Redis key 'n'"""
        encoded = self.r.get(self.name)
        h, w = struct.unpack('>II', encoded[:8])
        a = np.frombuffer(encoded, dtype=np.uint8, offset=8).reshape(h, w, 3)
        return a

    def read(self):
        if self.autotakeover and not self.controlling_camera:
            # redis doesnt raise the timeout used to trigger this
            # just try all the time
            self.maybe_takeover()
        return super(RedisCamera, self).read()


class ZMQVideoStreamSubscriber:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._stop = False
        self._data_ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=())
        self._thread.daemon = True
        self._thread.start()

    @property
    def url(self):
        return "tcp://{}:{}".format(self.host, self.port)

    def receive(self, timeout=1.0):
        flag = self._data_ready.wait(timeout=timeout)
        if not flag:
            raise TimeoutError(
                "Timeout while reading from subscriber {url}".format(
                    url=self.url))
        self._data_ready.clear()
        return self._data

    def _run(self):
        receiver = imagezmq.ImageHub(self.url, REQ_REP=False)
        while not self._stop:
            self._data = receiver.recv_image()
            self._data_ready.set()
        receiver.close()

    def close(self):
        self._stop = True


class ZMQCamera(Camera):
    """
    Camera interface that can be instantiated multiple times,
    instance takes over as frame broker if needed
    """

    def __init__(self, camera_index=0, autotakeover=True,
                 name="shared_camera", host="127.0.0.1", port=5555):
        self.port = port
        self.host = host
        self.sender = None
        self.receiver = None
        super().__init__(camera_index, autotakeover, name)

    @property
    def url(self):
        return 'tcp://{host}:{port}'.format(host=self.host, port=self.port)

    def _transmit(self, frame):
        """Store given Numpy array 'a' in Redis under key 'n'"""
        if self.sender is not None:
            self.sender.send_image(self.name, frame)

    def _receive(self):
        """Retrieve Numpy array from Redis key 'n'"""
        if self.receiver is not None:
            msg, image = self.receiver.receive()
            if self.name == msg:
                return image
        return self._last_frame

    def maybe_takeover(self):
        # zmq connection
        if self.sender is not None:
            return
        self.open_camera()
        try:
            self.sender = imagezmq.ImageSender(
                'tcp://*:{port}'.format(port=self.port), REQ_REP=False)
        except ZMQError:
            # address already in use
            self.receiver = ZMQVideoStreamSubscriber(self.host, self.port)

    def stop(self):
        if self.receiver is not None:
            self.receiver.close()
        super().stop()
