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
from asyncio import Event

import pytest

from app import App
from hardware_manager import HardwareManager
from project_manager import ProjectManager
from configuration.database import ConfigDatabase


class FoobarApp(App):   # cannot name it TestApp as then pytest thinks it is a class containing tests

    def __init__(self):
        super().__init__()


@pytest.fixture
def test_app():
    return FoobarApp()


def test_instance():

    with pytest.raises(RuntimeError):
        FoobarApp.instance()

    app = FoobarApp()
    assert app is not None
    assert FoobarApp.instance() is app

    FoobarApp._delete_instance()
    with pytest.raises(RuntimeError):
        FoobarApp.instance()




def test_config_database(test_app):
    db = ConfigDatabase("memory")
    test_app._config_database = db
    assert test_app.config_database is db


def test_storage_path(tmp_path,test_app):
    test_app._storage_path = tmp_path
    assert test_app.storage_path is tmp_path


def test_project_manager(test_app, tmp_path):
    test_app._storage_path = tmp_path  # projectmanager needs a storage path
    test_app._config_database = ConfigDatabase("memory")    # and a database
    pm = ProjectManager(test_app)
    test_app._project_manager = pm
    assert test_app.project_manager is pm


def test_hardware_manager(test_app):
    hm = HardwareManager()
    test_app._hardware_manager = hm
    assert test_app.hardware_manager is hm


def test_shutdown_event(test_app):
    ev = Event()
    test_app._shutdown_event = ev
    assert test_app.shutdown_event is ev
