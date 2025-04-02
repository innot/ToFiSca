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

import logging
from enum import Enum
from typing import Union

import uvicorn
from fastapi import FastAPI, status, HTTPException
from pydantic import BaseModel, Field

from film_specs import FilmFormat, FilmSpecs
from project_manager import ProjectManager
from .senditem_websocket import router as websocket_router

#@asynccontextmanager
#async def lifespan(app: FastAPI):
#    yield


webui_app = FastAPI()

webui_app.include_router(websocket_router)


class Tags(Enum):
    GLOBAL = "global"
    GLOBAL_SETTING = "Global Setting"
    PROJECT_SETTING = "Project Setting"
    CAMERA = "camera"
    WEBSOCKET = "websocket"




class ProjectSetupState(BaseModel):
    scanAreaSet: bool = False
    perforationLocationSet: bool = False
    cameraSet: bool = False
    whiteBalanceSet: bool = False
    pathsSet: bool = False
    nameSet: bool = False



class ProjectStateType(Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"


class ProjectState(BaseModel):
    current_frame: int = Field(0, ge=1)
    last_scanned_frame: int = Field(0, ge=1)
    last_processed_frame: int = Field(0, ge=1)
    state: ProjectStateType = Field(ProjectStateType.NOT_STARTED)


class Error(BaseModel):
    msg: str = ""


@webui_app.get("/api/allprojects",
               tags=[Tags.GLOBAL])
async def get_all_projects() -> dict[str, int]:
    all_projects = ProjectManager.list_projects()
    return AllProjects().all

@webui_app.get("/api/filmformats/all",
               tags=[Tags.GLOBAL])
async def get_all_filmformats() -> list[FilmFormat]:
    return FilmSpecs.get_api_film_formats()

@webui_app.get("/api/project/setup_state",
               tags=[Tags.PROJECT_SETTING])
async def get_project_setup_state() -> ProjectSetupState:
    # todo: actual implementation
    return ProjectSetupState()


@webui_app.get("/api/project/id",
               tags=[Tags.PROJECT_SETTING])
async def get_project_id() -> ProjectId:
    # todo: actual implementation
    return ProjectId(id=4)


@webui_app.get("/api/project/name",
               tags=[Tags.PROJECT_SETTING])
async def get_project_name() -> ProjectName:
    # todo: actual implementation
    return ProjectName(name="")


@webui_app.put("/api/project/name",
               responses={status.HTTP_409_CONFLICT: {"model": Error},
                          status.HTTP_400_BAD_REQUEST: {"model": Error}},
               tags=[Tags.PROJECT_SETTING])
async def put_project_name(name: ProjectName) -> ProjectName:
    return name


@webui_app.get("/api/project/paths",
               tags=[Tags.PROJECT_SETTING])
async def get_project_paths() -> ProjectPaths:
    return ProjectPaths()


@webui_app.put("/api/project/paths",
               responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
               tags=[Tags.PROJECT_SETTING])
async def update_project_paths(project_paths: ProjectPaths) -> ProjectPaths:
    return project_paths


@webui_app.get("/api/project/filmdata",
               tags=[Tags.PROJECT_SETTING])
async def get_project_filmdata() -> FilmData:
    return FilmData()


@webui_app.put("/api/project/filmdata",
               responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
               tags=[Tags.PROJECT_SETTING])
async def put_project_filmdata(project_metadata: FilmData) -> FilmData:
    return project_metadata


@webui_app.get("/api/project/state",
               tags=[Tags.PROJECT_SETTING])
async def get_project_state() -> ProjectState:
    return ProjectState(current_frame=0, last_scanned_frame=0, last_processed_frame=0,
                        state=ProjectStateType.NOT_STARTED)


@webui_app.get("/api/project/perf/location",
               responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
               tags=[Tags.PROJECT_SETTING])
async def get_perf_location() -> PerforationLocation:
    #        return JSONResponse(status_code=404, content={Error("Perforation location not set")})

    # todo: actual implementation
    return PerforationLocation(top_edge=0.4, bottom_edge=0.6, inner_edge=0.3, outer_edge=0.15,
                               reference=Point(x=0.3, y=0.5))


@webui_app.put("/api/project/perf/location",
               tags=[Tags.PROJECT_SETTING],
               )
async def put_perf_location(perf_location: PerforationLocation) -> PerforationLocation:
    # todo: actual implementation
    print(f"/api/perf/location POST: {perf_location}")
    return perf_location


@webui_app.post("/api/project/perf/detect",
                responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
                tags=[Tags.PROJECT_SETTING]
                )
async def post_perfdetect(startpoint: Point) -> PerforationLocation:
    # todo: actual implementation
    print(f"/api/perf/detect GET: {startpoint}")
    if not startpoint:
        msg = f"Could not detect perforation hole{' at the given point' if startpoint else ''}"
        raise HTTPException(404, msg)

    return PerforationLocation(top_edge=0.4, bottom_edge=0.6, inner_edge=0.3, outer_edge=0.15,
                               reference=Point(x=0.3, y=0.5))


@webui_app.get("/api/project/scanarea",
               responses={status.HTTP_404_NOT_FOUND: {"model": Error}},
               tags=[Tags.PROJECT_SETTING])
async def get_scanarea() -> ScanArea:
    """
    Get the camera Scanarea, the area that defines the film frame content to be used.
    All values are normalized (ref_delta: between -1 and 1, size: between 0 and 1) and
    independent of the select camera image resolution.
    """
    # todo: actual implementation
    scanarea = ScanArea(ref_delta=OffsetPoint(dx=0.3, dy=0.5), size=Size(width=0.7, height=0.5))
    return scanarea


@webui_app.put("/api/project/scanarea",
               tags=[Tags.PROJECT_SETTING],
               )
async def put_scanarea(scanarea: ScanArea) -> ScanArea:
    """
    Set the ScanArea, the area that defines the film frame content to be used.
    All values are normalized (between 0 and 1) to be independent of the select camera image resolution.
        - ref_delta: The delta between the Perforation reference point and the top left point of the scan area.
        - size: The size of the scan area.
    """
    print(f"/api/scanarea POST: {scanarea}")
    return scanarea


async def run_webui_server():
    port = 80  # todo: make port configurable

    config = uvicorn.Config(webui_app, port=port, log_level="info")
    server = uvicorn.Server(config)
    logging.info(f"WebUI server started on port {port}")
    await server.serve()
    logging.info("WebUI server stopped")


if __name__ == "__main__":
    uvicorn.run(webui_app, port=8000)
