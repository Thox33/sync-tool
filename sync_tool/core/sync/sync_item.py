from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel

from sync_tool.core.types import SyncStatusValue


class SyncItem(BaseModel):
    """Internal representation of an entry in the data store. Contains the data from source,
    optional the destination data and the sync status."""

    class SyncStatus(Enum):
        PREPARE = "prepare"  # Prepare data for syncing; this includes checking how to handle this data
        NEW = "new"  # Destination data (sync status field empty) is missing and should be created
        SHOULD_FETCH = "should_fetch"  # Destination data (sync status field contains destination id) should be fetched
        FETCHED = "fetched"  # Destination data has been fetched
        NEEDS_UPDATE = "needs_update"  # Source and destination data are different
        SYNCED = "synced"  # Source and destination in sync

    source_data: Dict[str, Any]
    destination_data: Optional[Dict[str, Any]] = None
    sync_status: SyncStatus = SyncStatus.PREPARE

    def update_state(self) -> None:
        """This method will update the sync status based on the source, destination data and internal state machine."""
        if self.sync_status == SyncItem.SyncStatus.PREPARE and self.destination_data is None:
            if self._destination_should_be_fetched():
                self.sync_status = SyncItem.SyncStatus.SHOULD_FETCH
            else:
                self.sync_status = SyncItem.SyncStatus.NEW
        if self.sync_status == SyncItem.SyncStatus.SHOULD_FETCH and self.destination_data is not None:
            self.sync_status = SyncItem.SyncStatus.FETCHED

        # Next compare source and destination data based on provided rules
        # if self.sync_status == SyncItem.SyncStatus.FETCHED:
        #     if self.source_data != self.destination_data:
        #         self.sync_status = SyncItem.SyncStatus.NEEDS_UPDATE
        #     else:
        #         self.sync_status = SyncItem.SyncStatus.SYNCED

    def add_destination_data(self, destination_data: Dict[str, Any]) -> None:
        """Add destination data to the sync item."""
        self.destination_data = destination_data
        self.update_state()

    def _destination_should_be_fetched(self) -> bool:
        """Checks if this item should be fetched from the destination provider.
        If the sync status field is present and it's not empty, we extract the destination item IDs from it
        and add them to the to fetch list."""
        if "syncStatus" in self.source_data:
            sync_status_entry: SyncStatusValue = self.source_data["syncStatus"]
            if sync_status_entry.value != "" and len(sync_status_entry.entries) > 0:
                return True

        return False
