from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional


class AdapterBase(metaclass=ABCMeta):
    """Base class for dynamic, lazy loaded adapter.

    .. hint:: The constructor will receive the options as parameters.
    """

    @staticmethod
    @abstractmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        """Check if the adapter configuration is valid.

        Will be called while smoke importing configured adapter classes.

        Args:
            options: Optional dictionary of configured adapter options

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
