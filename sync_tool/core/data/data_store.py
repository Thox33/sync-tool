from enum import Enum
from typing import Any, Dict, List, Optional, cast

from sync_tool.core.data.internal_type_storage import InternalTypeStorage


class DataStore:
    """Internal structure to store data from all providers. Provides helper methods to access, store, compare
    and transform data.
    """

    class StorageType(Enum):
        SOURCE = "source"
        DESTINATION = "destination"

    _source: Optional[InternalTypeStorage]  # Should contain data from source provider
    _destination: Optional[
        InternalTypeStorage
    ]  # Should be empty but with assigned provider to fetch data needed for syncing

    def __init__(self) -> None:
        self._source = None
        self._destination = None

    def is_ready(self) -> bool:
        """Check if the data store is ready to be used.

        Returns:
            bool: True if the data store is ready, False otherwise.
        """
        return self._source is not None and self._destination is not None

    def add_storage(self, storage: InternalTypeStorage, storage_type: StorageType = StorageType.SOURCE) -> None:
        """Add an internal type storage to the data store.

        Args:
            storage (InternalTypeStorage): Internal type storage to add.
            storage_type (StorageType, optional): Type of storage. Defaults to StorageType.SOURCE.
        """
        if storage_type == self.StorageType.SOURCE:
            self._source = storage
        elif storage_type == self.StorageType.DESTINATION:
            self._destination = storage

    def get_items_to_be_created(self) -> List[Dict[str, Any]]:
        """Get items that should be created in the destination provider.
        The check will be performed based on the sync status field. If it's not present or empty, the item should be
        created.
        """

        # Check if the data store is ready
        if not self.is_ready():
            raise ValueError("Data store is not ready to be used.")

        source_storage = cast(InternalTypeStorage, self._source)

        # Get items to be created
        items_to_be_created = []
        for item in source_storage.get():
            if "syncStatus" not in item or item["syncStatus"].value == "":
                items_to_be_created.append(item)

        return items_to_be_created
