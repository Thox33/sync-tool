from typing import Any, Dict, List

from pydantic import BaseModel, model_validator

from sync_tool.core.data.mapping.mapping_internal_type import MappingInternalType, create_mapping_internal_type


class MappingProvider(BaseModel):
    """Representation of a mapping between a provider and its mapping definitions."""

    provider_name: str
    mappings: Dict[str, MappingInternalType]  # dict[internal_type_name, MappingInternalType]

    @model_validator(mode="before")
    @classmethod
    def validate_and_Convert_mappings(cls, data: Any) -> Any:
        """Validates and converts the mappings to the correct format."""

        if "mappings" not in data:
            raise ValueError("Missing 'mappings' in data configuration")

        mappings = {}
        for internal_type_name, mapping_data in data["mappings"].items():
            if "fields" not in mapping_data:
                raise ValueError(f"Missing 'fields' in mapping for internal type '{internal_type_name}'")

            mappings[internal_type_name] = create_mapping_internal_type(
                internal_type_name=internal_type_name, fields=mapping_data["fields"]
            )

        data["mappings"] = mappings

        return data

    def map_raw_data(self, internal_type_name: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw data to internal type data."""
        mapping = self.mappings.get(internal_type_name)
        if not mapping:
            raise ValueError(f"Mapping for internal type '{internal_type_name}' not found.")

        return mapping.map_raw_data(raw_data)


def create_mapping_provider(
    provider_name: str, mappings: Dict[str, MappingInternalType], possible_internal_types: List[str]
) -> MappingProvider:
    """Create a mapping provider. Checks if the mapping internal types are valid."""

    for internal_type_name in mappings.keys():
        if internal_type_name not in possible_internal_types:
            raise ValueError(f"Internal type '{internal_type_name}' not found in possible internal types.")

    return MappingProvider(provider_name=provider_name, mappings=mappings)
