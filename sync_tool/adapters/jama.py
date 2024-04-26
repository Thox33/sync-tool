from typing import Any, Dict

import structlog
from py_jama_rest_client.client import JamaClient
from pydantic import BaseModel

from ..core.adapter_base import AdapterBase
from ..settings import Settings

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
    def validate_settings(settings: Settings) -> None:
        if settings is None:
            raise ValueError("settings has to be provided")

        JamaAdapterConfig(
            base_url=settings.jama_base_url,
            client_id=settings.jama_client_id,
            client_secret=settings.jama_client_secret,
        )

    def __init__(self, settings: Settings) -> None:
        self._config = JamaAdapterConfig(
            base_url=settings.jama_base_url,
            client_id=settings.jama_client_id,
            client_secret=settings.jama_client_secret,
        )

    async def init(self) -> None:
        self._client = JamaClient(
            self._config.base_url, credentials=(self._config.client_id, self._config.client_secret), oauth=True
        )
        # Resolve projects
        _projects = self._client.get_projects()
        logger.debug("projects", projects=_projects)

    async def teardown(self) -> None:
        pass
