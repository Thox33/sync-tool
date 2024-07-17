from typing import Any, Dict, List, Tuple

import structlog

from sync_tool.configuration import Configuration
from sync_tool.core.provider import ProviderBase, ProviderConfiguration
from sync_tool.core.sync import SyncRule
from sync_tool.core.sync.sync_item import SyncItem
from sync_tool.core.types import InternalType

logger = structlog.getLogger(__name__)


class SyncController:
    _config: Configuration
    _rule: SyncRule

    _internal_type: InternalType
    _provider_source_config: ProviderConfiguration
    _provider_source_instance: ProviderBase
    _provider_destination_config: ProviderConfiguration
    _provider_destination_instance: ProviderBase

    def __init__(self, configuration: Configuration, sync_rule: SyncRule):
        self._config = configuration
        self._rule = sync_rule

    async def init(self) -> None:
        """Initialize the sync controller.
        Preparing internal type,source and destination providers.
        """
        # Getting internal type
        logger.debug(f"Retrieving internal type '{self._rule.type}'...")
        internal_type = self._config.get_internal_type(self._rule.type)
        if internal_type is None:
            raise LookupError(f"Internal type '{self._rule.type}' not found in configuration.")
        self._internal_type = internal_type

        # Prepare source provider
        logger.debug(f"Initializing source provider '{self._rule.source.provider}'...")
        self._provider_source_config, self._provider_source_instance = await self._make_provider(
            self._rule.source.provider
        )
        # Prepare destination provider
        logger.debug(f"Initializing destination provider '{self._rule.destination.provider}'...")
        self._provider_destination_config, self._provider_destination_instance = await self._make_provider(
            self._rule.destination.provider
        )

    async def sync(self, dry_run: bool = False) -> None:
        """Sync data based on the sync rule.
        Will get source data, convert them to sync entries and performs the sync operation
        based on an lilo queue while yielding the progress

        Args:
            dry_run (bool): If True, the sync operation will not create or update any items
        """
        # Getting and preparing source data
        coerced_source_items = await self._get_source_data()
        sync_items = await self._prepare_sync_items(coerced_source_items)

    async def teardown(self) -> None:
        """Teardown the sync controller and its providers"""
        logger.debug("Tearing down sync controller...")
        # Source
        try:
            await self._provider_source_instance.teardown()
        except Exception as e:
            logger.exception("Could not teardown source provider", e)
        # Destination
        try:
            await self._provider_destination_instance.teardown()
        except Exception as e:
            logger.exception("Could not teardown destination provider", e)

    async def _make_provider(self, provider: str) -> Tuple[ProviderConfiguration, ProviderBase]:
        """Create a provider instance based on the provider name."""
        # Getting provider configuration
        provider_config = self._config.get_provider(provider)
        if provider_config is None:
            raise LookupError(f"Provider '{provider}' not found in configuration.")
        # Prepare provider instance
        try:
            provider_instance = provider_config.make_instance()
            await provider_instance.init()
        except Exception as e:
            raise RuntimeError(f"Could not initialize provider '{provider}': {e}")

        return provider_config, provider_instance

    async def _get_source_data(self) -> List[Dict[str, Any]]:
        """Get source data for syncing."""
        logger.debug("Retrieving data for rule...")
        try:
            source_data = await self._provider_source_instance.get_data(
                item_type=self._rule.source.mapping, query=self._rule.source.query
            )
        except Exception as e:
            raise RuntimeError(f"Could not retrieve data for rule: {e}")

        # Map source data to internal type
        logger.debug("Mapping data from source to internal type format...")
        mapped_source_items = []
        mapping_source_exceptions = []
        for item in source_data:
            try:
                item = self._provider_source_config.map_raw_data_to_internal_format(self._rule.source.mapping, item)
                mapped_source_items.append(item)
            except Exception as e:
                mapping_source_exceptions.append((item, e))
        if len(mapping_source_exceptions) > 0:
            for item, mapping_exception in mapping_source_exceptions:
                logger.error(f"Mapping failed for item '{item}': {mapping_exception}")
            raise RuntimeError(f"Mapping failed for some items {len(mapping_source_exceptions)}!")

        # Validate and coerce data
        logger.debug("Validating and coercing data...")
        coerced_source_items = []
        validation_exceptions = []
        for item in mapped_source_items:
            try:
                coerced_source_items.append(self._internal_type.validate_value(data=item))
            except Exception as e:
                validation_exceptions.append(e)
        if len(validation_exceptions) > 0:
            for validation_exception in validation_exceptions:
                logger.exception(validation_exception)
                if isinstance(validation_exception, ExceptionGroup):
                    for exception in validation_exception.exceptions:
                        logger.error(exception)
            raise RuntimeError(f"Validation with {len(validation_exceptions)} items failed!")

        logger.debug(f"Data retrieved for rule: {len(source_data)} items")
        return coerced_source_items

    async def _prepare_sync_items(self, source_data: List[Dict[str, Any]]) -> List[SyncItem]:
        """Prepare sync items based on the source data."""
        logger.debug("Preparing sync items...")
        sync_items = [SyncItem(source_data=item) for item in source_data]
        # Run first sync item state update
        for item in sync_items:
            item.update_state()
        # Log analytics
        logger.debug(f"Number of items to be created: {self._count_sync_items_to_be_created(sync_items)}")
        logger.debug(
            f"Number of items to be fetched from destination: {self._count_sync_items_to_be_fetched(sync_items)}"
        )

        return sync_items

    def _count_sync_items_to_be_created(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items to be created."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.NEW])

    def _count_sync_items_to_be_fetched(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items to be fetched from destination provider."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.SHOULD_FETCH])
