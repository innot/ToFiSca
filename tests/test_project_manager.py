import pytest

from main import MainApp
from project_manager import ProjectManager


@pytest.fixture
def app(tmp_path):
    return MainApp(data_storage_path=tmp_path, database_file="memory")


@pytest.mark.asyncio
async def test_list_projects(app):
    # first create a few projects
    pm = ProjectManager(app)
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
