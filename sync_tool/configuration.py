import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Dict

import structlog
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sync_tool.contants import CONFIGURATION_FILE_NAME
from sync_tool.core.data.data_configuration import DataConfiguration
from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_configuration import ProviderConfiguration
from sync_tool.core.sync.sync_configuration import SyncConfiguration

logger = structlog.getLogger(__name__)


class Configuration(BaseModel):
    """Application internal configuration representation.

    Has to be loaded with method :meth:`load_config`.
    """

    model_config = ConfigDict(frozen=True)

    # Data configuration
    data: DataConfiguration = Field(default_factory=dict)

    # Provider configuration
    providers: Dict[str, ProviderConfiguration] = Field(default_factory=dict)  # Dict key is the provider name

    # Sync configuration
    sync: Dict[str, SyncConfiguration] = Field(default_factory=dict)  # Dict key is the sync name

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, providers: Dict[str, ProviderConfiguration]) -> Dict[str, ProviderConfiguration]:
        """Validate all provider configurations."""
        if not all(isinstance(provider.make_instance(), ProviderBase) for provider in providers.values()):
            raise ValueError("Not all providers are of type ProviderBase.")

        return providers

    def get_sync(self, sync_name: str) -> SyncConfiguration | None:
        """Get the sync configuration for a given sync name.

        Args:
            sync_name (str): Name of the sync configuration to get.

        Returns:
            SyncConfiguration: The sync configuration.
            None: If the sync configuration does not exist.
        """
        return self.sync.get(sync_name)

    def get_provider(self, provider_name: str) -> ProviderConfiguration | None:
        """Get the provider configuration for a given provider name.

        Args:
            provider_name (str): Name of the provider configuration to get.

        Returns:
            ProviderConfiguration: The provider configuration.
            None: If the provider configuration does not exist.
        """
        return self.providers.get(provider_name)


def load_configuration(config_path: str = CONFIGURATION_FILE_NAME) -> Configuration:
    """Loads the configuration from a file. Validates the configuration twice.
    First without initialized provider in context.
    Second time with initialized provider in context. This is necessary to validate the sync rules.

    Args:
        config_path (str): Path to the configuration file. Defaults to "config.json".

    Returns:
        Configuration: The loaded configuration.

    Raises:
        OSError: If the file could not be opened.
        ValidationError: If the configuration is invalid.
    """

    configuration_path = Path(config_path)

    # Load environment variables from .env file
    load_dotenv()

    # Check if we need to create a new configuration file
    if not configuration_path.exists():
        logger.warning(f"Configuration file {configuration_path} does not exist. Creating a new one.")
        configuration_path.write_text(Configuration().model_dump_json(), encoding="utf-8")

    # Load the configuration from file
    logger.debug(f"Loading configuration from {configuration_path}")
    data = json.loads(configuration_path.read_text(encoding="utf-8"))
    config = Configuration(**deepcopy(data))

    # Validate the configuration a second time with an dict of initialized providers
    providers = {provider_name: provider.make_instance() for provider_name, provider in config.providers.items()}
    for provider in providers.values():
        asyncio.run(provider.init())
    Configuration.model_validate(
        obj=deepcopy(data), strict=True, from_attributes=False, context={"providers": providers}
    )

    return config
