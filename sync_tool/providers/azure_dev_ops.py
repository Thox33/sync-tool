from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

import requests
import structlog
from azure.devops.connection import Connection
from azure.devops.v7_0.core.core_client import CoreClient
from azure.devops.v7_0.work_item_tracking.models import Wiql
from azure.devops.v7_0.work_item_tracking.work_item_tracking_client import WorkItemTrackingClient
from msrest.authentication import BasicAuthentication
from pydantic import BaseModel

from sync_tool.core.provider.provider_base import ProviderBase
from sync_tool.core.sync.sync_rule import SyncRuleDestination, SyncRuleQuery, SyncRuleSource
from sync_tool.core.types import RichTextValue, SyncStatusValue

logger = structlog.getLogger(__name__)


class AzureUser(TypedDict):
    id: str
    display_name: str
    unique_name: str


class AzureProject(TypedDict):
    id: str
    name: str
    wits: List[str]  # Work item types


AzureWorkItem = Dict[str, Any]


class AzureDevOpsConfig(BaseModel):
    organization_url: str
    personal_access_token: str


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    items: List[Tuple[str, Any] | Dict[str, Any]] = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, Dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(cast(List[Tuple[str, Any]], items))


"""Create workitem

[
{
    "op": "add",
    "path": "/fields/System.Title",
    "value": "Test"
},
{
    "op": "add",
    "path": "/fields/System.Description",
    "value": "Test description"
},
{
    "op": "add",
    "path": "/relations/-",
    "value": {
        "rel": "System.LinkTypes.Hierarchy-Reverse",
        "url": "https://dev.azure.com/organization/project/_apis/wit/workItems/1"
    }
}
"""

"""Update workitem

[
{
    "op": "replace",
    "path": "/fields/System.Title",
    "value": "Test"
}
]
"""


