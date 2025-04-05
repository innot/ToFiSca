import pytest

from errors import ProjectDoesNotExistError
from main import MainApp
from project import Project


@pytest.fixture
def app(tmp_path):
    return MainApp(data_storage_path=tmp_path, database_file="memory")


@pytest.mark.asyncio
async def test_all_projects(app):
    # first create a few projects
    pm = app.project_manager
    proj_list = ["test_a", "test_b", "test_c"]
    for proj_name in proj_list:
        project = await pm.new_project(proj_name)

    lp = await pm.all_projects()
    assert len(lp) == len(proj_list)
    for name in lp.values():
        assert name in proj_list

    # the last project should be the active project
    # noinspection PyUnboundLocalVariable
    assert project is await pm.active_project


@pytest.mark.asyncio
async def test_new_project(app):
    pm = app.project_manager
    project1 = await pm.new_project("test_new_project")
    assert project1.pid > 0
    assert project1.name == "test_new_project"

    all_projects = await pm.all_projects()
    assert project1.pid in all_projects.keys()
    assert project1.name == all_projects[project1.pid]

    # test a second project to ensure no intererance from first
    project2 = await pm.new_project()  # default name
    assert project2.pid == project1.pid + 1
    assert project2.name == f"Project {project2.pid}"

    all_projects = await pm.all_projects()
    assert project2.pid in all_projects.keys()
    assert project2.name == all_projects[project2.pid]


@pytest.mark.asyncio
async def test_delete_project(app):
    pm = app.project_manager

    # first create a few projects
    projects: list[Project] = []
    for i in range(10):
        projects.append(await pm.new_project())

    # delete the first project
    await pm.delete_project(projects.pop(0).pid)
    assert len(await pm.all_projects()) == len(projects)

    # delete all other projects
    for project in projects:
        await pm.delete_project(project.pid)
    assert len(await pm.all_projects()) == 0

    # check exception
    with pytest.raises(ProjectDoesNotExistError):
        await pm.delete_project(999)

    # test delete_storage
    # todo:


@pytest.mark.asyncio
async def test_active_project(app):
    pm = app.project_manager
