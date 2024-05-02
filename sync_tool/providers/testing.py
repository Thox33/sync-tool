"""Should only be used inside testing"""

from typing import Any, Dict, Optional

from sync_tool.core.provider.provider_base import ProviderBase


class TestingProvider(ProviderBase):
    """Testing provider for testing purposes (resolving and initialization)."""

    @staticmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        pass

    async def init(self) -> None:
        pass

    async def teardown(self) -> None:
        pass
