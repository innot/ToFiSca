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

from errors import ProjectAlreadyExistsError
from models import PerforationLocation, Point, ScanArea
from project import Project, ProjectPathEntry, FilmData, ProjectState
from web_ui import Tags
from web_ui.api_errors import APINoActiveProject, APIProjectAlreadyExists, APIInvalidDataError, APIObjectNotFoundError


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


###############################################################################
#
# Projects
#
###############################################################################


@router.get("/api/project/id",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_project_id() -> int:
    """The id of the currently active project."""
    active_project = await get_active_project()
    pid = active_project.pid
    return pid


@router.get("/api/project/name",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_project_name() -> str:
    """Get the name of the currently active project."""
    active_project = await get_active_project()
    name = active_project.name
    return name


@router.put("/api/project/name",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
                APIProjectAlreadyExists.status_code: {"model": APIProjectAlreadyExists},
                APIInvalidDataError.status_code: {"model": APIInvalidDataError},
            },
            tags=[Tags.PROJECT_SETTING])
async def put_project_name(name: str) -> str:
    """
    Change the name of the currently active project.
    The new name must be unique and must not contain any characters that are unusable for a filesystem name.
    """
    active_project = await get_active_project()
    try:
        await active_project.set_name(name)
        return name

    except ValueError:
        apierror = APIInvalidDataError(
            title="Invalid project name",
            details="The name must not contain any characters that are unusable for a filesystem name.")
        raise HTTPException(status_code=apierror.status_code, detail=apierror)

    except ProjectAlreadyExistsError:
        apierror = APIProjectAlreadyExists(name=name)
        raise HTTPException(status_code=apierror.status_code, detail=apierror)


###############################################################################
# Project Paths
###############################################################################


@router.get("/api/project/allpaths",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_all_paths() -> list[ProjectPathEntry]:
    active_project = await get_active_project()
    return list(active_project.all_paths.values())


@router.get("/api/project/path",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
                APIObjectNotFoundError.status_code: {"model": APIObjectNotFoundError},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_project_path(name: str) -> ProjectPathEntry:
    active_project = await get_active_project()
    try:
        entry = await active_project.get_path(name)
        return entry
    except KeyError:
        apierror = APIObjectNotFoundError(
            title="Invalid project path",
            details=f"The project has no path with the name '{name}'",
            error_type="APIProjectPathNotFoundError"
        )
        raise HTTPException(status_code=apierror.status_code, detail=apierror)


@router.put("/api/project/path",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
                APIObjectNotFoundError.status_code: {"model": APIObjectNotFoundError},
                APIInvalidDataError.status_code: {"model": APIInvalidDataError},
            },
            tags=[Tags.PROJECT_SETTING])
async def put_project_path(path_entry: ProjectPathEntry) -> ProjectPathEntry:
    active_project = await get_active_project()
    try:
        await active_project.update_path(path_entry)
        return path_entry
    except KeyError:
        apierror = APIObjectNotFoundError(
            title="Invalid project path",
            details=f"The project has no path with the name '{path_entry.name}'",
            error_type="APIProjectPathNotFoundError"
        )
        raise HTTPException(status_code=apierror.status_code, detail=apierror)
    except ValueError as exc:
        apierror = APIInvalidDataError(
            title="Invalid project path",
            details=f"The path '{path_entry.name}' cannot be resolved to a real path.\nReason: {str(exc)}",
        )
        raise HTTPException(status_code=apierror.status_code, detail=apierror)


###############################################################################
# Project Film Data
###############################################################################

@router.get("/api/project/filmdata",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
                APIObjectNotFoundError.status_code: {"model": APIObjectNotFoundError},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_project_filmdata() -> FilmData:
    active_project = await get_active_project()
    filmdata = active_project.film_data
    return filmdata


@router.put("/api/project/filmdata",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
                APIInvalidDataError.status_code: {"model": APIInvalidDataError},
            },
            tags=[Tags.PROJECT_SETTING]
            )
async def put_project_filmdata(filmdata: FilmData) -> FilmData:
    active_project = await get_active_project()
    active_project.film_data = filmdata
    return filmdata


@router.get("/api/project/state",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_project_state() -> ProjectState:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/api/project/perf/location",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_perf_location() -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/api/project/perf/location",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING],
            )
async def put_perf_location(perf_location: PerforationLocation) -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.post("/api/project/perf/detect",
             responses={
                 APINoActiveProject.status_code: {"model": APINoActiveProject},
             },
             tags=[Tags.PROJECT_SETTING]
             )
async def post_perfdetect(startpoint: Point) -> PerforationLocation:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.get("/api/project/scanarea",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
            tags=[Tags.PROJECT_SETTING])
async def get_scanarea() -> ScanArea:
    """
    Get the camera Scanarea, the area that defines the film frame content to be used.
    All values are normalized (ref_delta: between -1 and 1, size: between 0 and 1) and
    independent of the select camera image resolution.
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED)


@router.put("/api/project/scanarea",
            responses={
                APINoActiveProject.status_code: {"model": APINoActiveProject},
            },
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
