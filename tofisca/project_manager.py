from pathlib import Path

from pydantic import BaseModel

from app import App
from configuration.config_item import ConfigItem
from errors import ProjectAlreadyExistsError, ProjectDoesNotExistError
from project import Project


class ProjectNameAndId(BaseModel):
    id: int = -1
    name: str = ""


class ActiveProject(ConfigItem):
    id: int = -1
    name: str = None


class RootDataPath(ConfigItem):
    path: str = ""


class ProjectManager:
    """
    :param app: Optional reference to the app this manager belongs to. If not set the App.instance will be used.
                This is used for testing.
    """

    def __init__(self, app: App):

        self.app = app

        # self._active_project.add_observer_callback(WebsocketManager().item_change_callback)

        # cache all projects so they do not have to be recreated from the database
        self._projects_cache: dict[id, Project] = {}

        # The currently active project. Only one project can be active at a time.
        self._active_project: ActiveProject | None = ActiveProject()

        # The root path for all projects. Projects store their data in a subfolder with the name of the project
        root_path = self.app.storage_path

        self._root_path: Path = root_path

        # store a reference to the config database
        self.db = app.config_database

    @property
    async def active_project(self) -> Project | None:
        """
        The active project, i.e. the last project loaded or created.
        Read-only. Use :meth:'load_project' or :meth:'create_project' to set the active project.
        :return: The active project or 'None' if no project has been loaded or created.
        """
        if self._active_project is None:
            self._active_project = await ActiveProject().retrieve(self.app.config_database)
        project_id = self._active_project.id
        try:
            project = await self.load_project(project_id)
            return project
        except ProjectDoesNotExistError:
            return None

    @property
    def root_path(self) -> Path:
        """
        The filesystem path where all application and project data are stored.
        Normally, this is the platform-specific default application data folder.

        This property is read-only and can only be set upon application startup.
        """
        return self._root_path

    async def load_project(self, project_id: int = None) -> Project:
        """
        Get the project with the given id.
        :param project_id: The id of the project to get.
        :return: The Project instance
        :raises ProjectDoesNotExistError: If the project does not exist.
        """
        # check if project is cached
        if project_id in self._projects_cache:
            project = self._projects_cache[project_id]
        else:
            # check if project exists
            all_projects = await self.db.all_projects()
            if not project_id in all_projects.items():
                raise ProjectDoesNotExistError(project_id)

            # load the project from the database
            project = Project(self.app, project_id)
            await project.load()
            self._projects_cache[project_id] = project

        # set it as the active project
        self._active_project.id = project.pid
        self._active_project.name = project.name

        # store the active project in the database
        await self._active_project.store(self.app.config_database)
        return project

    async def new_project(self, name: str | None = None) -> Project:

        # Project names must be unique.
        # Check if a project with this name already exists
        if not name:
            all_projects = await self.db.all_projects()
            for project_name in all_projects.values():
                if project_name == name:
                    raise ProjectAlreadyExistsError(name)

        pid = await self.db.create_project(name)
        project = Project(self.app, pid)
        await project.load()  # load the defaults

        self._projects_cache[project.pid] = project

        # set it as the active project
        self._active_project.id = project.pid
        self._active_project.name = project.name

        # store the active project in the database
        await self._active_project.store(self.app.config_database)

        return project

    async def delete_project(self, pid: int, delete_storage: bool = False) -> None:
        """
        Delete the project with the given id.

        :param pid:
        :param delete_storage: If `True` the complete storage of the project will be deleted from the filesystem.
        :raises ProjectDoesNotExistError: If the project does not exist.
        """
        active = self._active_project   # store here, because it will be overwritten by load_project

        # check that project exists
        project = await self.load_project(pid)

        if delete_storage:
            await project._delete_storage()

        # remove from cache...
        if project.pid in self._projects_cache:
            self._projects_cache.pop(project.pid)

        # ... and from database
        await self.app.config_database.delete_project(project.pid)

    async def all_projects(self) -> dict[int, str]:
        all_projects = await self.db.all_projects()
        return all_projects
