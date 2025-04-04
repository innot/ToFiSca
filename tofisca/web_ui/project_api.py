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

from fastapi import APIRouter, status, HTTPException
from pydantic import BaseModel
from pydantic_core import ErrorDetails

from app import App
from errors import ProjectAlreadyExistsError
from models import PerforationLocation, Point, ScanArea
from project import Project, ProjectPaths, FilmData, ProjectState
from project_manager import ProjectManager
from web_ui import Tags


async def get_active_project() -> Project:
    """
    Get the currently active project.
    :raises HTTPException: An HTTP_404_NOT_FOUND exception if no active project exists.
    """

    active_project = await App.instance().project_manager.active_project
    if not active_project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorDetails(type="no_active_project",
                                                                                       loc=tuple(),
                                                                                       msg="No active project found",
                                                                                       input=None))
    return active_project


router = APIRouter()


@router.get("/api/allprojects",
            tags=[Tags.GLOBAL])
async def get_all_projects() -> dict[int, str]:
    """A dictionary of all projects ids and their name"""
    all_projects = await ProjectManager.all_projects()
    return all_projects


class ProjectId(BaseModel):
    """Wrap project id into a model"""
    pid: int = -1


@router.get("/api/project/id",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_project_id() -> ProjectId:
    """The id of the currently active project."""
    active_project = await get_active_project()
    pid = active_project.pid
    return ProjectId(pid=pid)


class ProjectName(BaseModel):
    """Wrap project name into a model"""
    name: str = "Unknown"


@router.get("/api/project/name",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_project_name() -> ProjectName:
    """Get the name of the currently active project."""
    active_project = await get_active_project()
    name = active_project.name
    return ProjectName(name=name)


@router.put("/api/project/name",
            responses={status.HTTP_409_CONFLICT: {"model": ErrorDetails},
                       status.HTTP_400_BAD_REQUEST: {"model": ErrorDetails},
                       status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def put_project_name(new_name: ProjectName) -> ProjectName:
    """
    Change the name of the currently active project.
    The new name must be unique and must not contain any characters that are unusable for a filesystem name.
    """
    active_project = await get_active_project()
    try:
        await active_project.set_name(new_name.name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorDetails(type="invalid_name",
                                                                                         loc=tuple(),
                                                                                         msg=str(e),
                                                                                         input=new_name.name))
    except ProjectAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ErrorDetails(type="duplicate_name",
                                                                                      loc=tuple(),
                                                                                      msg="Project already exists",
                                                                                      input=new_name.name))

    return new_name


@router.get("/api/project/paths",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_project_paths() -> ProjectPaths:
    active_project = await get_active_project()
    return active_project.paths


@router.put("/api/project/paths",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def put_project_paths(project_paths: ProjectPaths) -> ProjectPaths:
    active_project = await get_active_project()
    await active_project.set_paths(project_paths)
    return project_paths


# todo: cleanup functions below

@router.get("/api/project/filmdata",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_project_filmdata() -> FilmData:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/api/project/filmdata",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def put_project_filmdata(project_metadata: FilmData) -> FilmData:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/api/project/state",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_project_state() -> ProjectState:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/api/project/perf/location",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_perf_location() -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/api/project/perf/location",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING],
            )
async def put_perf_location(perf_location: PerforationLocation) -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/api/project/perf/detect",
             responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
             tags=[Tags.PROJECT_SETTING]
             )
async def post_perfdetect(startpoint: Point) -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/api/project/scanarea",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING])
async def get_scanarea() -> ScanArea:
    """
    Get the camera Scanarea, the area that defines the film frame content to be used.
    All values are normalized (ref_delta: between -1 and 1, size: between 0 and 1) and
    independent of the select camera image resolution.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/api/project/scanarea",
            responses={status.HTTP_404_NOT_FOUND: {"model": ErrorDetails}},
            tags=[Tags.PROJECT_SETTING],
            )
async def put_scanarea(scanarea: ScanArea) -> ScanArea:
    """
    Set the ScanArea, the area that defines the film frame content to be used.
    All values are normalized (between 0 and 1) to be independent of the select camera image resolution.
        - ref_delta: The delta between the Perforation reference point and the top left point of the scan area.
        - size: The size of the scan area.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)
