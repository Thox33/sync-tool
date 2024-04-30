import os

import pytest
from sync_tool.configuration import ProviderConfig, Configuration, load_configuration
from sync_tool.core.provider.provider_base import ProviderBase


def test_provider_config():
    # Must be valid string
    with pytest.raises(ValueError):
        ProviderConfig(provider=None)

    # provider_entry_point_name must not be empty
    with pytest.raises(ValueError):
        ProviderConfig(provider="")

    # Could not resolve provider 'sync-tool-foo'
    with pytest.raises(ValueError):
        ProviderConfig(provider="sync-tool-foo")

    ProviderConfig(provider="sync-tool-provider-testing", options={"foo": "bar"})
    ProviderConfig(provider="sync-tool-provider-testing")

    provider_cfg = ProviderConfig(provider="sync-tool-provider-testing")
    assert isinstance(provider_cfg.make_instance(), ProviderBase)


def test_provider_config_options_special_values():
    os.environ["SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE"] = "baz"
    provider_cfg = ProviderConfig(
        provider="sync-tool-provider-testing", options={"foo": "env(SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE)"}
    )
    assert provider_cfg.options == {"foo": "baz"}
    del os.environ["SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE"]


def test_configuration_default_values():
    config = Configuration()
    assert config.providers == []


def test_configuration_validates_providers():
    Configuration(providers=[ProviderConfig(provider="sync-tool-provider-testing")])


def test_load_configuration(fs):
    test_config = Configuration()
    fs.create_file("config.json", contents=test_config.model_dump_json())

    assert test_config == load_configuration()
