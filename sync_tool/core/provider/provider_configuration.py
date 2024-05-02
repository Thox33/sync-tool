import os
from typing import Any, Dict, Optional

import structlog
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core.core_schema import ValidationInfo

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_resolve import provider_resolve

logger = structlog.getLogger(__name__)


class ProviderConfiguration(BaseModel):
    """Internal provider configuration representation

    This will dynamically load the adapter from a python module and validate its configuration.
    """

    model_config = ConfigDict(frozen=True)

    options: Optional[Dict[str, Any]] = None
    """Options to configure this provider"""
    provider: str
    """Entrypoint name of the provider. Example: 'sync-tool-provider-testing'"""

    @field_validator("options")
    @classmethod
    def validate_options(cls, options: Optional[Dict[str, Any]]) -> Dict[str, Any] | None:
        """As we do not validate the options our self, we just pass them
        through using the provider validator. We instead search for special values in the options
        which could be e.g. environment variables."""

        if options is None:
            return options

        # Check for special values in options
        for key, value in options.items():
            if isinstance(value, str) and value.startswith("env(") and value.endswith(")") and len(value) > 5:
                env_var = value[4:-1]
                resolved = os.environ.get(env_var)
                options[key] = resolved

        return options

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
