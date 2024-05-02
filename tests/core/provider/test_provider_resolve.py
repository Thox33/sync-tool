import pytest

from sync_tool.core.provider.provider_resolve import provider_resolve


def test_provider_resolve_raise_type_error():
    with pytest.raises(TypeError) as err:
        provider_resolve(provider_entry_point_name=123)
    assert str(err.value) == "provider_entry_point_name must be a string."


def test_provider_resolve_raise_value_error():
    with pytest.raises(ValueError) as err:
        provider_resolve(provider_entry_point_name="")
    assert str(err.value) == "provider_entry_point_name must not be empty."


def test_provider_resolve_raise_value_error_missing_entry_point():
    with pytest.raises(ValueError) as err:
        provider_resolve(provider_entry_point_name="sync-tool-foo")
    assert str(err.value) == "Could not resolve provider 'sync-tool-foo'."


def test_provider_resolve_success():
    provider_resolve(provider_entry_point_name="sync-tool-provider-testing")
