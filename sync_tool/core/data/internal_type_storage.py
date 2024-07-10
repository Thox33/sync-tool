from copy import deepcopy
from typing import Any, Dict, List

from sync_tool.core.provider import ProviderBase
from sync_tool.core.types import InternalType


class InternalTypeStorage:
    _provider: ProviderBase
    _internal_type: InternalType
    _data: List[Dict[str, Any]]

    def __init__(self, provider: ProviderBase, internal_type: InternalType):
        self._provider = provider
        self._internal_type = internal_type
        self._data = []

    def get_provider(self) -> ProviderBase:
        """Get the provider of the internal type storage.

        Returns:
            ProviderBase: Initialized provider of the internal type storage.
        """
        return self._provider

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
                data[field.name] = field.validate_value(data[field.name])
            except ValueError as e:
                validation_exceptions.append(e)

        if validation_exceptions:
            raise ExceptionGroup(f"Validation with data {data} failed", validation_exceptions)

        # Store data
        self._data.append(data)

    def get(self) -> List[Dict[str, Any]]:
        """Get all data stored in the internal type.

        Returns:
            List[Dict[str, Any]]: List of data.
        """
        return deepcopy(self._data)