class AzureDevOpsProvider(ProviderBase):
    """Azure DevOps API wrapper used for fetching and updating data from Azure DevOps."""

    _config: AzureDevOpsConfig
    _connection: Connection
    _core_client: CoreClient
    _work_item_client: WorkItemTrackingClient

    _users: Dict[str, AzureUser]  # Normalized by ID
    _projects_by_id: Dict[str, AzureProject]  # Normalized by ID
    _projects_by_name: Dict[str, AzureProject]  # Normalized by name

    @staticmethod
    def validate_config(options: Optional[Dict[str, Any]] = None) -> None:
        if options is None:
            raise ValueError("options has to be provided")

        AzureDevOpsConfig(**options)
        # TODO: Validate credentials

    def __init__(self, organization_url: str, personal_access_token: str) -> None:
        self._config = AzureDevOpsConfig(
            organization_url=organization_url,
            personal_access_token=personal_access_token,
        )

    async def init(self) -> None:
        # Setup connection and clients
        self._connect()
        # Load and cache users and projects
        self._load_projects()
        self._load_users()

    def _connect(self) -> None:
        """Initialize the connection to Azure DevOps."""
        credentials = BasicAuthentication("", self._config.personal_access_token)
        self._connection = Connection(base_url=self._config.organization_url, creds=credentials)
        self._core_client = self._connection.clients.get_core_client()
        self._work_item_client = self._connection.clients.get_work_item_tracking_client()

    def _load_projects(self) -> None:
        """Retrieve all projects from Azure DevOps. Normalize and store them in a dictionary."""
        projects_response = self._core_client.get_projects()
        normalized_by_id = {}
        normalized_by_name = {}
        for project in projects_response:
            project_work_item_types = self._work_item_client.get_work_item_types(project.id)
            azure_project = AzureProject(
                id=project.id, name=project.name, wits=[wit.name for wit in project_work_item_types]
            )
            normalized_by_id[project.id] = azure_project
            normalized_by_name[project.name] = azure_project
        self._projects_by_id = normalized_by_id
        self._projects_by_name = normalized_by_name
        logger.debug("loaded projects", projects=self._projects_by_id)

    def _load_users(self) -> None:
        """
        Retrieve all users from Azure DevOps by team, using already loaded projects and
        fetching team members via direct HTTP requests.
        """
        # Check if projects have been loaded
        if not self._projects_by_id:
            logger.error("Projects must be loaded before loading users.")
            return

        normalized_users = {}
        for project_id, project in self._projects_by_id.items():
            try:
                # Fetch teams for the current project using the Azure DevOps Client
                teams = self._core_client.get_teams(project_id=project_id)
                for team in teams:
                    team_id = team.id
                    # Construct the URL for fetching members of the current team using direct HTTP requests
                    members_url = (
                        f"{self._config.organization_url}/_apis/projects/"
                        f"{project_id}/teams/{team_id}/members?api-version=6.0"
                        # This should be the same version as the python client
                    )
                    response = requests.get(members_url, auth=("", self._config.personal_access_token), timeout=10)

                    if response.status_code == 200:
                        members_data = response.json()
                        for member in members_data.get("value", []):
                            user_id = str(member["identity"]["id"])

                            if user_id not in normalized_users:
                                normalized_users[user_id] = AzureUser(
                                    id=user_id,
                                    display_name=member["identity"]["displayName"],
                                    unique_name=member["identity"]["uniqueName"],
                                )
                    else:
                        logger.error(
                            f"Failed to get team members for team {team_id} in project {project_id}: {response.text}"
                        )
            except Exception as e:
                logger.error(f"Failed to get teams or team members for project {project_id}: {str(e)}")

        self._users = normalized_users
        logger.debug("loaded users", users=self._users)

    async def get_item_url_for_id(self, unique_id: str) -> str:
        """Return the URL to the item in the provider.

        Args:
            unique_id: The unique id of the item.

        Returns:
            str: The URL to the item.
        """
        work_item = self._work_item_client.get_work_item(id=int(unique_id))
        if work_item is None:
            raise ValueError(f"Work item with ID {unique_id} not found")

        # Grap the project name from the work item
        project_name = work_item.fields["System.TeamProject"]

        return f"{self._config.organization_url}/{project_name}/_workitems/edit/{unique_id}/"

    def validate_sync_rule_source(self, source: SyncRuleSource) -> None:
        """Validates the source of a sync rule that it at least should contain project (array),
        itemType (array), documentKey (array) or release (array). Multiple values are allowed.

        Args:
            source: The source to validate.

        Raises:
            ValueError: If the source is invalid.
        """

        # Validate sync rule mapping
        # TODO: Validate source mapping

        # Validate query filter
        query_filter = source.query.filter

        if "project" not in query_filter:
            raise ValueError("source has to contain project")

        if "project" in query_filter and not isinstance(query_filter["project"], str):
            raise ValueError("project has to be a string")

        if "itemType" in query_filter and not isinstance(query_filter["itemType"], str):
            raise ValueError("itemType has to be a string")

        if "project" in query_filter:
            project_name = query_filter["project"]
            if self._projects_by_name.get(project_name) is None:
                raise ValueError(f"project {project_name} not found")

        if "itemType" in query_filter and "project" not in query_filter:
            raise NotImplementedError("Please provide a project filter for itemType filtering")
        if "itemType" in query_filter and "project" in query_filter:
            project_name = query_filter["project"]
            project = self._projects_by_name.get(project_name)
            if not project:
                raise ValueError(f"project {project_name} not found")
            if query_filter["itemType"] not in project["wits"]:
                raise ValueError(f"itemType {query_filter['itemType']} not found in project {project_name}")

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
            work_items = self.get_work_items(project_name=project, item_id=parent_item_id)
            if not work_items:
                raise ValueError(f"destination query item {parent_item_id} not found in project {project}")
            if len(work_items) > 1:
                raise ValueError(f"destination query item {parent_item_id} found multiple times in project {project}")

    def get_user_by_id(self, user_id: str) -> Optional[AzureUser]:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> Optional[AzureProject]:
        return self._projects_by_id.get(project_id)

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

        # Get work items
        project_name = query_filter["project"]
        items = self.get_work_items(project_name=project_name)

        # Filter items by type
        if "itemType" in query_filter:
            items = [item for item in items if item["fields"]["System.WorkItemType"] in query_filter["itemType"]]

        return items

    async def get_data_by_id(self, item_type: str, unique_id: str) -> None | Dict[str, Any]:
        """Get data from the provider by using the id.

        Will be called to get data from the provider.

        Args:
            item_type: The source to get the data from.
            unique_id: The id of the item to get.

        Returns:
            Dict[str, Any]: The data
            None: If the item was not found

        Raises:
            ValueError: If the item_type is invalid or not supported by this provider.
            ProviderGetDataError: If the data could not be retrieved.
        """
        try:
            work_item = self._work_item_client.get_work_item(id=int(unique_id)).as_dict()
            return work_item
        except Exception as e:
            logger.error(f"Failed to get work item {unique_id}: {str(e)}")
            return None

    async def create_data(
        self, item_type: str, query: SyncRuleQuery, data: Dict[str, Any], dry_run: bool = False
    ) -> None | str:
        """
        Create data in the provider. For the azure devops workitems we have to create an json patch document.
        Which itself is an array of operations. As we create data in the destination we only have add operations.
        We have to make sure to add the correct path for nested objects,
        e.g. "/fields/System.Title".
        Additionally we have to add the workitem as child to the destination query workitem.

        Args:
            item_type: The internal type of data to create, e.g. "Feature"
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
        parent_work_item_url = f"{self._config.organization_url}/_apis/wit/workitems/{parent_item_id}"
        if parent_item_id:
            logger.debug("Destination work item", parent_work_item_url=parent_work_item_url)
        else:
            logger.info("No parent relation will be created")

        # Create the json patch document
        patch_document = []
        # data as to be flattened to be able to create the patch document
        flat_data = flatten_dict(data, sep="/")
        # Now we can create the patch document
        for key, value in flat_data.items():
            # We are not allowed to patch the work item id
            if "id" in key:
                continue
            # example for key: fields/System.Title
            correct_value = value
            if isinstance(value, datetime):
                correct_value = value.isoformat()
            elif isinstance(value, RichTextValue):
                # @TODO: For now we only use the string value without inline attachment handling
                correct_value = value.value
            elif isinstance(value, SyncStatusValue):
                correct_value = value.get_value()

            patch_document.append({"op": "add", "path": f"/{key}", "value": correct_value})

        if parent_item_id:
            patch_document.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {"rel": "System.LinkTypes.Hierarchy-Reverse", "url": parent_work_item_url},
                }
            )
        logger.debug("Patch document", patch_document=patch_document)

        # Create the work item
        if not dry_run:
            work_item = self._work_item_client.create_work_item(
                document=patch_document,
                project=project_id,
                type=item_type,
                bypass_rules=True,  # Needed to create as another user and also set the correct dates
            )
            logger.debug("Created work item", work_item_id=work_item.id, work_item=work_item)
            return str(work_item.id)

        return None

    async def patch_data(
        self, item_type: str, query: SyncRuleQuery, unique_id: str, data: Dict[str, Any], dry_run: bool = False
    ) -> None:
        # Get the project name
        project_name = query.filter["project"]
        project = self._projects_by_name.get(project_name)
        if not project:
            raise ValueError(f"project {project_name} not found")
        project_id = project["id"]

        # Get the destination work item to get the current revision number
        work_item = self._work_item_client.get_work_item(id=int(unique_id), project=project_id)
        current_rev = work_item.rev

        # Create the json patch document
        patch_document = [{"op": "test", "path": "/rev", "value": int(current_rev)}]
        # data as to be flattened to be able to create the patch document
        flat_data = flatten_dict(data, sep="/")
        # Now we can create the patch document
        for key, value in flat_data.items():
            # We are not allowed to patch the work item id
            if "id" in key:
                continue
            # example for key: fields/System.Title
            correct_value = value
            if isinstance(value, datetime):
                correct_value = value.isoformat()
            elif isinstance(value, RichTextValue):
                # @TODO: For now we only use the string value without inline attachment handling
                correct_value = value.value
            elif isinstance(value, SyncStatusValue):
                correct_value = value.get_value()

            patch_document.append({"op": "add", "path": f"/{key}", "value": correct_value})

        logger.debug("Patch document", patch_document=patch_document)

        # Update the work item
        work_item = self._work_item_client.update_work_item(
            id=int(unique_id),
            project=project_id,
            document=patch_document,
            validate_only=dry_run,
            bypass_rules=True,  # Needed to create as another user and also set the correct dates
            suppress_notifications=True,
        )
        logger.debug("Updated work item", work_item_id=work_item.id, work_item=work_item)

    def get_work_items(
        self,
        project_name: str,
        item_id: Optional[str] = None,
        earliest_date: Optional[datetime] = None,
        latest_date: Optional[datetime] = None,
        created_by: Optional[str] = None,
        state: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> List[AzureWorkItem]:
        """Retrieve all work items for a given project using the project's name and optional filters."""
        # Build the WIQL query dynamically based on provided parameters
        query_parts = [
            f"Select [Id], [Title], [State] From WorkItems Where [System.TeamProject] = '{project_name}'"  # nosec B206
        ]
        if item_id:
            query_parts.append(f"And [Id] = '{item_id}'")
        if earliest_date:
            query_parts.append(f"And [System.CreatedDate] >= '{earliest_date.strftime('%Y-%m-%d')}'")
        if latest_date:
            query_parts.append(f"And [System.CreatedDate] <= '{latest_date.strftime('%Y-%m-%d')}'")
        if created_by:
            query_parts.append(f"And [System.CreatedBy] = '{created_by}'")
        if state:
            query_parts.append(f"And [System.State] = '{state}'")
        if assigned_to:
            query_parts.append(f"And [System.AssignedTo] = '{assigned_to}'")

        wiql_query = Wiql(query=" ".join(query_parts))
        try:
            query_result = self._work_item_client.query_by_wiql(wiql_query)
            all_work_items = [self._work_item_client.get_work_item(wi.id).as_dict() for wi in query_result.work_items]
            logger.debug(f"Retrieved {len(all_work_items)} work items for project {project_name}.")
            return all_work_items
        except Exception as e:
            logger.error(f"Failed to retrieve work items for project {project_name}: {str(e)}")
            return []

    async def teardown(self) -> None:
        pass
