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
import os
from pathlib import Path
from typing import Coroutine, Any

import pytest

from main import MainApp
from project import Project


@pytest.fixture
def app(tmp_path):
    app = MainApp(data_storage_path=tmp_path, database_file="memory")
    yield app


@pytest.fixture
async def project_coro(app) -> Coroutine[Any, Any, Project]:
    pid = await app.config_database.create_project()
    project = Project(app, pid)
    await project.load()
    return project


@pytest.mark.asyncio
async def test_project(app):
    pid = await app.config_database.create_project()
    project = Project(app, pid)
    assert project is not None

    await project.load()
    assert "Project 1" == project.name
    assert pid == project.pid


@pytest.mark.asyncio
async def test_delete_storage(app, project_coro):
    # generate some content
    project = await project_coro
    project_path = project.resolve_path(project.paths.project_path) # this creates the directory

    project_file = project_path / "project_foo"
    project_file.touch()


    scanned_path = project.resolve_path(project.paths.scanned_images)
    scanned_file = scanned_path / "scanned_bar"
    scanned_file.touch()

    final_path = project.resolve_path(project.paths.final_images)
    final_file = final_path / "scanned_baz"
    final_file.touch()

    await project._delete_storage()
    assert project_path.exists() is False
    assert scanned_path.exists() is False
    assert final_path.exists() is False


@pytest.mark.asyncio
async def test_resolve_path(app):
    pid = await app.config_database.create_project("foobar")
    project = Project(app, pid)
    await project.load()

    root = Path(os.path.abspath(os.sep))

    path = "/foo/bar/baz"
    assert project.resolve_path(path, create_folder=False) == root / path

    path = "Project {project.name} {project.id} baz"
    assert project.resolve_path(path, create_folder=False).name == f"Project {project.name} {pid} baz"

    # resolve for real and check that the folder was created
    path = project.resolve_path("Resolve")
    assert path.exists() is True
    assert path.is_absolute() is True
    assert path.is_dir() is True
    assert path.name == "Resolve"
