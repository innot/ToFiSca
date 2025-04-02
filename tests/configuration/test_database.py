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
import tempfile
import threading
import unittest
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path

from tofisca.configuration.database import _ConfigDatabase, ConfigDatabase, Scope, Project, Setting


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def test_database(self):
        db = _ConfigDatabase("memory")
        self.assertIsNotNone(db)
        self.assertIsNotNone(db.db_engine)

        # check session
        session = db.Session()
        self.assertIsNotNone(session)

    async def test_file_database(self):
        # test file database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "settings.sqlite"
            db = _ConfigDatabase(db_file)
            self.assertIsNotNone(db)
            self.assertTrue(db_file.exists())

            pid = await db.create_project("test")
            self.assertIsNotNone(pid)
            db.Session.remove()
            db.db_engine.dispose()

    async def test_singleton(self):
        db = ConfigDatabase("memory")
        self.assertIsNotNone(db)

        db2 = ConfigDatabase()
        self.assertIs(db2, db)

        with self.assertRaises(RuntimeError):
            ConfigDatabase(databasefile="/path/to/nowhere")

    async def test_errors(self):
        with self.assertRaises(FileNotFoundError):
            _ConfigDatabase(Path("path/to/nowhere"))

    async def test_get_scope(self):
        db = _ConfigDatabase("memory")

        scope, _ = await db.get_scope(Scope.DEFAULT)
        self.assertEqual(Scope.DEFAULT, scope)
        scope, _ = await db.get_scope(Scope.GLOBAL)
        self.assertEqual(Scope.GLOBAL, scope)

        pid_1 = await db.create_project("test_scope")
        scope, pid_2 = await db.get_scope("test_scope")
        self.assertEqual(Scope.PROJECT, scope)
        self.assertEqual(pid_1, pid_2)

        scope, pid_2 = await db.get_scope(pid_1)
        self.assertEqual(Scope.PROJECT, scope)
        self.assertEqual(pid_1, pid_2)

        # test invalid input
        with self.assertRaises(ValueError):
            await db.get_scope("foobar")
        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            await db.get_scope([])

    async def test_project(self):
        db = _ConfigDatabase("memory")

        pid = await db.create_project('test')
        self.assertIsNotNone(pid)
        self.assertEqual(1, pid)

        project = await db.get_project(pid)
        self.assertIsNotNone(project)
        self.assertIsInstance(project, Project)

        project = await db.get_project('test')
        self.assertIsNotNone(project)
        self.assertEqual(1, project.id)

        pid2 = await db.create_project('test2')
        self.assertEqual(2, pid2)

        # test project without name
        pid3 = await db.create_project()
        self.assertEqual(3, pid3)
        project = await db.get_project(pid3)
        self.assertTrue(str(pid3) in project.name)

        # test invalid input
        for arg in ["test", "test2"]:
            with self.assertRaises(ValueError):
                await db.create_project(arg)

        for arg in [123, []]:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                await db.create_project(arg)

        for arg in [[], self]:
            with self.assertRaises(TypeError):
                # noinspection PyTypeChecker
                await db.get_project(arg)

    async def test_store_and_retrieve(self):
        db = _ConfigDatabase("memory")

        # Test with Scope.DEFAULT
        setting = await db.store_setting("foo", "default", Scope.DEFAULT)
        self.assertIsNotNone(setting)
        self.assertIsInstance(setting, Setting)
        self.assertEqual("default", await db.retrieve_setting("foo", Scope.DEFAULT))
        self.assertEqual("default", await db.retrieve_setting("foo"))
        setting = await db._retrieve_setting("foo")
        self.assertEqual("default", setting.value)
        self.assertEqual("foo", setting.key)
        self.assertEqual(Scope.DEFAULT, setting.scope)
        self.assertIsNone(setting.project_id)
        self.assertIsNone(setting.project)

        # Test with Scope.GLOBAL
        await db.store_setting("foo", "global", Scope.GLOBAL)
        self.assertEqual("global", await db.retrieve_setting("foo"))

        # test Scope.Project
        pid = await db.create_project("testproject")
        await db.store_setting("foo", "project", pid)
        self.assertEqual("project", await db.retrieve_setting("foo", pid))
        setting = await db._retrieve_setting("foo", pid)
        self.assertEqual(pid, setting.project_id)
        self.assertEqual(await db.get_project(pid), setting.project)

        # test other scopes
        self.assertEqual("global", await db.retrieve_setting("foo", Scope.GLOBAL))
        self.assertEqual("default", await db.retrieve_setting("foo", Scope.DEFAULT))

        # test invalid keys and values
        setting = await db._retrieve_setting("humbug")
        self.assertIsNone(setting)

        value = await db.retrieve_setting("humbug")
        self.assertIsNone(value)

        with self.assertRaises(TypeError):
            # noinspection PyTypeChecker
            await db.store_setting(123, "humbug")
        with self.assertRaises(ValueError):
            await db.store_setting("foo", "humbug", Scope.PROJECT)

    async def test_threading(self):
        db = _ConfigDatabase("memory")

        async def thread_runner():
            nonlocal db
            await db.create_project("thread_1")
            await db.store_setting("foo.bar", "default", Scope.DEFAULT)
            await db.store_setting("foo.bar", "global", Scope.GLOBAL)
            await db.store_setting("foo.bar", "project", "thread_1")

            self.assertEqual("project", await db.retrieve_setting("foo.bar", "thread_1"))
            self.assertEqual("global", await db.retrieve_setting("foo.bar", Scope.GLOBAL))
            self.assertEqual("default", await db.retrieve_setting("foo.bar", Scope.DEFAULT))

        def loop_runner():
            asyncio.run(thread_runner())

        thread = threading.Thread(target=loop_runner)
        thread.start()
        await db.create_project("no_thread")
        thread.join()

        self.assertEqual("project", await db.retrieve_setting("foo.bar", "thread_1"))
        self.assertEqual("global", await db.retrieve_setting("foo.bar", Scope.GLOBAL))
        self.assertEqual("default", await db.retrieve_setting("foo.bar", Scope.DEFAULT))
        self.assertIsNotNone(await db.get_project("no_thread"))

        async def threadrunner2(idx: int):
            await db.store_setting(f"key/{idx}", f"value={idx}")

        def loop_runner2(idx: int):
            asyncio.run(threadrunner2(idx))

        with ThreadPoolExecutor(max_workers=5) as executor:
            for _ in executor.map(loop_runner2, (idx for idx in range(10))):
                pass
            executor.shutdown(wait=True)

        for idx in range(10):
            self.assertEqual(f"value={idx}", await db.retrieve_setting(f"key/{idx}"))

    async def test_str_repr(self):
        db = _ConfigDatabase("memory")

        pid = await db.create_project("teststr")
        project = await db.get_project(pid)
        self.assertTrue(repr(project).startswith("Project"))

        setting = await db.store_setting("foo", "baz", Scope.DEFAULT)
        self.assertTrue(repr(setting).startswith("Setting"))
        self.assertTrue("default" in repr(setting))

        setting = await db.store_setting("foo", "baz", Scope.GLOBAL)
        self.assertTrue("global" in repr(setting))

        setting = await db.store_setting("foo", "baz", pid)
        self.assertTrue("project" in repr(setting))

    async def test_list_projects(self):
        db = _ConfigDatabase("memory")

        expected = {}
        for i in range(1, 11):
            name = f"project_{i}"
            pid = await db.create_project(name)
            expected[pid] = name

        result = await db.all_projects()

        self.assertDictEqual(expected, result)

    async def test_change_project_name(self):
        db = _ConfigDatabase("memory")

        pid = await db.create_project("testchange")
        await db.change_project_name(pid, "new name")

        project = await db.get_project(pid)
        self.assertEqual("new name", project.name)

    async def test_is_valid_project_id(self):
        db = _ConfigDatabase("memory")

        pid = await db.create_project("foobar")
        self.assertTrue(await db.is_valid_project_id(pid))
        for i in range(-1, 10):
            if i == pid: continue
            self.assertFalse(await db.is_valid_project_id(i))


if __name__ == '__main__':
    unittest.main()
