from enum import Enum

from sync_tool.core.data import InternalTypeStorage


class DataStore:
    """Internal structure to store data from all providers. Provides helper methods to access, store, compare
    and transform data.
    """

    class StorageType(Enum):
        SOURCE = "source"
        DESTINATION = "destination"

    _source: InternalTypeStorage
    _destination: InternalTypeStorage

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
