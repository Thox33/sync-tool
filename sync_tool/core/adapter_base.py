from abc import ABCMeta, abstractmethod

from ..settings import Settings


class AdapterBase(metaclass=ABCMeta):
    """Base class for synchronization adapter."""

    @staticmethod
    @abstractmethod
    def validate_settings(settings: Settings) -> None:
        """Check if the settings configuration is valid.

        Args:
            settings: The loaded settings.

        Raises:
            ValueError: If the settings configuration is invalid or something is missing.
        """
        raise NotImplementedError()

    @abstractmethod
    async def init(self) -> None:
        """Initialize the adapter.

        Will be called after creation of all adapters. Use this method to e.g. establish
        a connection to a third party system.

        Raises:
            AdapterInitError: If the initialization fails.
        """
        raise NotImplementedError()

    @abstractmethod
    async def teardown(self) -> None:
        """Tear down the adapter.

        Will be called if the adapter is no longer needed.

        Raises:
            AdapterTeardownError: If the teardown fails.
        """
        raise NotImplementedError()
