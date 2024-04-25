from typing import Any, Dict, Optional

import structlog
from py_jama_rest_client.client import JamaClient
from pydantic import BaseModel

from sync_tool.core.adapter_base import AdapterBase

logger = structlog.getLogger(__name__)


class JamaAdapterConfig(BaseModel):
    base_url: str
    client_id: str
    client_secret: str


class JamaAdapter(AdapterBase):
    """Jama API wrapper used for fetching and updating data from Jama."""

    _config: JamaAdapterConfig
    _client: JamaClient

    _projects: Dict[str, Any]

    @staticmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        if options is None:
            raise ValueError("options has to be provided")

        JamaAdapterConfig(**options)

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self._config = JamaAdapterConfig(base_url=base_url, client_id=client_id, client_secret=client_secret)

    async def init(self) -> None:
        self._client = JamaClient(
            self._config.base_url, credentials=(self._config.client_id, self._config.client_secret), oauth=True
        )
        # Resolve projects
        _projects = self._client.get_projects()
        logger.debug("Projects", projects=_projects)

    async def teardown(self) -> None:
        pass
