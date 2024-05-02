from datetime import datetime

from sync_tool.core.data.type.field_type import (
    FieldTypeNumber,
    FieldTypeString,
    FieldTypeDatetime,
    FieldTypeReference,
)
from sync_tool.core.data.type.internal_type import create_internal_type


def test_create_internal_type():
    name = "test"
    fields = {
        "field1": {"type": "number"},
        "field2": {"type": "string", "default": "test"},
        "field3": {"type": "datetime"},
        "field4": {"type": "reference", "reference_type": "test2"},
    }
    possible_other_types = ["test2"]

    internal_type = create_internal_type(name, fields, possible_other_types)

    assert internal_type.name == name
    assert len(internal_type.fields) == 4
    assert isinstance(internal_type.fields[0], FieldTypeNumber)
    assert internal_type.fields[0].name == "field1"
    assert isinstance(internal_type.fields[1], FieldTypeString)
    assert internal_type.fields[1].name == "field2"
    assert internal_type.fields[1].default == "test"
    assert isinstance(internal_type.fields[2], FieldTypeDatetime)
    assert internal_type.fields[2].name == "field3"
    assert isinstance(internal_type.fields[3], FieldTypeReference)
    assert internal_type.fields[3].name == "field4"
    assert internal_type.fields[3].reference_type == "test2"


def test_create_internal_type_invalid_reference():
    name = "test"
    fields = {
        "field1": {"type": "reference", "reference_type": "test2"},
    }
    possible_other_types = ["test3"]

    try:
        create_internal_type(name, fields, possible_other_types)
        assert False
    except ValueError as e:
        assert str(e) == "Reference type test2 is not available. Others: ['test3']"


def test_internal_type_store_data():
    name = "test"
    fields = {
        "field1": {"type": "number"},
        "field2": {"type": "string", "default": "test"},
        "field3": {"type": "datetime"},
        "field4": {"type": "reference", "reference_type": "test2"},
    }
    possible_other_types = ["test2"]

    internal_type = create_internal_type(name, fields, possible_other_types)

    data = {
        "field1": 123,
        "field2": "test",
        "field3": datetime.now(),
        "field4": "123",
    }

    internal_type.store_data("test_provider", data)

    assert internal_type.data["test_provider"] == data


def test_internal_type_store_data_invalid():
    name = "test"
    fields = {
        "field1": {"type": "number"},
        "field2": {"type": "string", "default": "test"},
        "field3": {"type": "datetime"},
        "field4": {"type": "reference", "reference_type": "test2"},
    }
    possible_other_types = ["test2"]

    internal_type = create_internal_type(name, fields, possible_other_types)

    data = {
        "field1": 123,
        "field2": "test",
        "field3": "test",
        "field4": "123",
    }

    try:
        internal_type.store_data("test_provider", data)
        assert False
    except Exception as e:
        assert (
            str(e) == "Validation for provider test_provider with data "
            "{'field1': 123, 'field2': 'test', 'field3': 'test', 'field4': '123'}"
            " failed (1 sub-exception)"
        )
        assert len(e.exceptions) == 1
        assert str(e.exceptions[0]) == "Field field3 value test is not a datetime"
