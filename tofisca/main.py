import asyncio
import logging
from pathlib import Path

import platformdirs
from pydantic import Field

from configuration import ConfigItem, ConfigDatabase
from hardware_manager import HardwareManager
from web_ui import run_webui_server

default_data_path = platformdirs.user_data_path("tofisca")


class DataPaths(ConfigItem):
    """
    The file system paths to store the images after
    """
    reference_data_path: Path = Field(default=default_data_path / "{project_name}")
    raw_image_storage_path: Path = Field(default=default_data_path / "{project_name}" / "scanned")
    processed_image_storage_path: Path = Field(default=default_data_path / "{project_name}" / "processed")


application_datapaths: DataPaths | None = None



async def main(database_file: Path | str = None):
    logging.basicConfig(level=logging.DEBUG)
    logging.info("Starting ToFiSca")

    # if not provided by the caller use the default location for the database
    if not database_file:
        database_file: Path = platformdirs.user_config_path(appauthor="tofisca") / "config_database.sqlite"

    #
    # Initialize the global objects
    #
    global application_datapaths


    # start the configuration database. This is a Singleton, so every future call will get this database
    ConfigDatabase(databasefile=database_file)

    # noinspection PyArgumentList
    application_datapaths = DataPaths(load_from_database=True)

    # start the camera manager to allow acces to the camera
    # CameraManager()

    # start the hardware manager to set up the gpios
    HardwareManager()

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

    logging.info("ToFiSca ended")


if __name__ == "__main__":
    asyncio.run(main("memory"))
