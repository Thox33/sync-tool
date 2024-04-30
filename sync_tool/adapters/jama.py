from typing import Any, Dict

import structlog
from py_jama_rest_client.client import JamaClient
from pydantic import BaseModel

from ..core.adapter_base import AdapterBase
from ..settings import Settings

logger = structlog.getLogger(__name__)

JamaProject = Dict[str, Any]


class JamaAdapterConfig(BaseModel):
    base_url: str
    client_id: str
    client_secret: str


class JamaAdapter(AdapterBase):
    """Jama API wrapper used for fetching and updating data from Jama."""

    _config: JamaAdapterConfig
    _client: JamaClient

    _projects: Dict[str, JamaProject]  # Normalized by project ID

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
        self._load_projects()

    def _load_projects(self) -> None:
        """Retrieve all projects from Jama. Normalize and store them in a dictionary."""
        projects_list = self._client.get_projects()
        projects_normalized = {}
        for project in projects_list:
            projects_normalized[str(project["id"])] = project
        self._projects = projects_normalized
        logger.debug("loaded projects", projects=self._projects)

    def get_project_by_id(self, project_id: str) -> JamaProject | None:
        return self._projects.get(project_id)

    async def teardown(self) -> None:
        pass
