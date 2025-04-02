from __future__ import annotations

from enum import Enum
from typing import Union

from pydantic import BaseModel, Field

from .configuration import ProjectItem
from .film_specs import FilmFormat
from .configuration import ConfigDatabase
from .errors import ProjectAlreadyExistsError, ProjectNotLoadedError
from .models import PerforationLocation, ScanArea


class AllProjects(BaseModel):
    all: dict[str, int] = {"foo": 1, "bar": 2, "baz": 3}


class ProjectStateEnum(Enum):
    NEW = "new"
    IDLE = "idle"
    RUN = "run"
    PAUSE = "pause"
    FAILURE = "failure"
    FINISHED = "finished"


class ProjectName(BaseModel):
    name: str = Field(default="", )


class ProjectState(ProjectItem):
    state: ProjectStateEnum = Field(default=ProjectStateEnum.NEW)
    current_frame: int = Field(default=0, ge=0)
    last_scanned_frame: int = Field(default=0, ge=0)
    last_processed_frame: int = Field(default=0, ge=0)
    errors: list[str] = Field(default=[])


class ProjectPaths(ProjectItem):
    scanned_images: str = "{project}/images_raw"
    processed_images: str = "{project}/images_processed"


class FilmData(ProjectItem):
    date: str = ""
    author: str = ""
    description: str = ""
    format: Union[FilmFormat, None] = None
    fps: float = 18
    stock: str = ""
    tags: list[str] = []


class Project:

    @classmethod
    async def load_project(cls, pid: int) -> Project:
        project = Project(pid)
        await project.load()
        return project

    def __init__(self, pid: int) -> None:

        self._pid = pid
        self._name: ProjectName |None = None

        self._project_state: ProjectState | None = None

        self._project_data: FilmData | None = None
        self._perforation_location: PerforationLocation | None = None
        self._scan_area: ScanArea | None = None

    async def load(self) -> Project:
        """
        Load all project Settings from the configuration database.
        This should be called immediately after instantiation
        """

        name  = await ConfigDatabase().get_project_name(self._pid)
        self._name = ProjectName(name=name)
        self._project_state = await ProjectState(pid=self._pid).retrieve()

        return self

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def name(self) -> str:
        if self._name is None:
            raise ProjectNotLoadedError(self._pid)
        return self._name.name

    @name.setter
    async def name(self, new_name: str) -> None:
        # check if the name already exists
        all_projects = await ConfigDatabase().all_projects()
        for [pid, name] in all_projects.items():
            if name == new_name and pid != self._pid:
                raise ProjectAlreadyExistsError(new_name)

        # change the name in the database
        await ConfigDatabase().change_project_name(self._pid, new_name)
        self._name.name = new_name
