import pytest
from pydantic import ValidationError

from sync_tool.core.data.mapping.mapping_provider import MappingProvider, create_mapping_provider


def test_init_valid():
    # Test initialization with valid arguments
    mapping = MappingProvider(
        provider_name="test_provider",
        mappings={"test_internal_type": {"fields": {"field1": "field1", "field2": "field2.data"}}},
    )
    assert isinstance(mapping, MappingProvider)


def test_init_invalid_provider_name():
    # Test initialization with invalid provider name
    with pytest.raises(ValidationError):
        MappingProvider(provider_name=123, mappings={})


def test_init_invalid_mappings():
    # Test initialization with invalid mappings
    with pytest.raises(ValidationError):
        MappingProvider(provider_name="test_provider", mappings={"test_internal_type": "invalid"})


def test_map_raw_data_valid():
    # Test map_raw_data with valid internal type name and raw data
    mapping = MappingProvider(
        provider_name="test_provider",
        mappings={"test_internal_type": {"fields": {"field1": "field1", "field2": "field2.data"}}},
    )
    raw_data = {"field1": "value1", "field2": {"data": "value2"}}
    result = mapping.map_raw_data("test_internal_type", raw_data)
    assert result == {"field1": "value1", "field2": "value2"}


def test_map_raw_data_invalid_internal_type():
    # Test map_raw_data with invalid internal type name
    mapping = MappingProvider(
        provider_name="test_provider",
        mappings={"test_internal_type": {"fields": {"field1": "field1", "field2": "field2.data"}}},
    )
    raw_data = {"key": "value"}
    with pytest.raises(ValueError):
        mapping.map_raw_data("invalid_internal_type", raw_data)


def test_map_raw_data_no_mapping():
    # Test map_raw_data when a mapping for the given internal type does not exist
    mapping = MappingProvider(provider_name="test_provider", mappings={})
    raw_data = {"key": "value"}
    with pytest.raises(ValueError):
        mapping.map_raw_data("test_internal_type", raw_data)


def test_create_mapping_provider_with_valid_data():
    # Given
    provider_name = "test_provider"
    mappings = {
        "internal_type_1": {"fields": {}},
        "internal_type_2": {"fields": {}},
    }
    possible_internal_types = ["internal_type_1", "internal_type_2"]

    # When/Then
    create_mapping_provider(provider_name, mappings, possible_internal_types)


def test_create_mapping_provider_with_invalid_internal_type():
    # Given
    provider_name = "test_provider"
    mappings = {
        "internal_type_1": {"fields": {}},
        "internal_type_3": {"fields": {}},
    }
    possible_internal_types = ["internal_type_1", "internal_type_2"]

    # When/Then
    with pytest.raises(ValueError) as context:
        create_mapping_provider(provider_name, mappings, possible_internal_types)

    assert str(context.value) == "Internal type 'internal_type_3' not found in possible internal types."
