from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, Optional

from sync_tool.core.sync.sync_rule import SyncRuleDestination, SyncRuleQuery, SyncRuleSource


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
    def validate_sync_rule_source(self, source: SyncRuleSource) -> None:
        """Validate the source of a sync rule.

        Will be called when a sync rule is loaded to validate the source.

        Args:
            source: The source to validate.

        Raises:
            ValueError: If the source is invalid.
        """
        raise NotImplementedError()

    @abstractmethod
    def validate_sync_rule_destination(self, destination: SyncRuleDestination) -> None:
        """Validate the destination of a sync rule.

        Will be called when a sync rule is loaded to validate the destination.

        Args:
            destination: The destination to validate.

        Raises:
            ValueError: If the destination is invalid.
        """
        raise NotImplementedError()

    @abstractmethod
    async def get_data(self, item_type: str, query: SyncRuleQuery) -> List[Dict[str, Any]]:
        """Get data from the provider.

        Will be called to get data from the provider.

        Args:
            item_type: The source to get the data from.
            query: The query to filter the data based on.

        Returns:
            List[Dict[str, Any]]: The data as list.

        Raises:
            ValueError: If the item_type is invalid or not supported by this provider.
            ProviderGetDataError: If the data could not be retrieved.
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
