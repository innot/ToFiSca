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
from asyncio import Event

import pytest

from pathlib import Path

from camera_manager import CameraManager
from configuration.database import ConfigDatabase
from hardware_manager import HardwareManager
from main import MainApp
from project_manager import ProjectManager

@pytest.fixture
def app(tmp_path):
    app = MainApp(data_storage_path=tmp_path, database_file="memory")
    yield app
    MainApp._delete_instance()

def test_app_init(tmp_path: Path, app):
    assert isinstance(app.config_database, ConfigDatabase)
    assert isinstance(app.storage_path, Path)
    assert app.storage_path == tmp_path

    assert isinstance(app.project_manager, ProjectManager)
    assert isinstance(app.hardware_manager, HardwareManager)
    assert isinstance(app.camera_manager, CameraManager)
    assert isinstance(app.shutdown_event, Event)

@pytest.mark.asyncio
async def test_shutdown(tmp_path: Path, app):
    main_task = asyncio.create_task(app.main())
    await asyncio.sleep(0.1)
    app.shutdown_event.set()
    result = await asyncio.wait_for(main_task, timeout=1)
    assert result == 0
