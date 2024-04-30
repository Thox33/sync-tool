from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional


class ProviderBase(metaclass=ABCMeta):
    """Base class for datasource providers"""

    @staticmethod
    @abstractmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        """Check if the provider configuration is valid.

        Will be called while smoke importing configured provider classes.

        Args:
             options: Optional dictionary of configured options

        Raises:
            ValueError: If the configuration is invalid.

        .. code-block::

            {
              ...,
              "options": {             <--- This is the validated options dictionary
                "listen": "0.0.0.0",
                "port": 502
              }
            }
        """
        raise NotImplementedError()

    @abstractmethod
    async def init(self) -> None:
        """Initialize the provider.

        Will be called after creation of all providers. Use this method to e.g. establish
        a connection to a third party system.

        Raises:
            ProviderInitError: If the initialization fails.
        """
        raise NotImplementedError()

    @abstractmethod
    async def teardown(self) -> None:
        """Tear down the provider.

        Will be called if the provider is no longer needed.

        Raises:
            ProviderTeardownError: If the teardown fails.
        """
        raise NotImplementedError()
