from typing import Any, Dict

from pydantic import BaseModel

from sync_tool.core.data.mapping.mapping_helper import add_field_data_by_path, get_field_data_by_path


class MappingInternalType(BaseModel):
    """Representation of a mapping between raw data (format dict[str, Any]) to a specific
    InternalType and its fields."""

    internal_type_name: str
    fields: Dict[str, str]  # dict[field_name, raw_data_path] (Example: {"name": "path.to.field"})

    def map_from_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map the raw data to the internal type fields."""
        mapped_data = {}

        for field_name, raw_data_path in self.fields.items():
            mapped_data[field_name] = get_field_data_by_path(raw_data, raw_data_path)

        return mapped_data

    def map_to_raw_data(self, internal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map the internal data to the raw data fields."""
        mapped_data: Dict[str, Any] = {}

        for field_name, raw_data_path in self.fields.items():
            value = internal_data.get(field_name)
            if value is None:
                continue

            mapped_data = add_field_data_by_path(mapped_data, raw_data_path, value)

        return mapped_data


def create_mapping_internal_type(internal_type_name: str, fields: Dict[str, str]) -> MappingInternalType:
    """Create a MappingInternalType object."""
    return MappingInternalType(internal_type_name=internal_type_name, fields=fields)
