import os

import pytest

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_configuration import ProviderConfiguration


def test_provider_configuration():
    # Must be valid string
    with pytest.raises(ValueError):
        ProviderConfiguration(provider=None)

    # provider_entry_point_name must not be empty
    with pytest.raises(ValueError):
        ProviderConfiguration(provider="")

    # Could not resolve provider 'sync-tool-foo'
    with pytest.raises(ValueError):
        ProviderConfiguration(provider="sync-tool-foo")

    ProviderConfiguration(provider="sync-tool-provider-testing", options={"foo": "bar"})
    ProviderConfiguration(provider="sync-tool-provider-testing")

    provider_cfg = ProviderConfiguration(provider="sync-tool-provider-testing")
    assert isinstance(provider_cfg.make_instance(), ProviderBase)


def test_provider_configuration_options_special_values():
    os.environ["SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE"] = "baz"
    provider_cfg = ProviderConfiguration(
        provider="sync-tool-provider-testing", options={"foo": "env(SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE)"}
    )
    assert provider_cfg.options == {"foo": "baz"}
    del os.environ["SYNC_TOOL_TESTING_ENVIRONMENT_VARIABLE"]
