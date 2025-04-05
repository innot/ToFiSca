from __future__ import annotations

import shutil
from enum import Enum
from pathlib import Path
from string import Template
from typing import Union

from pydantic import Field

from app import App
from configuration.config_item import ProjectItem
from errors import ProjectAlreadyExistsError, ProjectNotLoadedError, ProjectDoesNotExistError
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


class ProjectPathEntry(ProjectItem):
    name: str = Field(
        description="An identifier for this path, e.g. 'project' or 'scanned'")
    description: str = Field(default="",
                             description="What the path is for.")
    path: str = Field(default="",
                      description="The actual path. May be relative to the application storage folder or absolute. Can contain templates.")
    resolved: str = Field(default="",
                          description="The computed absolute path on the filesystem. For info only.")


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
        """
        Load the project with the given pid from the config database.
        :raises: ProjectDoesNotExistError if the project does not exist
        """
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

        self._paths: dict[str, ProjectPathEntry] = {
            "project": ProjectPathEntry(pid=pid,
                                        name="project",
                                        description="General project data storage",
                                        path="${name}",
                                        ),
            "scanned": ProjectPathEntry(pid=pid,
                                        name="scanned",
                                        description="Folder for raw scanned images",
                                        path="${project}/scanned_images",
                                        ),
            "final": ProjectPathEntry(pid=pid,
                                      name="final",
                                      description="Images after processing",
                                      path="${project}/final_images",
                                      ),
        }

        self._film_data: FilmData = FilmData(pid=pid)

        self._scanarea = ScanAreaManager(pid=pid)

    async def load(self) -> Project:
        """
        Load all project Settings from the configuration database.
        This should be called immediately after instantiation.

        There is no save function.
        All settings are saved whenever they are changed.
        :raises: ProjectDoesNotExistError if the project with the current pid does not exist.
        """
        self._name = await self.db.get_project_name(self._pid)
        if self._name is None:
            raise ProjectDoesNotExistError(self._pid)

        await self._project_state.retrieve(self.db, self._pid)
        await self._film_data.retrieve(self.db, self._pid)
        await self._scanarea.load_current_state(self.db, self._pid)

        for path in self._paths.values():
            await path.retrieve(self.db, self._pid)

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
    def all_paths(self) -> dict[str, ProjectPathEntry]:
        """
        The paths where to store the images and other data.

        The returned paths may contain templates (e.g. '{project.name}' or '{project.id}').
        Use :meth:`resolve_path` to resolve the templates and get the real path.

        This property is read-only.
        Use :meth:`set_paths` to set the project paths.
        """
        # resolve all paths first before handing them out
        result: dict[str, ProjectPathEntry] = {}
        for path_entry in self._paths.values():
            path_entry.resolved = str(self.resolve_path(path_entry.path, create_folder=False))
            result[path_entry.name] = path_entry.model_copy()
        return result

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
        self._name = new_name

        # todo: maybe we need to change the name of the paths

    async def update_path(self, new_path: ProjectPathEntry):
        """
        Update the given path.
        """
        # get the current path entry
        try:
            old_path_entry = self._paths[new_path.name]
        except KeyError:
            raise ValueError(f"The Project has no path named {new_path.name}")

        old_path_resolved = self.resolve_path(old_path_entry.path, create_folder=False)

        new_path = new_path.path
        new_path_resolved = self.resolve_path(new_path, create_folder=False)

        if new_path_resolved != old_path_resolved and old_path_resolved.exists():
            # The Path has changed. Rename the folder as well (if it exists)
            old_path_resolved.rename(new_path_resolved)

        # update the database
        self._paths[old_path_entry.name].path = new_path
        self._paths[old_path_entry.name].resolved = new_path_resolved
        await self._paths[old_path_entry.name].store(self.db, self._pid)

    async def _delete_storage(self) -> None:
        """
        Delete the project storage and image folders.

        All data within the folders is irreversebly deleted.

        :raises Exception: A filesystem Extecption if the storage paths could not be deleted.
        """
        for entry in self._paths.values():
            path = self.resolve_path(entry.path, create_folder=False)
            if path.exists():
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

        # first build a list of all template identifiers
        identifiers = {"name": self._name, "pid": self._pid, }
        for key in self._paths.keys():
            identifiers[key] = self._paths[key].path

        # now substitude until no more substitutions left
        counter = 0
        while "${" in folder_path:
            resolver = Template(folder_path)
            folder_path = resolver.safe_substitute(identifiers)
            counter += 1
            if counter > 10:
                raise RuntimeError("Template substitution counter exceeded. Probably due to circular template.")

        folder_path = Path(folder_path)  # ... and back to Path
        if not folder_path.is_absolute():
            # prepend the data_storage_path
            root = self.app.project_manager.root_path
            folder_path = root / folder_path

        # create the folder if required
        if create_folder:
            folder_path.mkdir(parents=True, exist_ok=True)

        return folder_path
