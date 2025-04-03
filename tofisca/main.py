from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import platformdirs

from .configuration import ConfigDatabase
from .hardware_manager import HardwareManager
from .project_manager import ProjectManager
from .utils import Event_ts
from .web_ui.server import run_webui_server

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class ToFiSca:
    """
    The main application.

    Besides the :meth:`main` method to start the application this methods allows access to the
    various managers.

    This class should be instatiated only once.

    Use :meth:`app` to access the instance of the application.
    """

    _instance: ToFiSca | None = None

    @classmethod
    def app(cls) -> ToFiSca:
        return cls._instance

    @classmethod
    def _delete_singleton(cls):
        """
        Reset the singleton instance so that tofisca can be instantiatied again with new arguments.
        Only used for unit testing
        """
        cls._instance = None

    def __new__(cls, *args, **kwargs):
        """
        Ensure that the class is only instantiated once.
        """
        if cls._instance:
            raise RuntimeError("ToFiSca can be instantiated only once. Use ToFiSca.app() instead.")

        cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, data_path: Path = None, database_file: Path | str = None):

        # if not provided by the caller, use the default platform-specific location for configuration data
        if not database_file:
            database_file: Path = platformdirs.user_config_path(appauthor="tofisca") / "config_database.sqlite"

        # Start the configuration database. This is a Singleton, so every future call will get this database
        self.config_db = ConfigDatabase(databasefile=database_file)

        # if not provided by the caller, use the default platform-specific location for application data
        if not data_path:
            data_path = platformdirs.user_data_path(appauthor="tofisca")

        self._data_path = data_path

        # Start the projectmanager. This must be done after the config database has been started
        self.project_manager = ProjectManager()

        # start the camera manager to allow acces to the camera
        # CameraManager()

        # start the hardware manager to set up the gpios
        self.hardware_manager = HardwareManager()

        self.shutdown_event: Event_ts | None = None
        """
        When set causes all parts of the application to shut down, saving their state as required.
        The application exits after that.
        """

    @property
    def data_path(self) -> Path:
        return self._data_path

    async def main(self):

        logger.info("Starting ToFiSca")

        #
        # run the different tasks
        #

        # noinspection PyListCreation
        tasks: list[asyncio.Task] = []

        # If scanning is started, the sequencer takes the images and handles post processing
        # todo: run scheduler

        # Start WebUI to control the Application from the web
        tasks.append(asyncio.create_task(run_webui_server()))

        # Start SshUI to control the Application via ssh
        #    ssh_task = asyncio.create_task(SSHServer().run())

        # wait for any task to finish (this will close the application)
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # stop all other tasks gracefully, allowing them to save state if required
        for task in tasks:
            task.cancel()
            await task

        logger.info("ToFiSca ended")


if __name__ == "__main__":
    _instance = ToFiSca()
    asyncio.run(_instance.main())
