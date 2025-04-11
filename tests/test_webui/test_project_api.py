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
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from main import MainApp
from project import ProjectPathEntry
from web_ui.api_errors import APIInvalidDataError
from web_ui.server import webui_app, set_app, get_app


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


@pytest.mark.asyncio
async def test_project_paths(client, project) -> None:
    response = client.get("/api/project/allpaths")
    assert response.status_code == 200
    paths = response.json()
    assert "project" in paths
    assert "scanned" in paths
    scanned_path = ProjectPathEntry.model_validate(paths["scanned"])
    assert isinstance(scanned_path, ProjectPathEntry)
    assert scanned_path.name == "scanned"

    # change path and write back
    scanned_path.path = "/foo/${name}/bar"
    response = client.put("/api/project/path", json=scanned_path.model_dump())
    assert response.status_code == 200
    path = ProjectPathEntry.model_validate(response.json())
    assert path.resolved == str(Path("/foo/TestProject/bar/").resolve())

    # and read again
    response = client.get(f"/api/project/path?name={scanned_path.name}")
    assert response.status_code == 200
    path = ProjectPathEntry.model_validate(response.json())
    assert path.path == "/foo/${name}/bar"


@pytest.mark.asyncio
def test_film_data(client, project):
    pass
