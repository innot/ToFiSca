class ProjectError(Exception):
    pass


class ProjectDoesNotExistError(Exception):
    def __init__(self, project_id: int):
        self.project_id = project_id
        message = f"Project with id={project_id} does not exist"
        super().__init__(message)


class ProjectAlreadyExistsError(ProjectError):
    def __init__(self, project_name: str):
        self.project_name = project_name
        msg = f"Project('{project_name}') already exists"
        super().__init__(msg)


class ProjectNotLoadedError(ProjectError):
    def __init__(self, project_id: int):
        self.project_id = project_id
        msg = f"Project('{project_id}') is not yet loaded. Call Project.load() first."
        super().__init__(msg)

