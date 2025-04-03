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
import tempfile
import unittest
from pathlib import Path

from tofisca.main import ToFiSca


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncTearDown(self):
        # ensure singleton is deleted
        ToFiSca._delete_singleton()

    def test_singleton(self):
        self.assertIsNone(ToFiSca.app())

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ToFiSca(Path(tmpdir), "memory")

            self.assertIs(app, ToFiSca.app())

            with self.assertRaises(RuntimeError):
                ToFiSca(Path(tmpdir), "memory")

            app._delete_singleton()
            self.assertIsNot(app, ToFiSca(Path(tmpdir), "memory"))

    def test_managers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app = ToFiSca(Path(tmpdir), "memory")

            self.assertIsNotNone(app.project_manager)
            self.assertIsNotNone(app.hardware_manager)
            self.assertEqual(Path(tmpdir), app.data_path)


if __name__ == '__main__':
    unittest.main()
