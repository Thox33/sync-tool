from typing import Any, Dict

from pydantic import BaseModel, model_validator

from sync_tool.core.data.mapping.mapping_provider import MappingProvider, create_mapping_provider
from sync_tool.core.data.type.internal_type import InternalType, create_internal_type


class DataConfiguration(BaseModel):
    types: Dict[str, InternalType]  # dict[internal_type_name, InternalType]
    mappings: Dict[str, MappingProvider]  # dict[provider_name, MappingProvider]

    @model_validator(mode="before")
    @classmethod
    def validate_and_convert(cls, data: Any) -> Any:
        """Validates and converts the data to the correct format.

        Types are converted to InternalType objects.
        """

        # Handle types configuration
        if "types" not in data:
            raise ValueError("Missing 'types' in data configuration")

        possible_internal_types = list(data["types"].keys())
        types = {}
        for type_name, type_data in data["types"].items():
            if "fields" not in type_data:
                raise ValueError(f"Missing 'fields' in type {type_name}")

            types[type_name] = create_internal_type(
                name=type_name, fields=type_data["fields"], possible_other_types=possible_internal_types
            )

        data["types"] = types

        # Handle mappings configuration
        if "mappings" not in data:
            raise ValueError("Missing 'mappings' in data configuration")

        mappings = {}
        for provider_name, mapping_data in data["mappings"].items():
            mappings[provider_name] = create_mapping_provider(
                provider_name=provider_name, mappings=mapping_data, possible_internal_types=possible_internal_types
            )

        data["mappings"] = mappings

        return data

    def get_internal_type(self, name: str) -> InternalType | None:
        """Get internal type by name.

        Args:
            name (str): Name of the internal type.

        Returns:
            InternalType: Internal type object.
        """
        return self.types.get(name)
