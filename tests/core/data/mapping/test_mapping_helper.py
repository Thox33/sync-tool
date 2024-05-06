from sync_tool.core.data.mapping.mapping_helper import get_field_data_by_path


def test_get_field_data_by_path_simple_dict():
    data = {"key": "value"}
    path = "key"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_simple_nested_dict():
    data = {"key1": {"key2": "value"}}
    path = "key1.key2"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_deeper_nested_dict():
    data = {"key1": {"key2": {"key3": "value"}}}
    path = "key1.key2.key3"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_non_existing_key():
    data = {"key1": {"key2": "value"}}
    path = "key1.key3"
    assert get_field_data_by_path(data, path) is None


def test_get_field_data_by_path_empty_path():
    data = {"key1": "value"}
    path = ""
    assert get_field_data_by_path(data, path) is None


def test_get_field_data_by_path_with_dots_in_keys():
    data = {"key1.key2": "value"}
    path = "[key1.key2]"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_with_dots_in_keys_nested():
    data = {"other": {"key1.key2": "value"}}
    path = "other.[key1.key2]"
    assert get_field_data_by_path(data, path) == "value"


def test_get_field_data_by_path_with_dots_in_keys_nested_alternative():
    data = {"key1.key2": {"other": "value"}}
    path = "[key1.key2].other"
    assert get_field_data_by_path(data, path) == "value"
