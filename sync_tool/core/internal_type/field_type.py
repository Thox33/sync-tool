from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import Any, Literal, Optional

from pydantic import BaseModel


class FieldType(BaseModel, metaclass=ABCMeta):
    """Internal representation of an field of the internal type. Providing validation of field values"""

    name: str
    type: Any
    default: Optional[Any] = None

    @abstractmethod
    def validate_value(
        self, value: Any, context: Optional[Any] = None
    ) -> None:  # TODO: Add context type (including other internal types)
        """Validate the value of the field. Has to be implemented in the child classes.

        Raises:
            ValueError: If the value is invalid
        """
        pass

    def get_default(self) -> Optional[Any]:
        """Get the default value of the field. Override in the child classes if different implementation is needed"""
        return self.default


class FieldTypeNumber(FieldType):
    """Internal representation of an number field of the internal type"""

    type: Literal["number"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> None:
        """Validate the value of the number field"""
        if not isinstance(value, (int, float)):
            raise ValueError(f"Field {self.name} value {value} is not a number")


class FieldTypeString(FieldType):
    """Internal representation of an string field of the internal type"""

    type: Literal["string"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> None:
        """Validate the value of the string field"""
        if not isinstance(value, str):
            raise ValueError(f"Field {self.name} value {value} is not a string")


class FieldTypeDatetime(FieldType):
    """Internal representation of an datetime field of the internal type"""

    type: Literal["datetime"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> None:
        """Validate the value of the datetime field"""
        from datetime import datetime

        if not isinstance(value, datetime):
            raise ValueError(f"Field {self.name} value {value} is not a datetime")

    def get_default(self) -> Optional[Any]:
        """Get the default value of the datetime field. If the user provided the string "now" as default,
        return the current datetime. Otherwise return the default value"""
        from datetime import datetime

        return datetime.now() if self.default == "now" else self.default


class FieldTypeReference(FieldType):
    """Internal representation of an reference field of the internal type. This"""

    type: Literal["reference"]
    reference_type: str

    def validate_value(self, value: Any, context: Optional[Any] = None) -> None:
        """Validate the value of the reference field by
        resolving the value (which should be an id) by using the context"""
        if not isinstance(value, str):  # TODO: Check if the value is a reference to an existing internal type
            raise ValueError(f"Field {self.name} value {value} is not a valid reference")


FieldTypes = FieldTypeNumber | FieldTypeString | FieldTypeDatetime | FieldTypeReference


def create_field_type(name: str, **kwargs: Any) -> FieldTypes:
    """Create an internal type field based on the provided parameters

    Args:
        name (str): The name of the field
        **kwargs: The parameters to create the internal type field

    Raises:
        ValueError: If the field type is unknown
    """
    if name == "":
        raise ValueError("Field name must not be empty.")

    if kwargs["type"] == "number":
        return FieldTypeNumber(name=name, **kwargs)
    if kwargs["type"] == "string":
        return FieldTypeString(name=name, **kwargs)
    if kwargs["type"] == "datetime":
        return FieldTypeDatetime(name=name, **kwargs)
    if kwargs["type"] == "reference":
        return FieldTypeReference(name=name, **kwargs)
    raise ValueError(f"Unknown field type: {kwargs['type']}")
