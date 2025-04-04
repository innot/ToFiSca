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

from main import MainApp
from project import Project


@pytest.fixture
def app(tmp_path):
    app = MainApp(data_storage_path=tmp_path, database_file="memory")
    yield app


@pytest.mark.asyncio
async def test_project(app):
    pid = await app.config_database.create_project()
    project = Project(app, pid)
    assert project is not None

    await project.load()
    assert "Project 1" == project.name
    assert pid == project.pid
