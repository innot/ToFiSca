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
import pytest_asyncio

from errors import ProjectDoesNotExistError, ProjectNotLoadedError, ProjectAlreadyExistsError
from main import MainApp
from project import Project, ProjectPathEntry


@pytest.fixture
def app(tmp_path):
    app = MainApp(data_storage_path=tmp_path, database_file="memory")
    return app


@pytest_asyncio.fixture
async def project(app) -> Project:
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
async def test_load_project(app, project):

    project_new = await Project.load_project(app, project.pid)

    assert project_new.pid == project.pid

    # test non-existing project
    with pytest.raises(ProjectDoesNotExistError):
        await Project.load_project(app, 999)


@pytest.mark.asyncio
async def test_name(app, project):
    p = Project(app, 1)

    with pytest.raises(ProjectNotLoadedError):
        _ = p.name

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
async def test_delete_storage(app, project):

    for path_entry in project.all_paths.values():
        # create directory and a single file in it
        path = project.resolve_path(path_entry)
        file = path / path_entry.name
        file.touch()

    await project._delete_storage()

    for path_entry in project.all_paths.values():
        path = Path(path_entry.resolved)
        assert path.exists() is False

@pytest.mark.asyncio
async def test_paths(app, project):

    # test all_paths
    all_paths = project.all_paths
    assert "project" in all_paths.keys()
    assert len(all_paths) == len(project._paths)

    # test get_path
    pp = await project.get_path("project")
    assert pp.name == "project"
    project.resolve_path(pp)    # create the path for real

    # update path
    pp.path = "${pid} - ${name}"
    ret_val = await project.update_path(pp)
    pp2 = await project.get_path("project")
    assert pp2.name == "project"
    assert pp2.path == "${pid} - ${name}"
    assert Path(pp2.resolved).name == f"{project.pid} - {project.name}"
    assert ret_val == pp2

    # check that it has been stored in the database
    project_new = await app.project_manager.load_project(project.pid, disable_cache=True)
    pe = await project_new.get_path("project")
    assert pe.path == "${pid} - ${name}"
    assert Path(pe.resolved).name == f"{project.pid} - {project.name}"

    # check that the folder has been renamed
    path = Path(pp.resolved)
    assert path.exists()
    assert path.is_dir()
    assert path.name == f"{project.pid} - {project.name}"


    # test invalid paths
    with pytest.raises(KeyError):
        await project.get_path("foo")

    pe.name = "bar"
    with pytest.raises(KeyError):
        await project.update_path(pe)

@pytest.mark.asyncio
async def test_resolve_path(app):
    pid = await app.config_database.create_project("foobar")
    project = Project(app, pid)
    await project.load()

    root = Path(os.path.abspath(os.sep))

    entry = ProjectPathEntry(name="test", path="", resolved="")

    entry.path = "/foo/bar/baz"
    assert project.resolve_path(entry, create_folder=False) == root / entry.path

    entry.path = "Project ${name} ${pid} baz"
    assert project.resolve_path(entry, create_folder=False).name == f"Project {project.name} {pid} baz"

    entry.path = "/${project}/foo"
    assert project.resolve_path(entry, create_folder=False) == root / f"/{project.name}/foo"

    entry.path = "/${scanned}/foo"
    assert project.resolve_path(entry, create_folder=False) == root / f"/{project.name}/scanned_images/foo"

    entry.path = "/${final}/foo"
    assert project.resolve_path(entry, create_folder=False) == root / f"/{project.name}/final_images/foo"

    # check that circular templates are caught
    entry = project.all_paths["scanned"]
    entry.path = "${scanned}/foo"
    await project.update_path(entry)
    with pytest.raises(ValueError):
        project.resolve_path(entry, create_folder=False)

    # resolve for real and check that the folder was created
    entry = await project.get_path("project")
    path = project.resolve_path(entry)
    assert path.exists() is True
    assert path.is_absolute() is True
    assert path.is_dir() is True
    assert path.name == project.name
