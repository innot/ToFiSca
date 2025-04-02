from models import Point, ScanArea, PerforationLocation


class ProjectError(Exception):
    pass


class ProjectDoesNotExistError(Exception):
    def __init__(self, project_id: int):
        message = f"Project with id={project_id} does not exist"
        super().__init__(message)


class ProjectAlreadyExistsError(ProjectError):
    def __init__(self, project_name: str):
        msg = f"Project('{project_name}') already exists"
        super().__init__(msg)


class ProjectNotLoadedError(ProjectError):
    def __init__(self, project_id: int):
        msg = f"Project('{project_id}') is not yet loaded. Call Project.load() first."
        super().__init__(msg)


