from typing import Any, Dict, List

from pydantic import BaseModel, Field

from sync_tool.core.types.field_type import FieldTypeReference, FieldTypes, create_field_type


class InternalType(BaseModel):
    """Configurable internal type to work as an connection point between all of the provider data sources.
    Providing validation through fields. Stores data as simple dictionary. Is able to
    store the same data in different providers. Should be later able to determine differences in the data."""

    name: str
    fields: List[FieldTypes] = Field(..., discriminator="type")

    def validate_value(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates and then returns coerced data.

        Args:
            data (Dict[str, Any]): Data to validate against this internal type.

        Returns:
            Dict[str, Any]: Coerced data.
        """

        coerced_data = {}

        # Validate data
        validation_exceptions: List[Exception] = []
        for field in self.fields:
            if field.name not in data:
                validation_exceptions.append(ValueError(f"Field {field.name} is missing in data"))
                continue

            try:
                coerced_data[field.name] = field.validate_value(data[field.name])
            except ValueError as e:
                validation_exceptions.append(e)

        if validation_exceptions:
            raise ExceptionGroup(f"Validation with data {data} failed", validation_exceptions)

        return coerced_data


def create_internal_type(name: str, fields: Dict[str, Any], possible_other_types: List[str]) -> InternalType:
    """Create a new internal type object with the given name and fields.

    Args:
        name (str): Name of the internal type.
        fields (Dict[str, Any]): Fields of the internal type.
        possible_other_types (List[str]): List of possible other internal types to validate reference fields.

    Returns:
        InternalType: Created internal type object.
    """

    # Convert fields to FieldTypes
    prepared_fields = [create_field_type(name=field_name, **field_data) for field_name, field_data in fields.items()]

    # Validate reference fields
    for field in prepared_fields:
        if isinstance(field, FieldTypeReference):
            if field.reference_type not in possible_other_types:
                raise ValueError(
                    f"Reference type {field.reference_type} is not available. Others: {possible_other_types}"
                )

    # Create and return the internal type
    return InternalType(name=name, fields=prepared_fields)
