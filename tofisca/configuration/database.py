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

import enum
import sqlite3
import threading
from pathlib import Path

from sqlalchemy import String, ForeignKey, create_engine, Text, Enum, Select, StaticPool, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker, scoped_session
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship


class ConfigDatabaseException(Exception):
    pass


class Scope(enum.Enum):
    DEFAULT = "default"
    GLOBAL = "global"
    PROJECT = "project"

    def __str__(self) -> str:
        return str(self.value)


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    settings: Mapped[list["Setting"]] = relationship()

    def __repr__(self) -> str:
        return f"Project(id={self.id!r}, {self.name!r})"


class Setting(Base):
    __tablename__ = 'config_store'
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(256))
    value: Mapped[str] = mapped_column(Text, nullable=True)
    scope: Mapped[Scope] = mapped_column(Enum(Scope), nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)
    project: Mapped["Project"] = relationship(back_populates="settings")

    def __repr__(self) -> str:
        if self.scope == Scope.DEFAULT:
            scope = "default value"
        elif self.scope == Scope.GLOBAL:
            scope = "global value"
        else:
            scope = f"project {self.project}"
        return f"Setting({self.key!r}: {self.value!r}, Scope {scope})"


class ConfigDatabase:
    _db_instance: ConfigDatabase | None = None
    """Singleton ConfigDatabase instance"""

    @classmethod
    def db(cls):
        """
        Get the singleton ConfigDatabase instance.
        May be `None` if the database has not been instantiated.
        """
        return cls._db_instance

    @classmethod
    def _delete_singleton(cls):
        """
        Delete the Singleton ConfigDatabase instance so a new instance can be created.
        This is supposed to be used for unit testing.
        """
        cls._db_instance = None

    def __new__(cls, databasefile: Path | str = None, debug=False) -> ConfigDatabase:
        # Check if the class has already been instantiated.
        # If yes return the class Singleton
        if cls._db_instance:
            # raise an exception if a different databasefile was given
            current_db_file = cls._db_instance._db_file
            if databasefile != current_db_file:
                raise RuntimeError(
                    f"Re-instantiating with different databas path. new:{databasefile}, existing: {current_db_file}")
            return cls._db_instance

        cls._db_instance = super().__new__(cls)
        return cls._db_instance

    def __init__(self, databasefile: Path | str, debug=False):

        if databasefile is None:
            raise ValueError("databasefile cannot be None")

        if databasefile == "memory":
            # Memory only db for unit test
            self.connection = sqlite3.connect(":memory:", check_same_thread=False)
            self.db_engine = create_engine("sqlite+pysqlite://",
                                           creator=lambda: self.connection,
                                           poolclass=StaticPool,
                                           echo=debug)
        else:
            databasefile = Path(databasefile)
            if not databasefile.parent.exists():
                raise FileNotFoundError(f"Cannot create database. Directory {databasefile.parent} does not exist")

            self.db_engine = create_engine(f"sqlite+pysqlite:///{databasefile}", echo=debug)

        self._db_file = databasefile

        Base.metadata.create_all(self.db_engine)

        session_factory = sessionmaker(bind=self.db_engine)
        self.Session = scoped_session(session_factory)

        self._db_write_lock = threading.Lock()

    def __del__(self) -> None:
        try:
            self.Session.remove()
            self.connection.close()
        except AttributeError:
            # this happens if there is an Exception in __init__ and the session is not created.
            # Or there is no connection set (only exists when using a memory database)
            pass

    async def retrieve_setting(self, key: str, scope: int | str | Scope = Scope.GLOBAL) -> str | None:
        """
        Get the value for the given key from the database.

        The retrieved value will be from the given scope (Project, global or default).
        If the value is not available in the given scope, it will be taken from a higher scope.

        :param key: The key of the item to retrieve
        :param scope: Either the name or id of a project or Scope.GLOBAL resp. Scope.DEFAULT.
        :returns: The stored value or `None` if no value is stored for the given key.
        """
        setting = await self._retrieve_setting(key, scope)
        if setting is None:
            return None
        return setting.value

    async def _retrieve_setting(self, key: str, scope: str | int | Scope = Scope.GLOBAL) -> Setting | None:
        """
        Get the Setting object for the given key and scope from the database.

        The retrieved value will be from the given scope (Project, global or default).
        If the value is not available in the given scope, it will be taken from a higher scope.

        :param key: The key of the setting to retrieve.
        :param scope: The scope of the setting to retrieve. Can be Scope.GLOBAL, Scope.DEFAULT or a project name or id.
        """
        real_scope, project_id = await self.get_scope(scope)
        session = self.Session()

        stmt = Select(Setting).where(Setting.key == key).where(Setting.scope <= real_scope)
        if project_id is not None:
            stmt = stmt.where(Setting.project_id == project_id)
        stmt = stmt.order_by(Setting.scope.desc())
        setting = session.scalars(stmt).first()  # the first entry has the lowest hierarchy
        return setting

    async def store_setting(self, key: str, value: str | None, scope: str | int | Scope = Scope.GLOBAL) -> Setting:
        """
        Store the value for the given in the database at the given scope.
        If the key exists at the given scope, the value will be updated and the old value
        will be saved in the value_prev field.

        :returns: The :class:`Setting` object representing the stored value.
        """
        if not isinstance(key, str):
            raise TypeError("key must be a string")
        if scope == Scope.PROJECT:
            raise ValueError("scope argument must be a project name or id number.")

        # get the previous value
        setting = await self._retrieve_setting(key, scope)
        scope, project_id = await self.get_scope(scope)

        if setting is None or setting.scope != scope:
            # create a new setting object
            setting = Setting(key=key, value=value, scope=scope)
            if project_id:
                setting.project_id = project_id
        else:
            # a setting object of with the same scope already exists.
            # update it
            setting.value = value

        # update and commit
        with self._db_write_lock:  # just in case...
            session = self.Session()
            session.add(setting)
            session.commit()
        return setting

    async def get_project_name(self, pid: int) -> str:
        proj = await self.get_project(pid)
        return str(proj.name)

    async def get_project(self, project: str | int) -> Project | None:
        """
        Get the project with the given name or id number.
        If the name/id does not match an existing project `None` is returned.

        :returns: a Project object, or `None`
        :raises: ValueError if the project argument is invalid.
        """

        if isinstance(project, int):
            stmt = Select(Project).where(Project.id == project)
        elif isinstance(project, str):
            stmt = Select(Project).where(Project.name == project)
        else:
            raise TypeError(f"'{project}' is not a valid name or id for a project")

        session = self.Session()
        project = session.scalars(stmt).first()
        return project

    async def create_project(self, name: str | None = None) -> int:
        """

        Create a new project with the given name.
        If no name is given, a name with "Project {id}" will be generated.
        :param name: The name of the new project.
        :returns: The id of the new project.
        """

        if name is not None:
            if not isinstance(name, str):
                raise TypeError("Project name must be a string")
            # check if a project with the name already exists
            project = await self.get_project(name)
            if project:
                raise ValueError(f"Project {name} already exists")
        else:
            name = ""  # Placeholder to be replaced by project id

        # create a new project
        session = self.Session()
        project = Project(name=name)
        with self._db_write_lock:  # just in case...
            session.add(project)
            session.commit()

            if project.name == "":
                project.name = f"Project {project.id}"
                session.commit()

        return project.id

    async def all_projects(self) -> dict[int, str]:
        """
        Returns the id's and names of all Projects stored in the database.
        :returns: a dict mapping project id to the project name.
        """
        session = self.Session()
        proj_list = session.scalars(select(Project).order_by(Project.id)).all()

        result: dict[int, str] = {}
        for proj in proj_list:
            result[proj.id] = proj.name

        return result

    async def change_project_name(self, project_id: int, new_name: str) -> None:

        with self._db_write_lock:  # just in case...
            session = self.Session()
            project = session.scalars(select(Project).where(Project.id == project_id)).first()
            project.name = new_name
            session.commit()

    async def get_scope(self, scope: str | int | Scope) -> tuple[Scope, int | None]:
        """
        Get the scope and optionally project id from the given input.
        :param scope: Either a :class:´Scope´ value,
                      or a project name or project id number.
        """

        project_id: int | None = None

        if scope == Scope.DEFAULT:
            real_scope = Scope.DEFAULT
        elif scope == Scope.GLOBAL:
            real_scope = Scope.GLOBAL
        else:
            # the scope is a project, either by name or by id
            real_scope = Scope.PROJECT
            project = await self.get_project(scope)
            if not project:
                raise ValueError(f"Project '{scope}' does not exist")
            # noinspection PyTypeChecker
            project_id = project.id

        return real_scope, project_id

    async def is_valid_project_id(self, pid: int) -> bool:
        session = self.Session()
        return session.query(Project.id).filter_by(id=pid).first() is not None
