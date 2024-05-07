from typing import Any, Dict, Optional

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
    query: Optional[SyncRuleQuery] = None


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
