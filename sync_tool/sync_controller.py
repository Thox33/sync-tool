from collections import deque
from copy import deepcopy
from typing import Any, Deque, Dict, List, Tuple

import structlog

from sync_tool.configuration import Configuration
from sync_tool.core.provider import ProviderBase, ProviderConfiguration
from sync_tool.core.sync import SyncRule
from sync_tool.core.sync.sync_item import SyncItem
from sync_tool.core.types import InternalType, SyncStatusValue, SyncStatusValueEntry

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
        work_queue: Deque[SyncItem] = deque()
        for item in sync_items:
            work_queue.append(item)

        # Sync items
        logger.debug("Syncing data...")
        sync_iteration = 0
        max_sync_iterations = (
            len(sync_items) * 5
        )  # 5 is the number of maximal hops an sync item can do (NEW, SHOULD_FETCH, FETCHED, NEEDS_UPDATE, SYNCED)
        while len(work_queue) > 0:
            sync_iteration += 1
            if sync_iteration > max_sync_iterations:
                logger.error("Maximal sync iterations reached!")
                break
            logger.debug(f"Sync iteration {sync_iteration}...")

            # Get the next sync item from the work queue and perform sync operation
            sync_item = work_queue.popleft()
            sync_item = await self._sync_item(sync_item, dry_run=dry_run)

            # Check if we have to add the work item back into the work queue
            if (
                sync_item.sync_status != SyncItem.SyncStatus.SYNCED
                and sync_item.sync_status != SyncItem.SyncStatus.FAILED
            ):
                work_queue.append(sync_item)

            # Log analytics
            self._log_analytics(sync_items)

        logger.debug("Sync completed.")

    async def _sync_item(self, item: SyncItem, dry_run: bool = False) -> SyncItem:
        """Perform the work for a single sync item. This will only perform one step in the sync workflow. Next time
        callings this method will continue the sync operation.

        Args:
            item (SyncItem): The sync item to be processed
            dry_run (bool): If True, the sync operation will not create or update any items

        Returns:
            SyncItem: The updated sync item
        """

        try:
            # Check if the destination item should be created
            if item.sync_status == SyncItem.SyncStatus.NEW:
                item = await self._sync_item_create(item, dry_run=dry_run)
            # Check if the destination item should be fetched
            elif item.sync_status == SyncItem.SyncStatus.SHOULD_FETCH:
                item = await self._sync_item_fetch(item)

            item.update_state()
        except Exception as e:
            logger.exception(f"Could not sync item: {e}", item=item.model_dump_json())
            item.sync_status = SyncItem.SyncStatus.FAILED

        return item

    async def _sync_item_create(self, item: SyncItem, dry_run: bool = False) -> SyncItem:
        """Create the destination item for the sync item.

        Args:
            item (SyncItem): The sync item to be processed
            dry_run (bool): If True, the sync operation will not create or update any items

        Returns:
            SyncItem: The updated sync item
        """
        logger.debug("Creating data...", item=item.model_dump_json())

        source_data = item.get_source_data()
        new_destination_data = deepcopy(source_data)

        # Add sync id from source data to destination data
        logger.debug("Adding sync ID to destination data...", item=item.model_dump_json())
        try:
            work_item_id_source = new_destination_data["id"]
            work_item_url_source = await self._provider_source_instance.get_item_url_for_id(work_item_id_source)
            sync_status_value_entry_source = SyncStatusValueEntry(id=work_item_id_source, url=work_item_url_source)
            sync_status_value_source = SyncStatusValue(value="", entries=[sync_status_value_entry_source])
            new_destination_data["syncStatus"] = sync_status_value_source
            logger.debug(
                "Sync ID added to destination data", item=item.model_dump_json(), sync_status=sync_status_value_source
            )
        except Exception as e:
            logger.error(f"Could not add sync ID to destination data: {e}", item=item.model_dump_json())
            raise RuntimeError(f"Could not add sync ID to destination data: {e}")

        # Transform data from source to destination
        logger.debug("Transform fields from source to destination...", item=item.model_dump_json())

        # Convert from internal source data to destination data
        logger.debug("Mapping data from source to destination format...", item=item.model_dump_json())
        mapped_items = self._map_internal_type_to_items([new_destination_data], is_source=False)

        # Create using the destination provider
        logger.debug("Creating data...", item=item.model_dump_json())
        creating_destination_exceptions = []
        created_item_id = None
        for mapped_item in mapped_items:
            try:
                created_item_id = await self._provider_destination_instance.create_data(
                    item_type=self._rule.destination.mapping,
                    query=self._rule.destination.query,
                    data=mapped_item,
                    dry_run=dry_run,
                )
            except Exception as e:
                creating_destination_exceptions.append((item, e))
        if len(creating_destination_exceptions) > 0:
            for item, creating_exception in creating_destination_exceptions:
                logger.error(f"Creating failed for item: {creating_exception}", item=item.model_dump_json())

            logger.error(
                f"Creating failed for some items {len(creating_destination_exceptions)}!", item=item.model_dump_json()
            )
            raise RuntimeError(f"Creating failed for some items {len(creating_destination_exceptions)}!")
        if created_item_id is None:
            raise RuntimeError("Could not create item in destination provider!")
        logger.debug("Data created!", item=item.model_dump_json(), created_item_id=created_item_id)

        # Add sync id from destination data to source date
        logger.debug("Adding sync ID to source data...", item=item.model_dump_json())
        work_item_id_destination = created_item_id
        work_item_url_destination = await self._provider_destination_instance.get_item_url_for_id(
            work_item_id_destination
        )
        sync_status_value_entry_destination = SyncStatusValueEntry(
            id=work_item_id_destination, url=work_item_url_destination
        )
        sync_status_value_destination = SyncStatusValue(value="", entries=[sync_status_value_entry_destination])
        source_data["syncStatus"] = sync_status_value_destination
        logger.debug(
            "Sync ID added to source data", item=item.model_dump_json(), sync_status=sync_status_value_destination
        )

        # Update sync item status
        item.sync_status = SyncItem.SyncStatus.SHOULD_FETCH

        return item

    async def _sync_item_fetch(self, item: SyncItem) -> SyncItem:
        """Fetch the destination item for the sync item.

        Args:
            item (SyncItem): The sync item to be processed

        Returns:
            SyncItem: The updated sync item
        """
        destination_sync_status_id = item.get_source_sync_id()
        if destination_sync_status_id is None:
            raise RuntimeError("Destination sync ID is missing in source data!")

        # Fetch destination item
        try:
            destination_item = await self._provider_destination_instance.get_data_by_id(
                item_type=self._internal_type.name, unique_id=destination_sync_status_id
            )
            if destination_item is None:
                raise RuntimeError(f"Destination item '{destination_sync_status_id}' not found!")
        except Exception as e:
            raise RuntimeError(f"Could not fetch destination item '{destination_sync_status_id}': {e}")

        # Add destination data to sync item
        item.add_destination_data(destination_item)

        return item

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
        mapped_source_items = self._map_items_to_internal_type(source_data, is_source=True)

        # Validate and coerce data
        coerced_source_items = self._validate_and_coerce_items(mapped_source_items)

        logger.debug(f"Data retrieved for rule: {len(source_data)} items")
        return coerced_source_items

    def _map_items_to_internal_type(self, items: List[Dict[str, Any]], is_source: bool = True) -> List[Dict[str, Any]]:
        """Map items to the internal type using the source or destination provider mapping.

        Args:
            items (List[Dict[str, Any]]): The items to be mapped to the internal type.
            is_source (bool): If True, the source provider mapping will be used, otherwise
                the destination provider mapping.

        Returns:
            List[Dict[str, Any]]: The mapped items in the internal type format
        """
        logger.debug(f"Mapping data from {'source' if is_source else 'destination'} to internal type format...")

        provider_config = self._provider_source_config if is_source else self._provider_destination_config
        mapping = self._rule.source.mapping if is_source else self._rule.destination.mapping

        mapped_items = []
        mapping_exceptions = []
        for item in items:
            try:
                item = provider_config.map_raw_data_to_internal_format(mapping, item)
                mapped_items.append(item)
            except Exception as e:
                mapping_exceptions.append((item, e))
        if len(mapping_exceptions) > 0:
            for item, mapping_exception in mapping_exceptions:
                logger.error(f"Mapping failed for item '{item}': {mapping_exception}")
            raise RuntimeError(f"Mapping failed for some items {len(mapping_exceptions)}!")

        return mapped_items

    def _map_internal_type_to_items(self, items: List[Dict[str, Any]], is_source: bool = True) -> List[Dict[str, Any]]:
        """Map items to the internal type using the source or destination provider mapping.

        Args:
            items (List[Dict[str, Any]]): The items to be mapped to the internal type.
            is_source (bool): If True, the source provider mapping will be used,
                otherwise the destination provider mapping.

        Returns:
            List[Dict[str, Any]]: The mapped items in the internal type format
        """
        logger.debug(f"Mapping data from internal type to {'source' if is_source else 'destination'} format...")

        provider_config = self._provider_source_config if is_source else self._provider_destination_config
        mapping = self._rule.source.mapping if is_source else self._rule.destination.mapping

        mapped_items = []
        mapping_exceptions = []
        for item in items:
            try:
                item = provider_config.map_internal_data_to_raw_format(mapping, item)
                mapped_items.append(item)
            except Exception as e:
                mapping_exceptions.append((item, e))
        if len(mapping_exceptions) > 0:
            for item, mapping_exception in mapping_exceptions:
                logger.error(f"Mapping failed for item '{item}': {mapping_exception}")
            raise RuntimeError(f"Mapping failed for some items {len(mapping_exceptions)}!")

        return mapped_items

    def _validate_and_coerce_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and coerce items based on the internal type.

        Args:
            items (List[Dict[str, Any]]): The items to be validated and coerced.
                Has to be already mapped to the internal type.

        Returns:
            List[Dict[str, Any]]: The validated and coerced items
        """
        logger.debug("Validating and coercing data...")
        coerced_items = []
        validation_exceptions = []
        for item in items:
            try:
                coerced_items.append(self._internal_type.validate_value(data=item))
            except Exception as e:
                validation_exceptions.append(e)
        if len(validation_exceptions) > 0:
            for validation_exception in validation_exceptions:
                logger.exception(validation_exception)
                if isinstance(validation_exception, ExceptionGroup):
                    for exception in validation_exception.exceptions:
                        logger.error(exception)
            raise RuntimeError(f"Validation with {len(validation_exceptions)} items failed!")

        return coerced_items

    async def _prepare_sync_items(self, source_data: List[Dict[str, Any]]) -> List[SyncItem]:
        """Prepare sync items based on the source data."""
        logger.debug("Preparing sync items...")
        sync_items = [SyncItem(source_data=item) for item in source_data]
        # Run first sync item state update
        for item in sync_items:
            item.update_state()
        # Log analytics
        self._log_analytics(sync_items)

        return sync_items

    def _log_analytics(self, sync_items: List[SyncItem]) -> None:
        """Log analytics based on the sync items."""
        logger.debug(f"Number of items to be created: {self._count_sync_items_to_be_created(sync_items)}")
        logger.debug(
            f"Number of items to be fetched from destination: {self._count_sync_items_to_be_fetched(sync_items)}"
        )
        logger.debug(f"Number of items fetched from destination: {self._count_sync_items_fetched(sync_items)}")
        logger.debug(f"Number of items to be updated: {self._count_sync_items_needs_update(sync_items)}")
        logger.debug(f"Number of items in synced: {self._count_sync_items_synced(sync_items)}")
        logger.debug(f"Number of items failed: {self._count_sync_items_failed(sync_items)}")

    def _count_sync_items_to_be_created(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items to be created."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.NEW])

    def _count_sync_items_to_be_fetched(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items to be fetched from destination provider."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.SHOULD_FETCH])

    def _count_sync_items_fetched(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items fetched from destination provider."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.FETCHED])

    def _count_sync_items_needs_update(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items needs updates from destination provider."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.NEEDS_UPDATE])

    def _count_sync_items_synced(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items synced from destination provider."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.SYNCED])

    def _count_sync_items_failed(self, sync_items: List[SyncItem]) -> int:
        """Count the number of items failed to sync."""
        return len([item for item in sync_items if item.sync_status == SyncItem.SyncStatus.FAILED])
