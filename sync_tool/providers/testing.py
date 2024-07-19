"""Should only be used inside testing"""

from typing import Any, Dict, List, Optional

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.sync.sync_rule import SyncRuleDestination, SyncRuleQuery, SyncRuleSource


class TestingProvider(ProviderBase):
    """Testing provider for testing purposes (resolving and initialization)."""

    @staticmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        pass

    async def init(self) -> None:
        pass

    def validate_sync_rule_source(self, source: SyncRuleSource) -> None:
        pass

    def validate_sync_rule_destination(self, destination: SyncRuleDestination) -> None:
        pass

    async def get_data(self, item_type: str, query: SyncRuleQuery) -> List[Dict[str, Any]]:
        return []

    async def get_data_by_id(self, item_type: str, unique_id: str) -> None | Dict[str, Any]:
        return None

    async def create_data(
        self, item_type: str, query: SyncRuleQuery, data: Dict[str, Any], dry_run: bool = False
    ) -> None | str:
        pass

    async def teardown(self) -> None:
        pass
