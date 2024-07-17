from __future__ import annotations

import re
from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel
from typing_extensions import TypedDict

ValueT = TypeVar("ValueT")


class FieldType(BaseModel, Generic[ValueT], metaclass=ABCMeta):
    """Internal representation of an field of the internal type. Providing validation of field values"""

    name: str
    type: Any
    default: Optional[Any] = None

    @abstractmethod
    def validate_value(
        self, value: Any, context: Optional[Any] = None
    ) -> ValueT:  # TODO: Add context type (including other internal types)
        """Validate the value of the field. Has to be implemented in the child classes.

        Raises:
            ValueError: If the value is invalid
        """
        pass

    def get_default(self) -> Optional[ValueT]:
        """Get the default value of the field. Override in the child classes if different implementation is needed"""
        return self.default


class FieldTypeInt(FieldType[int]):
    """Internal representation of an int field of the internal type"""

    type: Literal["int"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> int:
        """Validate the value of the number field"""
        if not isinstance(value, int):
            raise ValueError(f"Field {self.name} value {value} is not an int")

        return int(value)


class FieldTypeFloat(FieldType[float]):
    """Internal representation of an float field of the internal type"""

    type: Literal["float"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> float:
        """Validate the value of the number field"""
        if not isinstance(value, float):
            raise ValueError(f"Field {self.name} value {value} is not an float")

        return float(value)


class FieldTypeString(FieldType[str]):
    """Internal representation of an string field of the internal type"""

    type: Literal["string"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> str:
        """Validate the value of the string field"""
        if not isinstance(value, (str, int, float)):
            raise ValueError(f"Field {self.name} value {value} is not a string - or convertible to a string")

        return str(value)


class FieldTypeDatetime(FieldType[datetime]):
    """Internal representation of an datetime field of the internal type"""

    type: Literal["datetime"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> datetime:
        """Validate the value of the datetime field"""
        if not isinstance(value, (datetime, str, int, float)):
            raise ValueError(f"Field {self.name} value {value} is not a datetime - or convertible to a datetime")

        if isinstance(value, (int, float)):
            return datetime.utcfromtimestamp(value)
        if isinstance(value, str):
            return datetime.fromisoformat(value)

        return value

    def get_default(self) -> Optional[Any]:
        """Get the default value of the datetime field. If the user provided the string "now" as default,
        return the current datetime. Otherwise return the default value"""
        from datetime import datetime

        return datetime.now() if self.default == "now" else self.default


class FieldTypeReference(FieldType[str]):
    """Internal representation of an reference field of the internal type. This"""

    type: Literal["reference"]
    reference_type: str

    def validate_value(self, value: Any, context: Optional[Any] = None) -> str:
        """Validate the value of the reference field by
        resolving the value (which should be an id) by using the context"""
        if not isinstance(
            value, (str, int, float)
        ):  # TODO: Check if the value is a reference to an existing internal type
            raise ValueError(
                f"Field {self.name} value {value} is not a valid reference - or convertible to a reference"
            )

        return str(value)


class RichTextValue(BaseModel):
    """Internal representation of a rich text value"""

    value: str
    attachments: Optional[list[str]] = (
        None  # Found inside the rich text value. This is a list of the attachment url extracted from the html img tags.
    )


def filter_is_not_empty_string(value: str) -> bool:
    """Check if the value is not an empty string"""
    return value != ""


def extract_attachments(value: str) -> list[str]:
    """Extract attachments from the rich text value (html img) tag and store it as string list.

    Example:
        <img src="https://example.com/image.jpg" alt="image" />
        attachment: https://example.com/image.jpg
    """

    regex = re.compile(r'<img.*?src="(.*?)".*?>', re.IGNORECASE)
    return list(filter(filter_is_not_empty_string, regex.findall(value)))


class FieldTypeRichText(FieldType[RichTextValue]):
    """Internal representation of an rich text field of the internal type"""

    type: Literal["richtext"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> RichTextValue:
        """Validate the value of the rich text field"""
        if not isinstance(value, str):
            raise ValueError(f"Field {self.name} value {value} is not a string")

        rich_text_value = RichTextValue(value=value)
        # Extract attachments from the value (html img) tag and store it as string list
        rich_text_value.attachments = extract_attachments(value)

        return rich_text_value


class SyncStatusValueEntry(TypedDict):
    id: str
    url: str


def extract_sync_status_items(value: str) -> List[SyncStatusValueEntry]:
    """Extract sync status items from the rich text value (html a) tag and store it as a list of SyncStatusValueEntry.

    Example:
        <a href="https://destination-system.com/itemId?id=XXX">XXX</a>
        id: XXX
        url: https://destination-system.com/itemId?id=XXX
    """

    regex = re.compile(
        r'<a.*?href="(.*?)".*?>(.*?)</a>', re.IGNORECASE | re.MULTILINE
    )  # Alternative: <a.+?\s*href\s*=\s*["\']?([^"\'\s>]+)["\']?>(.*)</a>
    return [
        {
            "id": match[1],
            "url": match[0],
        }
        for match in regex.findall(value)
    ]


class SyncStatusValue(BaseModel):
    """Internal representation of a sync status value"""

    value: str
    entries: List[SyncStatusValueEntry] = []


class FieldTypeSyncStatus(FieldType[SyncStatusValue]):
    """Internal representation of an rich text field representing the current synchonrization status using html tags.

    Example html:
    <a href="https://destination-system.com/itemId?id=XXX">XXX</a>

    Example value:
    [
        {
            "id": "XXX",
            "url": "https://destination-system.com/itemId?id=XXX",
        },
        #... other sync status items...
    ]
    """

    type: Literal["syncStatus"]

    def validate_value(self, value: Any, context: Optional[Any] = None) -> SyncStatusValue:
        """Validate the value of the sync status field"""
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"Field {self.name} value {value} is not a string")

        sync_status_value = SyncStatusValue(value=value)
        sync_status_value.entries = extract_sync_status_items(value)

        return sync_status_value


FieldTypes = (
    FieldTypeInt
    | FieldTypeFloat
    | FieldTypeString
    | FieldTypeDatetime
    | FieldTypeReference
    | FieldTypeRichText
    | FieldTypeSyncStatus
)


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

    if kwargs["type"] == "int":
        return FieldTypeInt(name=name, **kwargs)
    if kwargs["type"] == "float":
        return FieldTypeFloat(name=name, **kwargs)
    if kwargs["type"] == "string":
        return FieldTypeString(name=name, **kwargs)
    if kwargs["type"] == "datetime":
        return FieldTypeDatetime(name=name, **kwargs)
    if kwargs["type"] == "reference":
        return FieldTypeReference(name=name, **kwargs)
    if kwargs["type"] == "richtext":
        return FieldTypeRichText(name=name, **kwargs)
    if kwargs["type"] == "syncStatus":
        return FieldTypeSyncStatus(name=name, **kwargs)
    raise ValueError(f"Unknown field type: {kwargs['type']}")
