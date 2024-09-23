from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

import structlog
from py_jama_rest_client.client import APIException, JamaClient, ResourceNotFoundException
from py_jama_rest_client.core import CoreException
from pydantic import BaseModel

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.sync.sync_rule import SyncRuleDestination, SyncRuleQuery, SyncRuleSource
from sync_tool.core.types import RichTextValue, SyncStatusValue

logger = structlog.getLogger(__name__)


class JamaUser(TypedDict):
    id: str
    username: str
    email: str


JamaItemTypeID = str


class JamaProject(TypedDict):
    id: str
    name: str


class JamaRelease(TypedDict):
    id: str
    name: str


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
    _item_types: Dict[str, JamaItemTypeID]  # Normalized by display name; Value is the item type ID
    _projects_by_id: Dict[str, JamaProject]  # Normalized by project ID
    _projects_by_name: Dict[str, JamaProject]  # Normalized by project name
    _releases_by_project_id: Dict[
        str, Dict[str, JamaRelease]
    ]  # str#1 = Jama Project Id; str#2 = Release Id; Normalized by release name

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
        logger.debug("creating client")
        client = JamaProvider._create_client(config)
        logger.debug("validating credentials")
        client.get_current_user()
        logger.debug("credentials are valid")

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
        self._load_item_types()
        self._load_projects()
        self._releases_by_project_id = {}

    def _load_users(self) -> None:
        """Retrieve all users from Jama. Normalize and store them in a dictionary."""
        users_list = self._client.get_users()
        users_normalized = {}
        for user in users_list:
            users_normalized[str(user["id"])] = JamaUser(
                id=str(user["id"]), username=user["username"], email=user["email"]
            )
        self._users = users_normalized
        logger.debug("loaded users", users=self._users)

    def _load_item_types(self) -> None:
        """Retrieve all item types from Jama. Normalize and store them in a dictionary."""
        item_types_list = self._client.get_item_types()
        item_types_normalized = {}
        for item_type in item_types_list:
            item_types_normalized[item_type["display"]] = item_type["id"]
        self._item_types = item_types_normalized
        logger.debug("loaded item types", itemTypes=self._item_types)

    def _load_projects(self) -> None:
        """Retrieve all projects from Jama. Normalize and store them in a dictionary."""
        projects_list = self._client.get_projects()
        projects_normalized_by_id = {}
        projects_normalized_by_name = {}
        for project in projects_list:
            jama_project = JamaProject(id=str(project["id"]), name=project["fields"]["name"])
            projects_normalized_by_id[str(project["id"])] = jama_project
            projects_normalized_by_name[str(project["fields"]["name"])] = jama_project
        self._projects_by_id = projects_normalized_by_id
        self._projects_by_name = projects_normalized_by_name
        logger.debug("loaded projects", projects=self._projects_by_id)

    def _load_releases_by_project_id(self, project_id: str) -> None:
        """Retrieve all releases for a project from Jama. Normalize and store them in a dictionary."""
        releases_list = self._get_releases(project_id=project_id)
        releases_normalized: Dict[str, JamaRelease] = {}
        for release in releases_list:
            releases_normalized[str(release["name"])] = JamaRelease(id=str(release["id"]), name=release["name"])
        self._releases_by_project_id[str(project_id)] = releases_normalized
        logger.debug("loaded releases for project", project_id=project_id, releases=self._releases_by_project_id)

    async def get_item_url_for_id(self, unique_id: str) -> str:
        """Return the URL to the item in the provider.

        Args:
            unique_id: The unique id of the item.

        Returns:
            str: The URL to the item.
        """
        return f"{self._config.url}/perspective.req#/items/{unique_id}"

    def validate_sync_rule_source(self, source: SyncRuleSource) -> None:
        """Validates the source of a sync rule that it at least should contain project (array),
        itemType (array), documentKey (array) or release (array). Multiple values are allowed.

        Args:
            source: The source to validate.

        Raises:
            ValueError: If the source is invalid.
        """

        # Validate sync rule mapping
        # TODO: Validate sync rule mapping

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

        if "tag" in query_filter and "project" not in query_filter:
            raise ValueError("source has to contain project if tag is present")

        if "project" in query_filter and not isinstance(query_filter["project"], list):
            raise ValueError("project has to be a list")

        if "itemType" in query_filter and not isinstance(query_filter["itemType"], list):
            raise ValueError("itemType has to be a list")

        if "documentKey" in query_filter and not isinstance(query_filter["documentKey"], list):
            raise ValueError("documentKey has to be a list")

        if "release" in query_filter and not isinstance(query_filter["release"], list):
            raise ValueError("release has to be a list")

        if "tag" in query_filter and not isinstance(query_filter["tag"], list):
            raise ValueError("tag has to be a list")

        if "project" in query_filter:
            for project_name in query_filter["project"]:
                if project_name not in self._projects_by_name:
                    raise ValueError(f"project {project_name} not found")

        if "itemType" in query_filter:
            for item_type in query_filter["itemType"]:
                if item_type not in self._item_types:
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
            # Resolve releases for each project
            project_ids = [self._projects_by_name[project_name]["id"] for project_name in query_filter["project"]]
            for project_id in project_ids:
                self._load_releases_by_project_id(project_id=project_id)

            # Check if provided release name existing in any provided project id
            for release_name in query_filter["release"]:
                found = False
                for project_id in project_ids:
                    if self._releases_by_project_id[project_id][release_name] is not None:
                        found = True
                        break

                if not found:
                    raise ValueError(f"release {release_name} not found in provided project names")

        if "tag" in query_filter and "project" in query_filter:
            project_name = query_filter["project"][0]
            project_id = self._projects_by_name[project_name]["id"]
            tags = self._client.get_tags(project=project_id)
            tag_names = [tag["name"] for tag in tags]
            for tag in query_filter["tag"]:
                if tag not in tag_names:
                    raise ValueError(f"tag {tag} not found in project {project_name}")

    def validate_sync_rule_destination(self, destination: SyncRuleDestination) -> None:
        """Validates the destination of a sync rule that it contains a valid mapping and query.

        Args:
            destination: The destination to validate.

        Raises:
            ValueError: If the destination is invalid.
        """

        if destination.mapping == "":
            raise ValueError("destination mapping has to be specified")

        # The destination should contain an valid query to find a correct parent to create the synced items
        if not destination.query:
            raise ValueError("destination query has to be specified")

        dest_query = destination.query
        if not dest_query.filter:
            raise ValueError("destination query has to contain a filter")

        project = dest_query.filter.get("project")
        parent_item_id = dest_query.filter.get("parentItemId")

        if not project:
            raise ValueError("destination query has to contain a project")
        if not parent_item_id:
            raise ValueError("destination query has to contain an parentItemId")

        if project not in self._projects_by_name:
            raise ValueError(f"destination query project {project} not found")

        if parent_item_id and not project:
            raise ValueError("destination query has to contain a project if provided an parentItemId")

        if parent_item_id and project:
            found_item = self._client.get_item(parent_item_id)
            if not found_item:
                raise ValueError(f"destination query item {parent_item_id} not found in project {project}")

    def _get_releases(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Gets release information for a specific project id.

        Args:
            project_id: The api id of the project to fetch releases for

        Returns: List[{id: number, name: string, ...}]

        """
        resource_path = "releases?project=" + str(project_id)
        try:
            response = self._client._JamaClient__core.get(resource_path)
        except CoreException as err:
            logger.error(err)
            raise APIException(str(err))
        JamaClient._JamaClient__handle_response_status(response)
        json_obj = response.json()
        logger.debug("loaded releases for project", project_id=project_id, json_obj=json_obj)
        return json_obj["data"]

    def get_user_by_id(self, user_id: str) -> JamaUser | None:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> JamaProject | None:
        return self._projects_by_id.get(project_id)

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
            possible_projects: List[JamaProject | None] = [
                self._projects_by_name.get(project_name) for project_name in query_filter["project"]
            ]
            projects: List[JamaProject] = [project for project in possible_projects if project is not None]
            project_ids = [project["id"] for project in projects]
        else:
            project_ids = None

        if "itemType" in query_filter:
            item_types = [self._item_types.get(item_type_name) for item_type_name in query_filter["itemType"]]
        else:
            item_types = None

        if "documentKey" in query_filter:
            document_keys = query_filter["documentKey"]
        else:
            document_keys = None

        if "release" in query_filter and project_ids:
            release_ids = []
            for project_id in project_ids:
                for release_name in query_filter["release"]:
                    release = self._releases_by_project_id.get(project_id, {}).get(release_name)
                    if release:
                        release_ids.append(release["id"])
        else:
            release_ids = None

        items = self._client.get_abstract_items(
            project=project_ids,
            item_type=item_types,
            document_key=document_keys,
            release=release_ids,
        )

        # Filter by tags if provided
        if "tag" in query_filter:
            # Enrich items with tags
            for item in items:
                item["tags"] = [tag["name"] for tag in self._client.get_item_tags(item_id=item["id"])]

            # Filter items by tags
            tags = query_filter["tag"]
            items = [item for item in items if any(tag in item["tags"] for tag in tags)]
            logger.debug("filtered items by tags", items=items)

        return items

    async def get_data_by_id(self, item_type: str, unique_id: str) -> None | Dict[str, Any]:
        """Get data from the provider by using the id.

        Will be called to get data from the provider.

        Args:
            item_type: The source to get the data from.
            unique_id: The id of the item to get.
        """
        try:
            item = self._client.get_item(item_id=unique_id)
            return item
        except ResourceNotFoundException:
            return None

    async def create_data(
        self, item_type: str, query: SyncRuleQuery, data: Dict[str, Any], dry_run: bool = False
    ) -> None | str:
        """
        Create data in the provider. For the jama items we have to create an json object.
        Format:
        {
          "project": 0,
          "itemType": 0,
          "location": {
            "parent": {
              "item": 0,
              "project": 0
            }
          },
          "fields": {
            "additionalProp1": {},
            "additionalProp2": {},
            "additionalProp3": {}
          }
        }

        Args:
            item_type: The internal type of data to create, e.g. "User Story"
            query: The destination query from the configuration of the sync rule
            data: Plain object; already run through the transformation and mapping to be in the right format
            dry_run: If True, the data will not be created but the operation will be logged

        Returns:
            str: The unique id of the created item
        """

        # Get the project name
        project_name = query.filter["project"]
        project = self._projects_by_name.get(project_name)
        if not project:
            raise ValueError(f"project {project_name} not found")
        project_id = project["id"]

        # Get the destination work item
        parent_item_id = query.filter["parentItemId"]
        if not parent_item_id:
            raise ValueError("parentItemId has to be provided")

        # Get item type id
        item_type_id = self._item_types.get(item_type)
        if not item_type_id:
            raise ValueError(f"itemType {item_type} not found")

        # Correct data inside of fields
        fields = {}
        for key, value in data["fields"].items():
            correct_value = value
            if isinstance(value, datetime):
                correct_value = value.isoformat()
            elif isinstance(value, RichTextValue):
                # @TODO: For now we only use the string value without inline attachment handling
                correct_value = value.value
            elif isinstance(value, SyncStatusValue):
                correct_value = value.get_value()
            fields[key] = correct_value

        # Create the item
        item_data = {
            "project": project_id,
            "itemType": item_type_id,
            "location": {"parent": {"item": parent_item_id}},
            "fields": fields,
        }
        logger.debug("New item", item=item_data)

        if not dry_run:
            item_id = self._client.post_item(
                project=item_data["project"],
                item_type_id=item_data["itemType"],
                child_item_type_id=None,
                location={"item": parent_item_id},
                fields=item_data["fields"],
            )
            logger.debug("Created item", itemId=item_id)
            return str(item_data)

        return None

    async def patch_data(
        self, item_type: str, query: SyncRuleQuery, unique_id: str, data: Dict[str, Any], dry_run: bool = False
    ) -> None:
        # Correct data inside of fields
        fields = {}
        for key, value in data["fields"].items():
            correct_value = value
            if isinstance(value, datetime):
                correct_value = value.isoformat()
            elif isinstance(value, RichTextValue):
                # @TODO: For now we only use the string value without inline attachment handling
                correct_value = value.value
            elif isinstance(value, SyncStatusValue):
                correct_value = value.get_value()
            fields[key] = correct_value

        # Prepare the patches
        patches = []
        for key, value in fields.items():
            patches.append({"op": "add", "path": f"/fields/{key}", "value": value})
        logger.debug("Patches", patches=patches)

        if not dry_run:
            self._client.patch_item(item_id=unique_id, patches=patches)

    async def teardown(self) -> None:
        pass
