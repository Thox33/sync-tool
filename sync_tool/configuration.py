import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import structlog
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sync_tool.contants import CONFIGURATION_FILE_NAME
from sync_tool.core.provider import ProviderBase, ProviderConfiguration
from sync_tool.core.sync import SyncConfiguration
from sync_tool.core.types import InternalType, create_internal_type

logger = structlog.getLogger(__name__)


class Configuration(BaseModel):
    """Application internal configuration representation.

    Has to be loaded with method :meth:`load_config`.
    """

    model_config = ConfigDict(frozen=True)

    # Types configuration
    types: Dict[str, InternalType] = Field(default_factory=dict)  # dict[internal_type_name, InternalType]

    # Provider configuration
    providers: Dict[str, ProviderConfiguration] = Field(default_factory=dict)  # Dict key is the provider name

    # Sync configuration
    syncs: Dict[str, SyncConfiguration] = Field(default_factory=dict)  # Dict key is the sync name

    @field_validator("types", mode="before")
    @classmethod
    def validate_and_convert(cls, types_to_convert: Any) -> Any:
        """Validates and converts the types to the correct format.

        Types are converted to InternalType objects.
        """

        # Handle types configuration
        if not isinstance(types_to_convert, dict):
            raise ValueError("Types configuration is not a dictionary.")

        possible_internal_types = list(types_to_convert.keys())
        types = {}
        for type_name, type_data in types_to_convert.items():
            if "fields" not in type_data:
                raise ValueError(f"Missing 'fields' in type {type_name}")
            if "options" not in type_data:
                type_data["options"] = {}

            types[type_name] = create_internal_type(
                name=type_name,
                fields=type_data["fields"],
                options=type_data["options"],
                possible_other_types=possible_internal_types,
            )

        return types

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, providers: Dict[str, ProviderConfiguration]) -> Dict[str, ProviderConfiguration]:
        """Validate all provider configurations."""
        if not all(isinstance(provider.make_instance(), ProviderBase) for provider in providers.values()):
            raise ValueError("Not all providers are of type ProviderBase.")

        return providers

    def get_internal_type(self, name: str) -> InternalType | None:
        """Get internal type by name.

        Args:
            name (str): Name of the internal type.

        Returns:
            InternalType: Internal type object.
        """
        return self.types.get(name)

    def get_provider(self, provider_name: str) -> ProviderConfiguration | None:
        """Get the provider configuration for a given provider name.

        Args:
            provider_name (str): Name of the provider configuration to get.

        Returns:
            ProviderConfiguration: The provider configuration.
            None: If the provider configuration does not exist.
        """
        return self.providers.get(provider_name)

    def get_sync(self, sync_name: str) -> SyncConfiguration | None:
        """Get the sync configuration for a given sync name.

        Args:
            sync_name (str): Name of the sync configuration to get.

        Returns:
            SyncConfiguration: The sync configuration.
            None: If the sync configuration does not exist.
        """
        return self.syncs.get(sync_name)


def load_configuration(config_path: str = CONFIGURATION_FILE_NAME, load_environment_file: bool = True) -> Configuration:
    """Loads the configuration from a file. Validates the configuration twice.
    First without initialized provider in context.
    Second time with initialized provider in context. This is necessary to validate the sync rules.

    Args:
        config_path (str): Path to the configuration file. Defaults to "config.json".
        load_environment_file (bool): Load environment variables from .env file.
            Useful to disable for automatic testing. Defaults to True.

    Returns:
        Configuration: The loaded configuration.

    Raises:
        OSError: If the file could not be opened.
        ValidationError: If the configuration is invalid.
    """

    configuration_path = Path(config_path)

    # Load environment variables from .env file
    if (
        load_environment_file
    ):  # This is only for testing purposes as we got an filesystem error while searching for the .env file
        load_dotenv(dotenv_path=str(Path.cwd() / ".env"))

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
