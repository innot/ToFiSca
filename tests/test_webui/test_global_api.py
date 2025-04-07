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

import pytest
from fastapi.testclient import TestClient

from main import MainApp
from web_ui.server import webui_app, set_app, get_app
from web_ui.api_errors import APINoActiveProject, APIProjectDoesNotExist, APIInvalidDataError


@pytest.fixture
def client(tmp_path_factory) -> TestClient:
    app = MainApp(data_storage_path=tmp_path_factory.mktemp("test", numbered=True),
                  database_file="memory")
    set_app(app)

    client = TestClient(webui_app)
    return client

###############################################################################
# Project Manager tests
###############################################################################

@pytest.mark.asyncio
async def test_all_projects(client) -> None:
    pm = get_app().project_manager

    # test with no project
    response = client.get("/api/projects/all")
    assert response.status_code == 200
    content = response.json()
    assert len(content) == 0

    # create a few projects
    for i in range(10):
        await pm.new_project()

    response = client.get("/api/projects/all")
    content = response.json()
    assert len(content) == 10


@pytest.mark.asyncio
async def test_active_project(client) -> None:
    pm = get_app().project_manager

    response = client.get("/api/projects/active")
    assert response.status_code == APINoActiveProject.status_code
    content = response.json()
    assert content["error_type"] == APINoActiveProject.__name__

    # create a project and check that it is the active one
    project1 = await pm.new_project()
    response = client.get("/api/projects/active")
    assert response.status_code == 200
    content = response.json()
    assert content == project1.pid

    # create a second project and check again
    project2 = await pm.new_project()
    response = client.get("/api/projects/active")
    assert response.status_code == 200
    content = response.json()
    assert content == project2.pid

    # make project1 active again
    response = client.put(f"/api/projects/load?pid={project1.pid}")
    content = response.json()
    assert content == project1.pid
    response = client.get("/api/projects/active")
    content = response.json()
    assert content == project1.pid


@pytest.mark.asyncio
async def test_new_project(client) -> None:
    pm = get_app().project_manager

    response = client.post("/api/projects/new")
    assert response.status_code == 200
    content = response.json()
    assert content == (await pm.active_project).pid


@pytest.mark.asyncio
async def test_load_project(client) -> None:
    pm = get_app().project_manager

    project = await pm.new_project()

    response = client.put(f"/api/projects/load?pid={project.pid}")
    assert response.status_code == 200
    content = response.json()
    assert content == project.pid

    # test invalid project id
    response = client.put("/api/projects/load?pid=999")
    assert response.status_code == APIProjectDoesNotExist.status_code
    content = response.json()
    assert content["error_type"] == APIProjectDoesNotExist.__name__

    # check the validator
    response = client.put("/api/projects/load?pid='foo'")
    assert response.status_code == APIInvalidDataError.status_code
    content = response.json()
    assert content["error_type"] == APIInvalidDataError.__name__

@pytest.mark.asyncio
async def test_delete_project(client) -> None:
    pm = get_app().project_manager
    project = await pm.new_project()

    response = client.delete(f"/api/projects/delete?pid={project.pid}")
    assert response.status_code == 200

    # ensure project is deleted
    response = client.delete(f"/api/projects/delete?pid={project.pid}")
    assert response.status_code == APIProjectDoesNotExist.status_code


###############################################################################
#
# Global lists
#
###############################################################################

@pytest.mark.asyncio
async def test_get_filmformats(client) -> None:

    response = client.get("/api/filmformats")
    assert response.status_code == 200
    content = response.json()
    assert len(content) > 0
    assert len(content[0]["key"]) > 2   # we don't know what the first entry is, so only test that there is content
    assert len(content[0]["name"]) > 2
    assert isinstance(content[0]["framerates"], list)

