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

from tofisca.configuration import ConfigDatabase, ConfigItem, FieldChangedObserverMixin


class MyTestCase(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.db = ConfigDatabase("memory")

    async def asyncTearDown(self):
        ConfigDatabase._delete_singleton()
        self.db = None

    async def test_get_qualified_name(self):
        class TestItem(ConfigItem):
            pass

        class TestChildItem(FieldChangedObserverMixin, TestItem):
            pass

        ti = TestChildItem()
        self.assertEqual("testitem.testchilditem", ti.get_qualified_name())

    async def test_store_and_retrieve(self):
        class TestItem(ConfigItem):
            value1: str = ""
            value2: int = 0

        ti = TestItem(value1="foobar", value2=1234)
        await ti.store()

        ti2 = TestItem()
        await ti2.retrieve()

        self.assertEqual("foobar", ti2.value1)
        self.assertEqual(1234, ti2.value2)

        # noinspection PyArgumentList
        ti3 = TestItem()
        await ti3.retrieve()
        self.assertEqual("foobar", ti3.value1)
        self.assertEqual(1234, ti3.value2)

    async def test_callback(self):
        class TestItem(FieldChangedObserverMixin, ConfigItem):
            value1: str = "old"

        async def callback(item: ConfigItem, name: str, old_value: any, new_value: any):
            self.assertIsInstance(item, TestItem)
            self.assertEqual("value1", name)
            self.assertEqual("old", old_value)
            self.assertEqual("new", new_value)

        ti = TestItem()
        ti.add_observer_callback(callback)
        ti.value1 = "new"
        self.assertEqual("new", ti.value1)


if __name__ == '__main__':
    unittest.main()
