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

import uvicorn
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app import App
from errors import ProjectDoesNotExistError, ProjectAlreadyExistsError
from web_ui.api_errors import APIProjectDoesNotExist, APIInvalidDataError, APIProjectAlreadyExists
from web_ui.global_api import router as global_api_router
from web_ui.project_api import router as project_api_router
from web_ui.websocket_api import router as websocket_router

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


@webui_app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    # Put the HTTPException in a JSONResponse
    return JSONResponse(jsonable_encoder(exc.detail), status_code=exc.status_code)


@webui_app.exception_handler(ProjectAlreadyExistsError)
async def project_already_exists_handler(_, exc: ProjectAlreadyExistsError):
    apierror = APIProjectAlreadyExists(name=exc.project_name)
    return JSONResponse(jsonable_encoder(apierror), status_code=APIProjectAlreadyExists.status_code)


@webui_app.exception_handler(ProjectDoesNotExistError)
async def project_does_not_exist_handler(_, exc: ProjectDoesNotExistError):
    apierror = APIProjectDoesNotExist(identifier=exc.project_id)
    return JSONResponse(jsonable_encoder(apierror), status_code=apierror.status_code)


@webui_app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    # Change the FastApi RequestValidationError into an APIInvalidData response
    # This ensures that the frontend can handle this error the same as all other APIErrors
    errors = exc.errors()
    errors_list: list[str] = []

    for error in errors:
        msg = f"The api {error['loc'][0]} parameter '{error['loc'][1]}' is invalid: {error['msg']}"
        errors_list.append(msg)

    details = "\n".join(errors_list)

    if exc.body is not None:
        details += f"\nQuery data:\n{exc.body}"

    apierror = APIInvalidDataError(
        title="Invalid data",
        details=details,
    )
    return JSONResponse(jsonable_encoder(apierror), status_code=apierror.status_code)


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
