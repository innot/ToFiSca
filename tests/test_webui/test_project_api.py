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
import pytest_asyncio
from fastapi.testclient import TestClient

from main import MainApp
from web_ui.server import webui_app, set_app, get_app
from web_ui.api_errors import APIInvalidDataError


@pytest.fixture(scope="session")
def client(tmp_path_factory) -> TestClient:
    app = MainApp(data_storage_path=tmp_path_factory.mktemp("test", numbered=True),
                  database_file="memory")
    set_app(app)

    client = TestClient(webui_app)
    return client


@pytest_asyncio.fixture()
async def project():
    app = get_app()

    project = await app.project_manager.new_project("TestProject")

    yield project

    await app.project_manager.delete_project(project.pid)


@pytest.mark.asyncio
async def test_no_project(client) -> None:
    response = client.get("/api/project/id")
    assert response.status_code == 404

    response = client.get("/api/project/name")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_id(client, project) -> None:
    response = client.get("/api/project/id")
    assert response.status_code == 200
    pid = response.json()
    assert isinstance(pid, int)
    assert pid == project.pid


@pytest.mark.asyncio
async def test_project_name(client, project) -> None:
    response = client.get("/api/project/name")
    assert response.status_code == 200
    name = response.json()
    assert isinstance(name, str)
    assert name == project.name

    # test put new name
    response = client.put("/api/project/name?name='new Project name'")
    assert response.status_code == 200
    name = response.json()
    assert isinstance(name, str)
    assert name == project.name

    # test invalid name
    response = client.put("/api/project/name?name='new:name'")
    assert response.status_code == APIInvalidDataError.status_code

    # test duplicate name
