from sync_tool.configuration import ProviderConfiguration, Configuration, load_configuration


def test_configuration_default_values():
    config = Configuration()
    assert config.providers == {}


def test_configuration_validates_providers():
    Configuration(providers=[ProviderConfiguration(provider="sync-tool-provider-testing")])


def test_load_configuration(fs):
    test_config = Configuration()
    fs.create_file("config.json", contents=test_config.model_dump_json())

    assert test_config == load_configuration()
