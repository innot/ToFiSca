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

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Self, Any, NewType

from pydantic import BaseModel, Field
from typing_extensions import override

from configuration.database import ConfigDatabase, Scope


class DataNotFoundError(Exception):
    """
    The requested data could not be loaded from the database.
    """


ChangeEventCallback = NewType("ObserverCallback", Callable[[Self, str, any, any], None])


class FieldChangedObserverMixin:
    """
    This Mixin can make ConfigItems observable.

    Whenever a managed field of the ConfigItem is changed, all registered observers are called
    with the full ConfigItem object, the name of the changed field, the new value and the previous value
    as arguments (see :ref:type:`ChangeEventCallback`).
    """

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)

        # a set of all observers
        self._observers: set[ChangeEventCallback] = set()

        # Set of all pending callback asyncio tasks. Needed for cleanup if this object gets garbage collected.
        self._observer_tasks: set[asyncio.Task] = set()

    def add_observer_callback(self, callback: ChangeEventCallback) -> None:
        """
        Register the callback function as an observer.
        If the same Callback is registered multiple times, it will be called only once.
        """
        self._observers.add(callback)

    def remove_observer_callback(self, callback: ChangeEventCallback) -> None:
        """
        Remove the callback function from the list of observers.
        """
        if callback in self._observers:
            self._observers.remove(callback)

    def __del__(self):
        # cancel all tasks that might not yet be finfished
        for task in self._observer_tasks:
            task.cancel()

    def __setattr__(self, name: str, new_value: Any) -> None:
        # if the attribute is one of the managed fields, then - if the value has changed -
        # all observers will be notified
        try:
            old_value = object.__getattribute__(self, name)
        except AttributeError:
            old_value = None
        super().__setattr__(name, new_value)

        if isinstance(self,ConfigItem):
            # todo: what to do if the is not the case? check with pydantic v3 where this is supposed to change.
            # for now there will be no observers called if this mixin is not mixed to a pydantic BaseModel.
            if name in self.__class__.model_fields:
                if old_value != new_value:
                    for observer in self._observers:
                        task = asyncio.create_task(observer(self, name, old_value, new_value))
                        self._observer_tasks.add(task)
                        task.add_done_callback(lambda _: self._observer_tasks.remove(task))


class ConfigItem(BaseModel):

    def __init__(self, /, **kwargs):
        super().__init__(**kwargs)

    async def store(self, database: ConfigDatabase, scope: Scope | int = Scope.GLOBAL) -> None:
        """
        Store the data of this model to the configuration database.
        By default, the scope is for a Global setting. However, if the scope is
        set to a project id, then the data is stored only for this project.
        The data is stored as an JSON object with a key derived from the Class name of this ConfigItem.
        For example,

        .. code: python
            class MySettings(ConfigItem): ...

            MySettings().store()

        will store MySettings with the key `ConfigItem.MySettings`

        :param scope: Project id number. Default is Scope.Global.
        """
        json = self.model_dump_json()
        await database.store_setting(self.get_qualified_name(), json, scope)

    async def retrieve(self, database: ConfigDatabase, scope: Scope | int = Scope.GLOBAL) -> Self:
        """
        Retrieve the data for this Item from the database and set the model fields.

        By default, the scope is for a Global setting.
        However, if the scope is set to a project id, then the data is taken from the project scope.
        If the project scope does not exist, it falls back to the globalscope.

        If there is nothing in the Global scope, all fields are reset to their default value.

        """
        json = await database.retrieve_setting(self.get_qualified_name(), scope)
        if json is None:
            # leave the model untouched
            return self
        new_item = self.model_validate_json(json)
        self.copy_from(new_item)
        return self

    def copy_from(self, item: ConfigItem):
        """
        Copy all managed fields from the given ConfigItem into this item.
        """
        # todo: is this method needed or would pydantic.model_copy() work
        for field, _ in self.model_dump().items():
            value = getattr(item, field)
            setattr(self, field, value)

    def get_qualified_name(self) -> str:
        """
        Get a qualified name of this class that includes all superclass names.

        .. code:: python
            class SomeItem(ConfigItem):
                pass

            class AnotherItem(SomeItem):
                pass

            print(AnotherItem().get_qualified_name())

            > 'someitem.anotheritem'

        The returned string can be used as a key to store the item in the database.
        """
        mro_list = self.__class__.__mro__
        names_list: list[str] = []
        for c in mro_list:
            if c is ConfigItem or c is ProjectItem or c is NamedProjectItem:
                break
            if c is FieldChangedObserverMixin:
                # skip the mixin
                continue
            names_list.append(c.__name__.lower())

        names_list.reverse()

        name = ".".join(names_list)

        return name

    def clear(self):
        """
        Set all fields to their default values.
        """
        for field, field_info in self.__class__.model_fields.items():
            if field_info.default_factory:
                default_value = field_info.default_factory()
            else:
                default_value = field_info.default
            setattr(self, field, default_value)
        self.model_fields_set.clear()


class ProjectItem(ConfigItem):
    """
    Extends ConfigItem to mark this item as a per-Project setting item.
    Upon instantiation, this class needs a valid project id number which is used
    to store and retrieve the item specifically for this project.

    :param pid: The project id number. Must be valid, otherwise the store/retrieve methods will raise an Error.
    """

    pid: int = Field(-1, exclude=True)

    @override
    async def store(self, database: ConfigDatabase, *args):
        if not await database.is_valid_project_id(self.pid):
            return ValueError(f"{self._pid} is not a valid project id.")
        await super(ProjectItem, self).store(database, scope=self.pid)

    async def store_global(self, database: ConfigDatabase):
        """
        Stores this item in the global scope, i.e. as default for new ProjectItems
        """
        await super(ProjectItem, self).store(database, scope=Scope.GLOBAL)

    @override
    async def retrieve(self, database: ConfigDatabase, *args) -> Self:
        return await super(ProjectItem, self).retrieve(database, scope=self.pid)

class NamedProjectItem(ProjectItem):
    """
    A Project item that has a name attribute.

    The name is appended to the key for the setting.

    This can be used for lists of ProjectItems.
    """
    name: str = Field()     # no default; must exist

    @override
    def get_qualified_name(self) -> str:
        name = super().get_qualified_name()
        name += "." + self.name
        return name
