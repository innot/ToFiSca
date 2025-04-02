from pydantic import BaseModel

from .configuration import ConfigItem, ConfigDatabase
from .errors import ProjectAlreadyExistsError, ProjectDoesNotExistError
from .project import Project


class ProjectNameAndId(BaseModel):
    id: int = -1
    name: str = ""


class ActiveProject(ConfigItem):
    id: int = -1
    name: str = None


class _ProjectManager(object):

    def __init__(self):

        # self._active_project.add_observer_callback(WebsocketManager().item_change_callback)

        # cache all projects so they do not have to be recreated from the database
        self._projects_cache: dict[id, Project] = {}

    @property
    async def active_project(self) -> Project | None:
        """
        Get the active project, i.e. the last project loaded or created.
        Read only. Use :meth:'load_project' or :meth:'create_project' to set the active project.
        :return: The active project or 'None' if no project has been loaded or created.
        :rtype: Project
        """
        if self._active_project is None:
            self._active_project = await ActiveProject().retrieve()
        project_id = self._active_project.id
        project = await self.get_project(project_id)
        return project

    async def get_project(self, project_id: int = None) -> Project:
        """
        Get the project with the given id.
        :param project_id: The id of the project to get.
        :return: The Project instance
        :raises ProjectDoesNotExistError: If the project does not exist.
        """
        # check if project is cached
        if project_id in self._projects_cache:
            return self._projects_cache[project_id]

        # check if project exists
        all_projects = await ConfigDatabase().all_projects()
        if not project_id in all_projects.items():
            raise ProjectDoesNotExistError(project_id)

        # load the project from the database
        project = Project(project_id)
        self._projects_cache[project_id] = project
        return project

    async def new_project(self, name: str | None = None) -> Project:

        # Project names must be unique.
        # check if a project with this name already exists
        if not name:
            all_projects = await ConfigDatabase().all_projects()
            for project_name in all_projects.values():
                if project_name == name:
                    raise ProjectAlreadyExistsError(name)

        pid = await ConfigDatabase().create_project(name)
        project = Project(pid).load_from_db()
        self._projects_cache[project.pid] = project
        return project

    async def list_projects(self) -> list[dict[str, int | str]]:
        all_projects = await ConfigDatabase().all_projects()

        # convert to list
        result = []
        for [id_, name] in all_projects.items():
            result.append({"id": id_, "name": name})

        return result

    def set_project_active(self, project: Project) -> None:
        self._active_project = project


# One manager to rule them all
ProjectManager = _ProjectManager()
