from typing import Dict

from sync_tool.core.data.mapping.mapping_internal_type import MappingInternalType, create_mapping_internal_type


def test_map_raw_data():
    # Arrange
    mapping = MappingInternalType(internal_type_name="User", fields={"name": "user.name", "age": "user.age"})
    raw_data = {"user": {"name": "John Doe", "age": 30}}

    # Act
    mapped_data = mapping.map_raw_data(raw_data)

    # Assert
    assert mapped_data == {"name": "John Doe", "age": 30}


def test_create_mapping_internal_type():
    # Define test data
    internal_type_name = "TestType"
    fields: Dict[str, str] = {"name": "path.to.name", "age": "path.to.age"}

    # Call the function
    mapping_internal_type = create_mapping_internal_type(internal_type_name, fields)

    # Assert the result
    assert isinstance(mapping_internal_type, MappingInternalType)
    assert mapping_internal_type.internal_type_name == internal_type_name
    assert mapping_internal_type.fields == fields
