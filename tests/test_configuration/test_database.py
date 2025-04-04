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
import asyncio
import threading
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import Engine

from tofisca.configuration.database import ConfigDatabase, Scope, Project, Setting


@pytest.fixture
def test_db():
    db = ConfigDatabase("memory")
    return db


@pytest.mark.asyncio
async def test_instantiation():
    db = ConfigDatabase("memory")
    assert db is not None
    assert isinstance(db.db_engine, Engine)

    # check session
    session = db.Session()
    assert session is not None


@pytest.mark.asyncio
async def test_file_database(tmp_path):
    db_file = tmp_path / "settings.sqlite"
    db = ConfigDatabase(db_file)
    assert db is not None
    assert db_file.exists()
    assert db_file.stat().st_size > 0  # file does have content


@pytest.mark.asyncio
async def test_errors():
    with pytest.raises(FileNotFoundError):
        ConfigDatabase(Path("/path/to/nowhere"))


@pytest.mark.asyncio
async def test_get_scope(test_db):
    scope, _ = await test_db.get_scope(Scope.DEFAULT)
    assert Scope.DEFAULT == scope
    scope, _ = await test_db.get_scope(Scope.GLOBAL)
    assert Scope.GLOBAL == scope

    pid_1 = await test_db.create_project("test_scope")
    scope, pid_2 = await test_db.get_scope("test_scope")
    assert Scope.PROJECT == scope
    assert pid_1 == pid_2

    scope, pid_2 = await test_db.get_scope(pid_1)
    assert Scope.PROJECT == scope
    assert pid_1 == pid_2

    # test invalid input
    with pytest.raises(ValueError):
        await test_db.get_scope("foobar")
    with pytest.raises(ValueError):
        # noinspection PyTypeChecker
        await test_db.get_scope([])


@pytest.mark.asyncio
async def test_create_project(test_db):
    pid = await test_db.create_project('test')
    assert pid is not None
    assert 1 == pid

    project = await test_db.get_project(pid)
    assert project is not None
    assert isinstance(project, Project)

    project = await test_db.get_project('test')
    assert project is not None
    assert 1 == project.id

    pid2 = await test_db.create_project('test2')
    assert 2 == pid2

    # test project without name
    pid3 = await test_db.create_project()
    assert 3 == pid3
    project = await test_db.get_project(pid3)
    assert str(pid3) in project.name

    # test invalid input
    for arg in ["test", "test2", [], object()]:
        with pytest.raises((ValueError, TypeError)):
            print(f"{arg} = {arg!r}")
            await test_db.create_project(arg)


@pytest.mark.asyncio
async def test_delete_project(test_db):
    # first create a project
    pid = await test_db.create_project()
    assert await test_db.get_project(pid) is not None

    # add setting that should be deleted a well
    await test_db.store_setting("test_key", "test_value", pid)
    assert await test_db.retrieve_setting("test_key", pid) == "test_value"

    await test_db.delete_project(pid)

    assert await test_db.get_project(pid) is None

    with pytest.raises(ValueError):
        assert await test_db.retrieve_setting("test_key", pid) is None


