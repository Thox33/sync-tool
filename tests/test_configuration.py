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

    # Testing provider does not support options
    with pytest.raises(ValueError):
        ProviderConfig(provider="sync-tool-provider-testing", options={"foo": "bar"})

    ProviderConfig(provider="sync-tool-provider-testing")

    provider_cfg = ProviderConfig(provider="sync-tool-provider-testing")
    assert isinstance(provider_cfg.make_instance(), ProviderBase)


def test_configuration_default_values():
    config = Configuration()
    assert config.providers == []


def test_configuration_validates_providers():
    Configuration(providers=[ProviderConfig(provider="sync-tool-provider-testing")])


def test_load_configuration(fs):
    test_config = Configuration()
    fs.create_file("config.json", contents=test_config.model_dump_json())

    assert test_config == load_configuration()
