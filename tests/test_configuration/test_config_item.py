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

import pytest

from configuration.config_item import ConfigItem, FieldChangedObserverMixin
from configuration.database import ConfigDatabase


@pytest.fixture
def database():
    db = ConfigDatabase("memory")
    return db


@pytest.mark.asyncio
async def test_get_qualified_name(database):
    class TestItem(ConfigItem):
        pass

    class TestChildItem(FieldChangedObserverMixin, TestItem):
        pass

    ti = TestChildItem()
    assert "testitem.testchilditem" == ti.get_qualified_name()


@pytest.mark.asyncio
async def test_store_and_retrieve(database):
    class TestItem(ConfigItem):
        value1: str = ""
        value2: int = 0

    ti = TestItem(value1="foobar", value2=1234)
    await ti.store(database)

    ti2 = TestItem()
    await ti2.retrieve(database)

    assert "foobar" == ti2.value1
    assert 1234 == ti2.value2

    # noinspection PyArgumentList
    ti3 = TestItem()
    await ti3.retrieve(database)
    assert "foobar" == ti3.value1
    assert 1234 == ti3.value2


@pytest.mark.asyncio
async def test_callback(database):
    class TestItem(FieldChangedObserverMixin, ConfigItem):
        value1: str = "old"

    async def callback(item: ConfigItem, name: str, old_value: any, new_value: any):
        assert isinstance(item, TestItem)
        assert "value1" == name
        assert "old" == old_value
        assert "new" == new_value

    ti = TestItem()
    ti.add_observer_callback(callback)
    ti.value1 = "new"
    assert "new" == ti.value1
