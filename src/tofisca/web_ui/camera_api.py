#  This file is part of the ToFiSca application.
#
#  ToFiSca is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  ToFiSca is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with ToFiSca.  If not, see <http://www.gnu.org/licenses/>.
#
#  Copyright (c) 2025 by Thomas Holland, thomas@innot.de
#
import asyncio
import io
import logging

from PIL import Image
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from camera_manager import CameraManager, VideoStreamOutput
from project import Project
from web_ui import Tags
from web_ui.api_errors import APINoActiveProject

try:
    from picamera2.encoders import JpegEncoder
except ImportError:
    from mock_picamera2.encoders import JpegEncoder

logger = logging.getLogger(__name__)


def get_camera_manager() -> CameraManager:
    """
    Get the CameraManager from the running Application.
    """
    from web_ui.server import get_app
    app = get_app()
    return app.camera_manager


async def get_active_project() -> Project:
    """
    Get the currently active project.
    :raises HTTPException: An HTTP_404_NOT_FOUND exception if no active project exists.
    """
    from web_ui.server import get_app
    app = get_app()

    active_project = await app.project_manager.active_project
    if not active_project:
        raise HTTPException(status_code=APINoActiveProject.status_code,
                            detail=APINoActiveProject())
    return active_project


router = APIRouter()


@router.get("/api/camera/preview",
            responses={200: {"content": {"image/png": {}}}},
            tags=[Tags.CAMERA], )
async def get_camera_preview(reload: bool = False) -> Response:
    cm = get_camera_manager()
    image_data = await cm.get_preview_image(reload=reload)
    image = Image.fromarray(image_data)

    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return Response(content=stream.getvalue(), media_type="image/png",
                    headers={"Cache-control": "no-cache"})


async def video_stream(stream: VideoStreamOutput, cm: CameraManager):
    """
    Wait for new images from the stream, add the multipart headers, and yield them to the StreamResponse.
    Once the connection is closed, the CameraManager is informed to stop streaming.

    :param stream: The stream supplying new images.
    :param cm: The CameraManager
    :return:
    """
    try:
        while True:
            with stream.condition:
                stream.condition.wait()
                frame = stream.frame

                body = b'---frame\r\n'
                body += b'Content-Type: image/jpeg\r\n'
                body += str.encode(f"Content-Length: {len(frame)}\r\n")
                body += b'\r\n'
                body += frame
                body += b'\r\n'

                yield body
                await asyncio.sleep(0)  # hand control to the event_loop to receive CancelledError
    except asyncio.CancelledError:
        cm.stop_streaming()
        logger.debug("Live Stream Client disconnected")


class MJPEGStreamingResponse(StreamingResponse):
    media_type = "multipart/x-mixed-replace; boundary=---frame"


@router.get("/api/camera/live",
            response_class=MJPEGStreamingResponse,
            tags=[Tags.CAMERA], )
async def get_camera_live() -> MJPEGStreamingResponse:
    """Start a stream with MJPEG images."""
    logger.debug("Live Stream Client connected")
    cm = get_camera_manager()
    encoder = JpegEncoder()
    output = cm.start_streaming(encoder)
    response = MJPEGStreamingResponse(video_stream(output, cm),
                                      headers={
                                          "Cache-control": "no-cache, private",
                                          "Pragma": "no-cache",
                                          "Age": "0"}
                                      )
    return response
