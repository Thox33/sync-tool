import os
from typing import Any, Dict, Optional

import structlog
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core.core_schema import ValidationInfo

from sync_tool.core.provider.mapping import MappingInternalType, create_mapping_internal_type
from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.provider.provider_resolve import provider_resolve

logger = structlog.getLogger(__name__)


class ProviderConfiguration(BaseModel):
    """Internal provider configuration representation

    This will dynamically load the adapter from a python module and validate its configuration.
    """

    model_config = ConfigDict(frozen=True)

    mappings: Dict[str, MappingInternalType]  # dict[internal_type_name, MappingInternalType]
    """Mappings for this provider"""
    options: Optional[Dict[str, Any]] = None
    """Options to configure this provider"""
    provider: str
    """Entrypoint name of the provider. Example: 'sync-tool-provider-testing'"""

    @field_validator("mappings", mode="before")
    @classmethod
    def validate_and_convert_mappings(cls, mappings_to_convert: Any) -> Any:
        """Validates and converts the mappings to the correct format."""

        if not isinstance(mappings_to_convert, dict):
            raise ValueError("Mappings configuration is not a dictionary.")

        mappings = {}
        for internal_type_name, mapping_data in mappings_to_convert.items():
            if "fields" not in mapping_data:
                raise ValueError(f"Missing 'fields' in mapping for internal type '{internal_type_name}'")

            mappings[internal_type_name] = create_mapping_internal_type(
                internal_type_name=internal_type_name, fields=mapping_data["fields"]
            )

        return mappings

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
                logger.debug(f"Resolving environment variable in option {key} with environment variable {env_var}")
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

    def map_raw_data_to_internal_format(self, internal_type_name: str, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map raw data to internal type data."""
        mapping = self.mappings.get(internal_type_name)
        if not mapping:
            raise ValueError(f"Mapping for internal type '{internal_type_name}' not found.")

        return mapping.map_from_raw_data(raw_data)

    def map_internal_data_to_raw_format(self, internal_type_name: str, internal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map internal type data to raw data."""
        mapping = self.mappings.get(internal_type_name)
        if not mapping:
            raise ValueError(f"Mapping for internal type '{internal_type_name}' not found.")

        return mapping.map_to_raw_data(internal_data)
