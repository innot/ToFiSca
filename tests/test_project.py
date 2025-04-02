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

import unittest

from tofisca.configuration import ConfigDatabase
from tofisca.project import Project
from tofisca.project import ProjectStateEnum


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = ConfigDatabase("memory")

    async def asyncTearDown(self):
        ConfigDatabase.delete_singleton()

    async def test_project(self):
        pid = await self.db.create_project()
        project = Project(pid)
        self.assertIsNotNone(project)

        await project.load()
        self.assertEqual("Project 1", project.name)
        self.assertEqual(pid, project.pid)

        self.assertEqual(ProjectStateEnum.NEW, project.state)


if __name__ == '__main__':
    unittest.main()
