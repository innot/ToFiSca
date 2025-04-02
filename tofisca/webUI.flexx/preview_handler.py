from typing import Optional, Awaitable

import cv2 as cv
import tornado.web

from tofisca import ProjectManager


class PreviewHandler(tornado.web.RequestHandler):

    def prepare(self):
        header = "Content-Type"
        body = "image/png"
        self.set_header(header, body)

    async def get(self):
        width = int(self.get_argument('width', '800'))
        counter = int(self.get_argument('counter', None))
        print(f"PreviewHandler get() called with width={width} and counter={counter}")

        img = ProjectManager.active_project.current_frame_image

        if img is None:
            await ProjectManager.active_project.new_image()
            img = ProjectManager.active_project.current_frame_image

        h, w, _ = img.shape
        if w != width:
            aspect = h / w
            height = round(width * aspect)
            img = cv.resize(img, (width, height), interpolation=cv.INTER_AREA)

        # convert to png
        retval, buffer = cv.imencode('.png', img)

        self.write(buffer.tobytes())
        await self.flush()
        await self.finish()
        print(f"Previewhandler for counter {counter} finished")

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        # handling of streamed input is not used
        pass
