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
from fastapi import APIRouter, HTTPException

from project_manager import ProjectManager
from film_specs import FilmFormat, FilmSpecs
from web_ui import Tags
from web_ui.api_errors import APINoActiveProject, APIProjectDoesNotExist, APIInvalidDataError

router = APIRouter()


###############################################################################
#
# Project Management
#
###############################################################################

def get_projectmanager() -> ProjectManager:
    from web_ui.server import get_app
    app = get_app()
    return app.project_manager


@router.get("/api/projects/all",
            tags=[Tags.GLOBAL])
async def get_all_projects() -> dict[int, str]:
    """A dictionary of all projects ids and their name"""
    pm = get_projectmanager()
    all_projects = await pm.all_projects()
    return all_projects


@router.get("/api/projects/active",
            responses={APINoActiveProject.status_code: {"model": APINoActiveProject}},
            tags=[Tags.GLOBAL])
async def get_active_project() -> int:
    """
    Get the pid of the currently active project.
    """
    pm = get_projectmanager()
    active = await pm.active_project
    if active is None:
        raise HTTPException(status_code=APINoActiveProject.status_code,
                            detail=APINoActiveProject())
    return active.pid


@router.put("/api/projects/load",
            responses={
                APIInvalidDataError.status_code: {"model": APIInvalidDataError},
                APIProjectDoesNotExist.status_code: {"model": APIProjectDoesNotExist},
            },
            tags=[Tags.GLOBAL])
async def load_project(pid: int) -> int:
    """
    Load the project with the given id and make it the active one.
    :param pid: Valid Project ID
    """
    pm = get_projectmanager()
    project = await pm.load_project(pid)
    return project.pid


@router.post("/api/projects/new",
             tags=[Tags.GLOBAL])
async def new_project() -> int:
    pm = get_projectmanager()
    project = await pm.new_project()
    return project.pid


@router.delete("/api/projects/delete",
               responses={
                   APIInvalidDataError.status_code: {"model": APIInvalidDataError},
                   APIProjectDoesNotExist.status_code: {"model": APIProjectDoesNotExist},
               },
               tags=[Tags.GLOBAL]
               )
async def delete_project(pid: int) -> None:
    pm = get_projectmanager()
    project = await pm.delete_project(pid)


###############################################################################
#
# Supported Types
#
###############################################################################

@router.get("/api/filmformats",
            tags=[Tags.GLOBAL])
async def get_all_filmformats() -> list[FilmFormat]:
    return FilmSpecs.get_api_film_formats()
