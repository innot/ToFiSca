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
import logging
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

        self._db_access_lock = threading.Lock()

    def __del__(self) -> None:
        try:
            if hasattr(self, "connection"):
                self.connection.close()
            if hasattr(self, "session"):
                self.Session.remove()
        except BaseException as e:
            logging.warn(f"Excpetion in ComfogDatabase.__del__: {str(e)}")

    async def retrieve_setting(self, key: str, scope: int | str | Scope = Scope.GLOBAL) -> str | None:
        """
        Get the *value* for the given key from the database.

        The retrieved value will be from the given scope (Project, global or default).
        If the value is not available in the given scope, it will be taken from a higher scope.

        :param key: The key of the setting to retrieve.
        :param scope: The scope of the setting to retrieve.
                      It Can be Scope.GLOBAL, Scope.DEFAULT or a project name or id.
        :returns: The value of the setting or None if the given key does not exist
        :raises: ValueError if the project or scope does not exist.
        """
        setting = await self._retrieve_setting(key, scope)
        if setting is None:
            return None
        return setting.value

    async def _retrieve_setting(self, key: str, scope: str | int | Scope = Scope.GLOBAL) -> Setting | None:
        """
        Get the *Setting* object for the given key and scope from the database.

        The retrieved value will be from the given scope (Project, global or default).
        If the value is not available in the given scope, it will be taken from a higher scope.

        :param key: The key of the setting to retrieve.
        :param scope: The scope of the setting to retrieve.
                      It Can be Scope.GLOBAL, Scope.DEFAULT or a project name or id.
        :returns: A :class:`Setting` object or None if the given key does not exist
        :raises: ValueError if the project or scope does not exist.
        """
        real_scope, project_id = await self.get_scope(scope)

        stmt = Select(Setting).where(Setting.key == key).where(Setting.scope <= real_scope)
        if project_id is not None:
            stmt = stmt.where(Setting.project_id == project_id)
        stmt = stmt.order_by(Setting.scope.desc())
        with self._db_access_lock:
            session = self.Session()
            setting = session.scalars(stmt).first()  # the first entry has the lowest hierarchy
        return setting

    async def store_setting(self, key: str, value: str | None, scope: str | int | Scope = Scope.GLOBAL) -> Setting:
        """
        Store the value for the given in the database at the given scope.
        If the key exists in the given scope, the value will be updated and the old value
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
        with self._db_access_lock:  # just in case...
            session = self.Session()
            session.add(setting)
            session.commit()
        return setting

    async def get_project_name(self, pid: int) -> str | None:
        """
        Get the name of the project with the given pid.

        :param pid:
        :return: The name or `None` if the project does not exist
        """
        proj = await self.get_project(pid)
        if proj is None:
            return None
        else:
            return str(proj.name)

    async def get_project(self, project: str | int) -> Project | None:
        """
        Get the project with the given name or id number.
        If the name/id does not match an existing project, `None` is returned.

        :returns: A Project object or `None` if the project does not exist.
        """

        if isinstance(project, int):
            stmt = Select(Project).where(Project.id == project)
        elif isinstance(project, str):
            stmt = Select(Project).where(Project.name == project)
        else:
            raise ValueError(f"'{project}' is not a valid name or id for a project")

        with self._db_access_lock:
            session = self.Session()
            project = session.scalars(stmt).first()
        return project

    async def create_project(self, name: str | None = None) -> int:
        """
        Create a new project with the given name.
        If no name is given, a name with "Project {id}" will be generated.
        :param name: The name of the new project.
        :returns: The id of the new project.
        :raises: ValueError if the project already exists.
        """

        if name is not None:
            if not isinstance(name, str):
                raise TypeError("Project name must be a string")
            # check if a project with the name already exists
            project = await self.get_project(name)
            if project is not None:
                raise ValueError(f"Project '{name}' already exist")
        else:
            name = ""  # Placeholder to be replaced by project id

        # create a new project
        project = Project(name=name)
        with self._db_access_lock:  # just in case...
            session = self.Session()
            session.add(project)
            session.commit()

            # set the default project name here, as we now have an project id number
            if project.name == "":
                project.name = f"Project {project.id}"
                session.commit()

        return project.id

    async def delete_project(self, pid: int) -> int | None:
        """
        Delete the project with the given id.

        :param pid: The pid of the project to delete.
        :return: The pid of the deleted project or `None` if the project did not exist
        """
        with self._db_access_lock:  # just in case...
            session = self.Session()
            project = session.get(Project, pid)
            if project is None:
                return None
            session.delete(project)
            session.commit()
        return pid

    async def all_projects(self) -> dict[int, str]:
        """
        Returns the id's and names of all Projects stored in the database.
        :returns: a dict mapping project id to the project name.
        """
        with self._db_access_lock:  # just in case...
            session = self.Session()
            proj_list = session.scalars(select(Project).order_by(Project.id)).all()

        result: dict[int, str] = {}
        for proj in proj_list:
            result[proj.id] = proj.name

        return result

    async def change_project_name(self, project_id: int, new_name: str) -> None:

        with self._db_access_lock:  # just in case...
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

        if scope is Scope.DEFAULT:
            real_scope = Scope.DEFAULT
        elif scope is Scope.GLOBAL:
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
        with self._db_access_lock:  # just in case...
            session = self.Session()
            return session.query(Project.id).filter_by(id=pid).first() is not None
