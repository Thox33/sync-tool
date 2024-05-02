from typing import Any, Dict, List, Optional

import structlog
from py_jama_rest_client.client import JamaClient
from pydantic import BaseModel

from sync_tool.core.provider.provider_base import ProviderBase

logger = structlog.getLogger(__name__)

JamaUser = Dict[str, Any]
JamaProject = Dict[str, Any]
JamaAbstractItem = Dict[str, Any]


class JamaProviderConfig(BaseModel):
    url: str
    clientId: str
    clientSecret: str


class JamaProvider(ProviderBase):
    """Jama API wrapper used for fetching and updating data from Jama."""

    _config: JamaProviderConfig
    _client: JamaClient

    _users: Dict[str, JamaUser]  # Normalized by user ID
    _projects: Dict[str, JamaProject]  # Normalized by project ID

    @staticmethod
    def _create_client(config: JamaProviderConfig) -> JamaClient:
        return JamaClient(
            config.url,
            credentials=(config.clientId, config.clientSecret),
            oauth=True,
        )

    @staticmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        if options is None:
            raise ValueError("options has to be provided")

        config = JamaProviderConfig(**options)
        # Validate credentials
        client = JamaProvider._create_client(config)
        client.get_current_user()

    def __init__(self, url: str, clientId: str, clientSecret: str) -> None:
        self._config = JamaProviderConfig(
            url=url,
            clientId=clientId,
            clientSecret=clientSecret,
        )

    async def init(self) -> None:
        # Setup client
        self._client = JamaProvider._create_client(self._config)
        self._client.set_allowed_results_per_page(50)  # Defaults to 20 results per page. Max is 50.
        # Load and cache users and projects
        self._load_users()
        self._load_projects()

    def _load_users(self) -> None:
        """Retrieve all users from Jama. Normalize and store them in a dictionary."""
        users_list = self._client.get_users()
        users_normalized = {}
        for user in users_list:
            users_normalized[str(user["id"])] = user
        self._users = users_normalized
        logger.debug("loaded users", users=self._users)

    def _load_projects(self) -> None:
        """Retrieve all projects from Jama. Normalize and store them in a dictionary."""
        projects_list = self._client.get_projects()
        projects_normalized = {}
        for project in projects_list:
            projects_normalized[str(project["id"])] = project
        self._projects = projects_normalized
        logger.debug("loaded projects", projects=self._projects)

    def get_user_by_id(self, user_id: str) -> JamaUser | None:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> JamaProject | None:
        return self._projects.get(project_id)

    def get_items_by_project_id(self, project_id: str) -> List[JamaAbstractItem]:
        return self._client.get_abstract_items(project=[project_id])

    async def teardown(self) -> None:
        pass
