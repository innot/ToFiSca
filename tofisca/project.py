from __future__ import annotations

import shutil
from enum import Enum
from pathlib import Path
from typing import Union

from pydantic import Field

from app import App
from configuration.config_item import ProjectItem
from errors import ProjectAlreadyExistsError, ProjectNotLoadedError
from film_specs import FilmFormat
from scanarea_manager import ScanAreaManager


class ProjectStateEnum(Enum):
    NEW = "new"
    IDLE = "idle"
    RUN = "run"
    PAUSE = "pause"
    FAILURE = "failure"
    FINISHED = "finished"


class ProjectState(ProjectItem):
    state: ProjectStateEnum = Field(default=ProjectStateEnum.NEW)
    current_frame: int = Field(default=0, ge=0)
    last_scanned_frame: int = Field(default=0, ge=0)
    last_processed_frame: int = Field(default=0, ge=0)
    errors: list[str] = Field(default=[])


class ProjectPaths(ProjectItem):
    project_path: str = "{project.name}"
    scanned_images: str = "scanned_images"
    final_images: str = "final_images"


class FilmData(ProjectItem):
    date: str = ""
    author: str = ""
    description: str = ""
    format: Union[FilmFormat, None] = None
    fps: float = 18
    stock: str = ""
    tags: list[str] = []


class Project:
    """
    The Project object is a Container for the current state of the project.

    It contains the settings, loads and stores them in the config database
    """

    @classmethod
    async def load_project(cls, app: App, pid: int) -> Project:
        project = Project(app, pid)
        await project.load()
        return project

    def __init__(self, app: App, pid: int, name: str = None) -> None:

        self.app = app
        self.db = app.config_database  # convenience shortcut

        self._pid = pid
        self._name: str | None = name

        # load defaults

        self._project_state: ProjectState = ProjectState(pid=pid)

        self._paths: ProjectPaths = ProjectPaths(pid=pid)

        self._film_data: FilmData = FilmData(pid=pid)

        self._scanarea = ScanAreaManager(pid=pid)

    async def load(self) -> Project:
        """
        Load all project Settings from the configuration database.
        This should be called immediately after instantiation.

        There is no save function.
        All settings are saved whenever they are changed.
        """
        self._name = await self.db.get_project_name(self._pid)
        await self._project_state.retrieve(self.db, self._pid)
        await self._film_data.retrieve(self.db, self._pid)
        await self._scanarea.load_current_state(self.db, self._pid)

        await self._paths.retrieve(self.db, self._pid)

        return self

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def name(self) -> str:
        """
        Gets the name of the project.

        This property is read-only.
        Use :meth:`set_name` to change the name of the project.
        """
        if self._name is None:
            raise ProjectNotLoadedError(self._pid)
        return self._name

    @property
    def paths(self) -> ProjectPaths:
        """
        The paths where to store the images and other data.

        The returned paths may contain templates ('{project.name}' or '{project.id}').
        Use :meth:`resolve_path` to resolve the templates and get the real path.

        This property is read-only and returns a copy of the internal one.
        Use :meth:`set_paths` to set the project paths.
        """
        # apply templates
        paths = self._paths.model_copy()
        return paths

    async def set_name(self, new_name: str) -> None:
        """
        Sets the name of the project.

        The new name of the project must be unique, there must be no other project of the same name.
        This is enforced to make the project name useable as a descriptive path name for storing images and data.
        Therefore, the name must also contain no characters that are unusable for a filesystem name.
        """
        # check if the name contains any invalid character
        for c in new_name:
            if ord(c) < 32 or c in r'\/:*?"<>|':  # no control characters and special characters (windows compatible)
                raise ValueError(f"Invalid character {c} in name")

        # check if the name already exists
        all_projects = await self.db.all_projects()
        for [pid, name] in all_projects.items():
            if name == new_name and pid != self._pid:
                raise ProjectAlreadyExistsError(new_name)

        # change the name in the database
        await self.db.change_project_name(self._pid, new_name)
        self._name.name = new_name

        # todo: maybe we need to change the name of the paths

    async def set_paths(self, new_paths: ProjectPaths):
        """
        Set the image and data storage paths for this project.
        """
        self._paths.project_path = str(self._update_path(self._paths.project_path, new_paths.project_path))
        self._paths.scanned_images = str(self._update_path(self._paths.scanned_images, new_paths.scanned_images))
        self._paths.final_images = str(self._update_path(self._paths.final_images, new_paths.final_images))

        await self._paths.store(self.db, self._pid)

    def _update_path(self, old_path: str, new_path: str) -> Path:
        old_path = self._get_absolute_path(old_path)
        new_path = self._get_absolute_path(new_path)
        if new_path != old_path:
            # project path has changed. rename the folder as well
            old_path.rename(new_path)
        return Path(new_path)

    def _get_absolute_path(self, path: Path | str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        else:
            return self.app.project_manager.root_path / path

    async def _delete_storage(self) -> None:
        """
        Delete the project storage and image folders.

        All data within the folders is irreversebly deleted.

        :raises Exception: A filesystem Extecption if the storage paths could not be deleted.
        """
        path = self.resolve_path(self._paths.project_path)
        shutil.rmtree(path)

        path = self.resolve_path(self._paths.scanned_images)
        shutil.rmtree(path)

        path = self.resolve_path(self._paths.final_images)
        shutil.rmtree(path)

    def resolve_path(self, folder_path: str | Path, create_folder: bool = True) -> Path:
        """
        Resolve a path from the path settings to a fully qualified absolute path.

        If present, the templates '{project.name}' and {project.id}' will be replaced
        with the actual values.

        I the given folder is not absolute, i.e. does not start with '/', the returned folder
        will be placed in the data_storage_path of the App this project belongs to.

        If the folder pointed to by the path does not exist, it will be created.

        :param folder_path:
        :param create_folder: If set to `False`, the folder is not created.
        :return: An absolute path to the specified folder.
        :raises Exception: A filesystem Extecption if the storage paths could not be created.
        """
        folder_path = str(folder_path)  # convert Path to string...
        folder_path = folder_path.replace("{project.name}", self._name)
        folder_path = folder_path.replace("{project.id}", str(self._pid))

        folder_path = Path(folder_path)  # ... and back to Path
        if not folder_path.is_absolute():
            # prepend the data_storage_path
            root = self.app.project_manager.root_path
            folder_path = root / folder_path

        # create the folder if required
        if create_folder:
            folder_path.mkdir(parents=True, exist_ok=True)

        return folder_path
