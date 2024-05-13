from copy import deepcopy
from typing import Any, Dict, List

from pydantic import Field

from sync_tool.core.data.type.internal_type import InternalType


class InternalTypeStorage:
    _key: str  # provider_name + "_" + internal_type_name
    _internal_type: InternalType
    _data: List[Dict[str, Any]]

    def __init__(self, provider_name: str, internal_type: InternalType):
        self._key = f"{provider_name}_{internal_type.name}"
        self._internal_type = internal_type
        self._data = []

    def get_key(self) -> str:
        """Get the key of the internal type storage.

        Returns:
            str: Key of the internal type storage.
        """
        return self._key

    def store_data(self, data: Dict[str, Any]) -> None:
        """Validates and then stores data.

        Args:
            data (Dict[str, Any]): Data to store in the internal type.
        """

        # Validate data
        validation_exceptions: List[Exception] = []
        for field in self._internal_type.fields:
            if field.name not in data:
                validation_exceptions.append(ValueError(f"Field {field.name} is missing in data"))
                continue

            try:
                field.validate_value(data[field.name])
            except ValueError as e:
                validation_exceptions.append(e)

        if validation_exceptions:
            raise ExceptionGroup(f"Validation for {self._key} with data {data} failed", validation_exceptions)

        # Store data
        self._data.append(data)

    def get(self) -> List[Dict[str, Any]]:
        """Get all data stored in the internal type.

        Returns:
            List[Dict[str, Any]]: List of data.
        """
        return deepcopy(self._data)


class DataStore:
    """Internal structure to store data from all providers. Provides helper methods to access, store, compare
    and merge data.
    """

    data: Dict[str, InternalTypeStorage] = Field(
        default_factory=dict
    )  # Dict[internal_type_storage_key, InternalTypeStorage]

    def add_internal_storage(self, storage: InternalTypeStorage) -> None:
        """Add an internal type storage to the data store.

        Args:
            storage (InternalTypeStorage): Internal type storage to add.
        """
        self.data[storage.get_key()] = storage
