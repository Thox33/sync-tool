from collections import deque
from copy import deepcopy
from datetime import datetime
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
                raise RuntimeError("Maximal sync iterations reached!")

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
            # Check if the destination item should be created -> then create it
            if item.sync_status == SyncItem.SyncStatus.NEW:
                item = await self._sync_item_create(item, dry_run=dry_run)
            # Check if the destination item should be fetched -> then fetch it
            elif item.sync_status == SyncItem.SyncStatus.SHOULD_FETCH:
                item = await self._sync_item_fetch(item)
            # Check if the source and destination item should be updated -> then compare it
            elif item.sync_status == SyncItem.SyncStatus.FETCHED:
                item = await self._sync_item_compare(item)
            # Check if the source and destination item are out of sync -> then update one or both sides
            elif item.sync_status == SyncItem.SyncStatus.NEEDS_UPDATE:
                item = await self._sync_item_update(item, dry_run=dry_run)

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

        # Patch source data in source provider
        data_to_patch = {
            "syncStatus": sync_status_value_destination,
        }
        mapped_to_patch_items = self._map_internal_type_to_items([data_to_patch], is_source=True)
        await self._provider_source_instance.patch_data(
            item_type=self._rule.source.mapping,
            query=self._rule.source.query,
            unique_id=work_item_id_source,
            data=mapped_to_patch_items[0],
            dry_run=dry_run,
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
        logger.debug("Fetching destination data...", item=item.model_dump_json())

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

        logger.debug("Destination data fetched!", item=item.model_dump_json(), destination_item=destination_item)

        # Map destination data to internal type
        mapped_destination_items = self._map_items_to_internal_type([destination_item], is_source=False)

        # Validate and coerce data
        coerced_destination_items = self._validate_and_coerce_items(mapped_destination_items)

        # Add destination data to sync item
        if len(coerced_destination_items) == 0:
            raise RuntimeError("No destination data found!")
        if len(coerced_destination_items) > 1:
            raise RuntimeError("More than one destination data found!")

        item.add_destination_data(coerced_destination_items[0])

        return item

    async def _sync_item_compare(self, item: SyncItem) -> SyncItem:
        """Compare the source and destination item for the sync item based on the
        comparable fields of the internal type."""
        logger.debug("Comparing source and destination data...", item=item.model_dump_json())

        source_data = item.get_source_data()
        destination_data = item.get_destination_data()
        if destination_data is None:
            raise RuntimeError("Destination data is missing!")

        # Compare source and destination data based on the comparable fields
        needs_sync = False
        comparable_fields = self._internal_type.options.comparableFields
        for field in comparable_fields:
            if source_data[field] != destination_data[field]:
                # Special case: datetime fields (we allow a small difference of 5 minutes)
                if isinstance(source_data[field], datetime) and isinstance(destination_data[field], datetime):
                    if abs(source_data[field] - destination_data[field]).seconds > (5 * 60):
                        needs_sync = True
                else:
                    needs_sync = True

                if needs_sync:
                    logger.debug(
                        f"Source and destination data are different for field '{field}': "
                        f"{source_data[field]} != {destination_data[field]}",
                        item=item.model_dump_json(),
                    )

        if needs_sync:
            item.needs_update()
            logger.debug("Source and destination data are different!", item=item.model_dump_json())
        else:
            item.synced()
            logger.debug("Source and destination data are equal!", item=item.model_dump_json())

        return item

    async def _sync_item_update(self, item: SyncItem, dry_run: bool = False) -> SyncItem:
        """Update the source and destination item for the sync item based on the
        sync-able fields of the internal type and the mode inside the sync rule."""

        # Prepare data for patching
        source_data = item.get_source_data()
        destination_data = item.get_destination_data()
        if destination_data is None:
            raise RuntimeError("Destination data is missing!")

        data_to_patch = {}

        if self._rule.mode == "single":
            # Perform an update only from source to destination
            logger.debug("Running one-way sync...", item=item.model_dump_json())
            # Extract to patch data from source data
            sync_able_fields = self._internal_type.options.syncableFields
            for field in sync_able_fields:
                if source_data.get(field) is not None:
                    data_to_patch[field] = source_data[field]
            # Transform data from source to destination
            logger.debug("Transform fields from source to destination...", item=item.model_dump_json())
            mapped_items = self._map_internal_type_to_items([data_to_patch], is_source=False)
            # Patch using the destination provider
            logger.debug("Patching data...", item=item.model_dump_json())
            await self._provider_destination_instance.patch_data(
                item_type=self._rule.source.mapping,
                query=self._rule.destination.query,
                unique_id=destination_data["id"],
                data=mapped_items[0],
                dry_run=dry_run,
            )
        elif self._rule.mode == "both":
            # Perform an update from source to destination and vice versa based on the modified date
            logger.debug("Running both-way sync based on last change date...", item=item.model_dump_json())
            # Determine which item is newer
            source_modified_date = source_data.get("modifiedDate")
            destination_modified_date = destination_data.get("modifiedDate")
            if source_modified_date is None or destination_modified_date is None:
                raise RuntimeError("Modified date is missing in source or destination data!")
            update_source_to_destination = source_modified_date > destination_modified_date
            # Extract to patch data from source or destination data
            sync_able_fields = self._internal_type.options.syncableFields
            for field in sync_able_fields:
                if (update_source_to_destination and source_data.get(field) is not None) or (
                    not update_source_to_destination and destination_data.get(field) is not None
                ):
                    data_to_patch[field] = (
                        source_data.get(field) if update_source_to_destination else destination_data[field]
                    )
            # Transform data from source or destination to internal type
            logger.debug(
                "Transform fields from source or destination to internal type...",
                item=item.model_dump_json(),
                update_source_to_destination=update_source_to_destination,
            )
            mapped_items = self._map_internal_type_to_items([data_to_patch], is_source=update_source_to_destination)
            # Patch using the corresponding provider
            logger.debug(
                "Patching data...",
                item=item.model_dump_json(),
                update_source_to_destination=update_source_to_destination,
            )
            if update_source_to_destination:
                await self._provider_destination_instance.patch_data(
                    item_type=self._rule.destination.mapping,
                    query=self._rule.destination.query,
                    unique_id=destination_data["id"],
                    data=mapped_items[0],
                    dry_run=dry_run,
                )
            else:
                await self._provider_source_instance.patch_data(
                    item_type=self._rule.source.mapping,
                    query=self._rule.source.query,
                    unique_id=source_data["id"],
                    data=mapped_items[0],
                    dry_run=dry_run,
                )

        # Update state
        item.synced()

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
