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
import logging
from enum import Enum

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app import App
from .global_api import router as global_api_router
from .project_api import router as project_api_router
from .senditem_websocket import router as websocket_router

logger = logging.getLogger(__name__)

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#    yield

_app: App | None = None

def get_app():
    global _app
    return _app

def set_app(app: App):
    global _app
    _app = app


webui_app = FastAPI()

webui_app.include_router(global_api_router)
webui_app.include_router(project_api_router)
webui_app.include_router(websocket_router)


async def run_webui_server(app: App):

    set_app(app)

    port = 80  # todo: make port configurable

    config = uvicorn.Config(webui_app, port=port, log_level="info")
    server = uvicorn.Server(config)
    logger.info(f"WebUI server started on port {port}")

    task_server = asyncio.create_task(server.serve())
    task_shutdown = asyncio.create_task(app.shutdown_event.wait())

    for fut in asyncio.as_completed([task_server, task_shutdown]):
        await fut  # avoid pending futures
        # as the server should not shut down on its own, it is propably a shutdown event
        server.should_exit = True

    logger.info("WebUI server stopped")


if __name__ == "__main__":
    uvicorn.run(webui_app, port=8000)
