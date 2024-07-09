from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from sync_tool.core.sync.sync_transformer import Transformers


class SyncRuleQuery(BaseModel):
    filter: Dict[str, Any]


class SyncRuleSource(BaseModel):
    provider: str
    mapping: str  # Name of mapping in provider context
    query: SyncRuleQuery


class SyncRuleDestination(SyncRuleSource):
    provider: str
    mapping: str  # Name of mapping in provider context
    query: SyncRuleQuery


class SyncRule(BaseModel):
    source: SyncRuleSource
    transformer: Dict[str, List[Transformers]] = Field(default_factory=dict)
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
    def validate_destination(cls, destination: SyncRuleDestination, info: ValidationInfo) -> SyncRuleDestination:
        if info.context is not None and "providers" in info.context:
            # This is the second time configuration validation.
            # Providers are initialized and provided in context.
            # Type: Dict[provider_name, ProviderBase]
            provider = info.context["providers"].get(destination.provider)
            if provider is None:
                raise ValueError(f"Could not resolve provider '{destination.provider}'.")
            provider.validate_sync_rule_destination(destination)

        return destination
