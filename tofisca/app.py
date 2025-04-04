from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import Event
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .configuration import ConfigDatabase
    from .hardware_manager import HardwareManager
    from .project_manager import ProjectManager


class App(ABC):
    """
    This class holds references to all parts of the application.
    Subparts of the application can get access to the config database and all managers.

    This class should not be instantiated directly.
    Instead the main application will
    """

    _instance: App | None = None

    @classmethod
    def instance(cls) -> App:
        if cls._instance is None:
            raise RuntimeError("App instance is not initialized")
        return cls._instance

    @classmethod
    def _delete_instance(cls) -> None:
        cls._instance = None

    @abstractmethod
    def __init__(self):
        # The app attributes
        self._config_database: ConfigDatabase | None = None
        self._storage_path: Path | None = None
        self._project_manager: ProjectManager | None = None
        self._hardware_manager: HardwareManager | None = None
        self._shutdown_event: Event | None = None

        App._instance = self

    @property
    def config_database(self) -> ConfigDatabase:
        if self._config_database is None:
            raise RuntimeError("Config database has not been initialized")
        return self._config_database

    @property
    def storage_path(self) -> Path:
        if self._storage_path is None:
            raise RuntimeError("Storage path has not been initialized")
        return self._storage_path

    @property
    def project_manager(self) -> ProjectManager:
        if self._project_manager is None:
            raise RuntimeError("Project manager has not been initialized")
        return self._project_manager

    @property
    def hardware_manager(self) -> HardwareManager:
        if self._hardware_manager is None:
            raise RuntimeError("Hardware manager has not been initialized")
        return self._hardware_manager

    @property
    def shutdown_event(self) -> Event:
        """
        When set causes all parts of the application to shut down, saving their state as required.
        The application exits after that.
        """
        if self._shutdown_event is None:
            raise RuntimeError("Shutdown event has not been initialized")
        return self._shutdown_event
