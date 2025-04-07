import asyncio
import io
import threading

import cv2 as cv
import numpy as np
import tornado.web

from tofisca import ProjectManager


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = threading.Condition()

    def write(self, image_data):
        if image_data.startswith(b'\xff\xd8'):
            print("StreamingHandler.write: received start of new frame")
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                print(f"StreamingHandler.write: copied {len(self.frame)} to buffer. {self.frame}")
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(image_data)

    def finish(self):
        with self.condition:
            self.frame = None
            self.condition.notify_all()


class LiveStreamHandler(tornado.web.RequestHandler):
    stream_buffer = None
    camera_manager = None

    def initialize(self):
        project = ProjectManager.active_project
        self.camera_manager = project.camera_manager

    def prepare(self):
        if self.stream_buffer is None:
            self.stream_buffer = StreamingOutput()

    async def get(self):
        width = int(self.get_argument('width', '800'))
        height = int(self.get_argument('height', '600'))

        print(f"LiveStreamHandler get() with size {width}/{height}")

        self.camera_manager.start_streaming(self.stream_buffer, (width, height))

        self.set_header('Cache-Control', 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0')
        self.set_header('Connection', 'close')
        self.set_header('Content-Type', 'multipart/x-mixed-replace;boundary=--boundarydonotcross')
        self.set_header('Expires', 'Mon, 3 Jan 2000 12:34:56 GMT')
        self.set_header('Pragma', 'no-cache')

        my_boundary = "--boundarydonotcross\n"

        #        self.served_image_timestamp = time.time()
        try:
            while True:
                print("LiveStreamHandler: Loop")
                frame = await self.get_image_buffer()
                if frame is None:
                    print("LiveStreamHandler: get : None-Frame exit")
                    return
                if len(frame) == 0:  # buffer empty, skip and wait for next frame
                    continue

                self.write(my_boundary)
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % len(frame))
                self.write(frame)
                print("LiveStreamHandler: get: frame written")
                await self.flush()
                await asyncio.sleep(0.01)   # give the server some time to handle other stuff
        except Exception as e:
            # Connection dropped
            print(f"Livestreamhandler loop stopped with exception {str(e)}")
            self.camera_manager.stop_streaming()
            return

    def on_connection_close(self) -> None:
        print("LiveStreamHandler: on_connection_close")
        self.camera_manager.stop_streaming()

    def on_finish(self):
        print("LiveStreamHandler: on_finish")

        # self.stream_buffer = None

    async def get_image_buffer(self):
        with self.stream_buffer.condition:
            self.stream_buffer.condition.wait(2)
            frame = self.stream_buffer.frame
        return frame

    def data_received(self, chunk: bytes):
        # handling of streamed input is not used
        pass
