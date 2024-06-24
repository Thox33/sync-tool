from typing import Any, Dict

from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo


class SyncRuleQuery(BaseModel):
    filter: Dict[str, Any]


class SyncRuleSource(BaseModel):
    provider: str
    type: str
    query: SyncRuleQuery


class SyncRuleDestination(BaseModel):
    provider: str
    type: str
    query: SyncRuleQuery

    @field_validator("type")
    @classmethod
    def validate_type_contains_colon(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("Type must contain a colon. Format: 'internal_type:item_type'")
        return value


class SyncRule(BaseModel):
    source: SyncRuleSource
    destination: SyncRuleDestination

    @field_validator("source")
    @classmethod
    def validate_source(cls, source: SyncRuleSource, info: ValidationInfo) -> SyncRuleSource:
        if info.context is not None and "providers" in info.context:
            # This is the second time configuration validation.
            # Providers are initialized and provided in context.
            # Type: Dict[provider_name, ProviderBase]
            provider = info.context["providers"].get(source.provider)
            if provider is None:
                raise ValueError(f"Could not resolve provider '{source.provider}'.")
            provider.validate_sync_rule_source(source)

        return source

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, destination: SyncRuleSource, info: ValidationInfo) -> SyncRuleSource:
        if info.context is not None and "providers" in info.context:
            # This is the second time configuration validation.
            # Providers are initialized and provided in context.
            # Type: Dict[provider_name, ProviderBase]
            provider = info.context["providers"].get(destination.provider)
            if provider is None:
                raise ValueError(f"Could not resolve provider '{destination.provider}'.")
            provider.validate_sync_rule_destination(destination)

        return destination