@pytest.mark.asyncio
async def test_store_and_retrieve(test_db):
    # Test with Scope.DEFAULT
    setting = await test_db.store_setting("foo", "default", Scope.DEFAULT)
    assert setting is not None
    assert isinstance(setting, Setting)
    assert "default" == await test_db.retrieve_setting("foo", Scope.DEFAULT)
    assert "default" == await test_db.retrieve_setting("foo")
    setting = await test_db._retrieve_setting("foo")
    assert "default" == setting.value
    assert "foo" == setting.key
    assert Scope.DEFAULT == setting.scope
    assert setting.project_id is None
    assert setting.project is None

    # Test with Scope.GLOBAL
    await test_db.store_setting("foo", "global", Scope.GLOBAL)
    assert "global" == await test_db.retrieve_setting("foo")

    # test Scope.Project
    pid = await test_db.create_project("testproject")
    await test_db.store_setting("foo", "project", pid)
    assert "project" == await test_db.retrieve_setting("foo", pid)
    setting = await test_db._retrieve_setting("foo", pid)
    assert pid == setting.project_id
    assert await test_db.get_project(pid) == setting.project

    # test other scopes
    assert "global" == await test_db.retrieve_setting("foo", Scope.GLOBAL)
    assert "default" == await test_db.retrieve_setting("foo", Scope.DEFAULT)

    # test invalid keys and values
    setting = await test_db._retrieve_setting("humbug")
    assert setting is None

    value = await test_db.retrieve_setting("humbug")
    assert value is None

    with pytest.raises(TypeError):
        # noinspection PyTypeChecker
        await test_db.store_setting(123, "humbug")
    with pytest.raises(ValueError):
        await test_db.store_setting("foo", "humbug", Scope.PROJECT)


@pytest.mark.asyncio
async def test_threading(test_db):
    async def thread_runner():
        nonlocal test_db
        await test_db.create_project("thread_1")
        await test_db.store_setting("foo.bar", "default", Scope.DEFAULT)
        await test_db.store_setting("foo.bar", "global", Scope.GLOBAL)
        await test_db.store_setting("foo.bar", "project", "thread_1")

        assert "project" == await test_db.retrieve_setting("foo.bar", "thread_1")
        assert "global" == await test_db.retrieve_setting("foo.bar", Scope.GLOBAL)
        assert "default" == await test_db.retrieve_setting("foo.bar", Scope.DEFAULT)

    def loop_runner():
        asyncio.run(thread_runner())

    thread = threading.Thread(target=loop_runner)
    thread.start()
    await test_db.create_project("no_thread")
    thread.join()

    assert "project" == await test_db.retrieve_setting("foo.bar", "thread_1")
    assert "global" == await test_db.retrieve_setting("foo.bar", Scope.GLOBAL)
    assert "default" == await test_db.retrieve_setting("foo.bar", Scope.DEFAULT)
    assert await test_db.get_project("no_thread") is not None

    async def threadrunner2(idx: int):
        await test_db.store_setting(f"key/{idx}", f"value={idx}")

    def loop_runner2(idx: int):
        asyncio.run(threadrunner2(idx))

    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in executor.map(loop_runner2, (idx for idx in range(10))):
            pass
        executor.shutdown(wait=True)

    for idx in range(10):
        assert f"value={idx}" == await test_db.retrieve_setting(f"key/{idx}")


@pytest.mark.asyncio
async def test_str_repr(test_db):
    pid = await test_db.create_project("teststr")
    project = await test_db.get_project(pid)
    assert repr(project).startswith("Project")

    setting = await test_db.store_setting("foo", "baz", Scope.DEFAULT)
    assert repr(setting).startswith("Setting")
    assert "default" in repr(setting)

    setting = await test_db.store_setting("foo", "baz", Scope.GLOBAL)
    assert "global" in repr(setting)

    setting = await test_db.store_setting("foo", "baz", pid)
    assert "project" in repr(setting)


@pytest.mark.asyncio
async def test_list_projects(test_db):
    expected = {}
    for i in range(1, 11):
        name = f"project_{i}"
        pid = await test_db.create_project(name)
        expected[pid] = name

    result = await test_db.all_projects()

    assert expected == result


@pytest.mark.asyncio
async def test_change_project_name(test_db):
    pid = await test_db.create_project("testchange")
    await test_db.change_project_name(pid, "new name")

    project = await test_db.get_project(pid)
    assert "new name" == project.name


@pytest.mark.asyncio
async def test_is_valid_project_id(test_db):
    pid = await test_db.create_project("foobar")
    assert await test_db.is_valid_project_id(pid)
    for i in range(-1, 10):
        if i == pid: continue
        assert not await test_db.is_valid_project_id(i)
