import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from sync_tool.contants import CONFIGURATION_FILE_NAME
from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_resolve import provider_resolve

logger = structlog.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Internal provider configuration representation

    This will dynamically load the adapter from a python module and validate its configuration.
    """

    model_config = ConfigDict(frozen=True)

    options: Optional[Dict[str, Any]] = None
    """Options to configure this provider"""
    provider: str
    """Entrypoint name of the provider. Example: 'sync-tool-provider-testing'"""

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, provider: str, info: ValidationInfo) -> str:
        """Performs import test and validates options using imported provider handler."""
        logger.debug(f"Validating provider {provider}")
        provider_cls = provider_resolve(provider)
        if "options" in info.data:
            provider_cls.validate_config(options=info.data["options"])
        else:
            provider_cls.validate_config()
        logger.debug(f"Provider {provider} validated")
        return provider

    def make_instance(self) -> ProviderBase:
        """Create a new instance of the provider handler."""
        logger.debug(f"Creating instance of provider {self.provider}")
        if self.options is None:
            return provider_resolve(self.provider)()
        return provider_resolve(self.provider)(**self.options)


class Configuration(BaseModel):
    """Application internal configuration representation.

    Has to be loaded with method :meth:`load_config`.
    """

    model_config = ConfigDict(frozen=True)

    # Provider configuration
    providers: List[ProviderConfig] = Field(default_factory=list)

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, providers: List[ProviderConfig]) -> List[ProviderConfig]:
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
    logger.info(f"Loading configuration from {configuration_path}")
    data = json.loads(configuration_path.read_text(encoding="utf-8"))
    return Configuration(**data)
