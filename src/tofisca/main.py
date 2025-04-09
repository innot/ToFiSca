from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import platformdirs

from app import App
from configuration.database import ConfigDatabase
from hardware_manager import HardwareManager
from project_manager import ProjectManager
from camera_manager import CameraManager
from utils import Event_ts
from web_ui.server import run_webui_server

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MainApp(App):

    def __init__(self, *, data_storage_path: Path = None, database_file: Path | str = None):

        super().__init__()  # initialize the App attributes

        # if not provided by the caller, use the default platform-specific location for configuration data
        if not database_file:
            database_file: Path = platformdirs.user_config_path(appauthor="tofisca") / "config_database.sqlite"

        # Start the configuration database. This is a Singleton, so every future call will get this database
        self._config_database = ConfigDatabase(databasefile=database_file)

        # if not provided by the caller, use the default platform-specific location for application data
        if not data_storage_path:
            data_storage_path = platformdirs.user_data_path(appauthor="tofisca", ensure_exists=True)

        if not data_storage_path.exists() and not data_storage_path.is_dir():
            raise FileNotFoundError(f"The data storage path {data_storage_path} does not exist.")

        self._storage_path = data_storage_path

        # Start the projectmanager. This must be done after the config database has been started
        self._project_manager = ProjectManager(self)

        # start the camera manager to allow acces to the camera
        self._camera_manager = CameraManager(self)

        # start the hardware manager to set up the gpios
        self._hardware_manager = HardwareManager()

        self._shutdown_event = Event_ts()

        App._instance = self

        logger.info("ToFiSca App successfully initialized")

    async def main(self) -> int:
        logger.info("Starting ToFiSca")

        #
        # run the different tasks
        #

        # noinspection PyListCreation
        tasks: list[asyncio.Task] = []

        # If scanning is started, the sequencer takes the images and handles post processing
        # todo: run scheduler

        # Start WebUI to control the Application from the web
        tasks.append(asyncio.create_task(run_webui_server(self)))

        # Start SshUI to control the Application via ssh
        #    ssh_task = asyncio.create_task(SSHServer().run())

        # wait for any task to finish (this will close the application)
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # stop all other tasks gracefully, allowing them to save state if required
        for task in tasks:
            task.cancel()
            await task

        logger.info("ToFiSca ended")

        return 0


if __name__ == "__main__":
    # todo: read the storage path and the database file from the command line arguments
    app = MainApp()
    exitcode = asyncio.run(app.main())
    sys.exit(exitcode)
