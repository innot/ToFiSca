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

from errors import ProjectDoesNotExistError, ProjectNotLoadedError, ProjectAlreadyExistsError
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
    # noinspection PyTypeChecker
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
async def test_load_project(app, project_coro):
    project_orig = await project_coro  # generate one project

    project_new = await Project.load_project(app, project_orig.pid)

    assert project_new.pid == project_orig.pid

    # test non-existing project
    with pytest.raises(ProjectDoesNotExistError):
        await Project.load_project(app, 999)


@pytest.mark.asyncio
async def test_name(app, project_coro):
    p = Project(app, 1)

    with pytest.raises(ProjectNotLoadedError):
        _ = p.name

    # for the next tests we need a real project
    project = await project_coro

    # test some invalid names
    for name in ['foo\nbar', 'foo/bar', 'foo"bar', 'foo:bar']:
        with pytest.raises(ValueError):
            await project.set_name(name)

    # test duplicate name
    project_dup = await app.project_manager.new_project("test")
    with pytest.raises(ProjectAlreadyExistsError):
        await project.set_name(project_dup.name)

    # test valid names
    old_name = project.name
    await project.set_name(project.name)
    assert project.name == old_name
    await project.set_name("foo bar baz")
    assert project.name == "foo bar baz"


@pytest.mark.asyncio
async def test_delete_storage(app, project_coro):
    # generate some content
    project = await project_coro

    for path_entry in project.all_paths.values():
        # create directory and a single file in it
        path = project.resolve_path(path_entry.path)
        file = path / path_entry.name
        file.touch()

    await project._delete_storage()

    for path_entry in project.all_paths.values():
        path = Path(path_entry.resolved)
        assert path.exists() is False


@pytest.mark.asyncio
async def test_resolve_path(app):
    pid = await app.config_database.create_project("foobar")
    project = Project(app, pid)
    await project.load()

    root = Path(os.path.abspath(os.sep))

    path = "/foo/bar/baz"
    assert project.resolve_path(path, create_folder=False) == root / path

    path = "Project ${name} ${pid} baz"
    assert project.resolve_path(path, create_folder=False).name == f"Project {project.name} {pid} baz"

    path = "/${project}/foo"
    assert project.resolve_path(path, create_folder=False) == root / f"/{project.name}/foo"

    path = "/${scanned}/foo"
    assert project.resolve_path(path, create_folder=False) == root / f"/{project.name}/scanned_images/foo"

    path = "/${final}/foo"
    assert project.resolve_path(path, create_folder=False) == root / f"/{project.name}/final_images/foo"

    # resolve for real and check that the folder was created
    path = project.resolve_path("Resolve")
    assert path.exists() is True
    assert path.is_absolute() is True
    assert path.is_dir() is True
    assert path.name == "Resolve"
