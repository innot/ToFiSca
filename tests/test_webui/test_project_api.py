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
from typing import Coroutine

import pytest
from fastapi.testclient import TestClient

from main import MainApp
from project import Project
from project_api import ProjectId
from web_ui.server import webui_app, set_app, get_app


@pytest.fixture(scope="session")
def client(tmp_path_factory) -> TestClient:
    app = MainApp(data_storage_path=tmp_path_factory.mktemp("test", numbered=True),
                  database_file="memory")
    set_app(app)

    client = TestClient(webui_app)
    return client


@pytest.fixture(autouse=True)
async def project():
    app = get_app()

    project_coro = await app.project_manager.new_project("TestProject")
    yield project_coro
    await app.project_manager.delete_project(project_coro)


@pytest.mark.asyncio
async def test_allprojects(client, project) -> None:
    response = client.get("/api/allprojects")
    assert response.status_code == 200
    content = response.json()
    assert 0 == len(content)

    # generate the new project
    proj = await project

    response = client.get("/api/allprojects")
    assert response.status_code == 200
    content = response.json()
    assert 1 == len(content)
    assert proj.name in content.values()


@pytest.mark.asyncio
async def test_project_id(client, project) -> None:

    # start with no project
    response = client.get("/api/project/id")
    assert response.status_code == 404

    p = await project
    response = client.get("/api/project/id")
    assert response.status_code == 200
    project_id = ProjectId.model_validate_json(response.json())
    assert project_id.pid == p.pid
