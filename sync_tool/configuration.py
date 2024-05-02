import json
from pathlib import Path
from typing import List

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sync_tool.contants import CONFIGURATION_FILE_NAME
from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_configuration import ProviderConfiguration

logger = structlog.getLogger(__name__)


class Configuration(BaseModel):
    """Application internal configuration representation.

    Has to be loaded with method :meth:`load_config`.
    """

    model_config = ConfigDict(frozen=True)

    # Provider configuration
    providers: List[ProviderConfiguration] = Field(default_factory=list)

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, providers: List[ProviderConfiguration]) -> List[ProviderConfiguration]:
        """Validate all provider configurations."""
        if not all(isinstance(provider.make_instance(), ProviderBase) for provider in providers):
            raise ValueError("Not all providers are of type ProviderBase.")

        return providers


def load_configuration(config_path: str = CONFIGURATION_FILE_NAME) -> Configuration:
    """Loads the configuration from a file.

    Args:
        config_path (str): Path to the configuration file. Defaults to "config.json".

    Returns:
        Configuration: The loaded configuration.

    Raises:
        OSError: If the file could not be opened.
        ValidationError: If the configuration is invalid.
    """

    configuration_path = Path(config_path)

    # Check if we need to create a new configuration file
    if not configuration_path.exists():
        logger.warning(f"Configuration file {configuration_path} does not exist. Creating a new one.")
        configuration_path.write_text(Configuration().model_dump_json(), encoding="utf-8")

    # Load the configuration from file
    logger.debug(f"Loading configuration from {configuration_path}")
    data = json.loads(configuration_path.read_text(encoding="utf-8"))
    return Configuration(**data)
