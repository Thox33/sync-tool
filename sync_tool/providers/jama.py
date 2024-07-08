from typing import Any, Dict, List, Optional

import structlog
from py_jama_rest_client.client import APIException, JamaClient, ResourceNotFoundException
from py_jama_rest_client.core import CoreException, py_jama_rest_client_logger
from pydantic import BaseModel

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.sync.sync_rule import SyncRuleDestination, SyncRuleQuery, SyncRuleSource

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

    _supported_internal_types = ["items"]

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

    def validate_sync_rule_source(self, source: SyncRuleSource) -> None:
        """Validates the source of a sync rule that it at least should contain project (array),
        itemType (array), documentKey (array) or release (array). Multiple values are allowed.

        Args:
            source: The source to validate.

        Raises:
            ValueError: If the source is invalid.
        """

        # Validate sync rule type
        if source.type not in self._supported_internal_types:
            raise ValueError(f"source type {source.type} not supported by this provider")

        # Validate query filter
        query_filter = source.query.filter

        if (
            "project" not in query_filter
            and "itemType" not in query_filter
            and "documentKey" not in query_filter
            and "release" not in query_filter
        ):
            raise ValueError("source has to contain at least one of project, itemType, documentKey or release")

        if "release" in query_filter and "project" not in query_filter:
            raise ValueError("source has to contain project if release is present")

        if "project" in query_filter and not isinstance(query_filter["project"], list):
            raise ValueError("project has to be a list")

        if "itemType" in query_filter and not isinstance(query_filter["itemType"], list):
            raise ValueError("itemType has to be a list")

        if "documentKey" in query_filter and not isinstance(query_filter["documentKey"], list):
            raise ValueError("documentKey has to be a list")

        if "release" in query_filter and not isinstance(query_filter["release"], list):
            raise ValueError("release has to be a list")

        if "project" in query_filter:
            for project_id in query_filter["project"]:
                if self.get_project_by_id(project_id=project_id) is None:
                    raise ValueError(f"project {project_id} not found")

        if "itemType" in query_filter:
            for item_type in query_filter["itemType"]:
                try:
                    self._client.get_item_type(item_type_id=item_type)
                except ResourceNotFoundException:
                    raise ValueError(f"itemType {item_type} not found")

        if "documentKey" in query_filter:
            for document_key in query_filter["documentKey"]:
                try:
                    items = self._client.get_abstract_items(document_key=document_key)
                    if not items or len(items) == 0:
                        raise ValueError(f"documentKey {document_key} not found")
                except ResourceNotFoundException:
                    raise ValueError(f"documentKey {document_key} not found")

        if "release" in query_filter:
            for release_id in query_filter["release"]:
                try:
                    self._get_release(release_id)
                except ResourceNotFoundException:
                    raise ValueError(f"release {release_id} not found")

    def validate_sync_rule_destination(self, destination: SyncRuleDestination) -> None:
        """Validates the destination of a sync rule that it contains a valid type and query.

        Args:
            destination: The destination to validate.

        Raises:
            ValueError: If the destination is invalid.
        """

        if destination.type == "":
            raise ValueError("destination type has to be specified")

        # Destination type is a concatenation of the internal type and the item type (e.g. "item:Feature")

    def _get_release(self, release_id: str) -> Dict[str, Any]:
        """
        Gets release information for a specific release.

        Args:
            release_id: The api id of the release to fetch

        Returns: JSON object

        """
        resource_path = "releases/" + str(release_id)
        try:
            response = self._client.__core.get(resource_path)
        except CoreException as err:
            py_jama_rest_client_logger.error(err)
            raise APIException(str(err))
        JamaClient.__handle_response_status(response)
        return response.json()["data"]

    def get_user_by_id(self, user_id: str) -> JamaUser | None:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> JamaProject | None:
        return self._projects.get(project_id)

    def get_items_by_project_id(self, project_id: str) -> List[JamaAbstractItem]:
        return self._client.get_abstract_items(project=[project_id])

    async def get_data(self, item_type: str, query: SyncRuleQuery) -> List[Dict[str, Any]]:
        """Get data from the provider.

        Will be called to get data from the provider.

        TODO: As we currently only support items as source we have put everything here. Later on we should split this

        Args:
            item_type: The source to get the data from.
            query: The query to filter the data based on.

        Returns:
            List[Dict[str, Any]]: The data as list.

        Raises:
            ValueError: If the item_type is invalid or not supported by this provider.
            ProviderGetDataError: If the data could not be retrieved.
        """
        query_filter = query.filter

        if "project" in query_filter:
            project_ids = query_filter["project"]
        else:
            project_ids = None

        if "itemType" in query_filter:
            item_types = query_filter["itemType"]
        else:
            item_types = None

        if "documentKey" in query_filter:
            document_keys = query_filter["documentKey"]
        else:
            document_keys = None

        if "release" in query_filter:
            release_ids = query_filter["release"]
        else:
            release_ids = None

        items = self._client.get_abstract_items(
            project=project_ids,
            item_type=item_types,
            document_key=document_keys,
            release=release_ids,
        )

        return items

    async def create_data(
        self, item_type: str, query: SyncRuleQuery, data: Dict[str, Any], dry_run: bool = False
    ) -> None:
        raise ValueError("Usage as destination is currently not supported by this provider.")

    async def teardown(self) -> None:
        pass
