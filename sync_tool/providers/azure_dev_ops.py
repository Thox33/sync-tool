from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

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
from sync_tool.core.types import RichTextValue

logger = structlog.getLogger(__name__)

AzureUser = Dict[str, Any]
AzureProject = Dict[str, Any]
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

    _supported_internal_types = ["items"]
    _supported_item_types = ["Feature", "User Story"]

    _config: AzureDevOpsConfig
    _connection: Connection
    _core_client: CoreClient
    _work_item_client: WorkItemTrackingClient
    _users: Dict[str, AzureUser] = {}
    _projects: Dict[str, AzureProject] = {}

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
        self._projects = {str(project.id): project.as_dict() for project in projects_response}
        logger.debug("loaded projects", projects=self._projects)

    def _load_users(self) -> None:
        """
        Retrieve all users from Azure DevOps by team, using already loaded projects and
        fetching team members via direct HTTP requests.
        """
        # Check if projects have been loaded
        if not self._projects:
            logger.error("Projects must be loaded before loading users.")
            return

        for project_id, project in self._projects.items():
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

                            if user_id not in self._users:
                                self._users[user_id] = {
                                    "id": member["identity"]["id"],
                                    "display_name": member["identity"]["displayName"],
                                    "unique_name": member["identity"]["uniqueName"],
                                    "url": member["identity"]["url"],
                                }
                                logger.debug("loaded user", user_id=user_id, user_details=self._users[user_id])
                    else:
                        logger.error(
                            f"Failed to get team members for team {team_id} in project {project_id}: {response.text}"
                        )
            except Exception as e:
                logger.error(f"Failed to get teams or team members for project {project_id}: {str(e)}")

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

        if "project" not in query_filter:
            raise ValueError("source has to contain project")

        if "project" in query_filter and not isinstance(query_filter["project"], str):
            raise ValueError("project has to be a string")

        if "itemType" in query_filter and not isinstance(query_filter["itemType"], list):
            raise ValueError("itemType has to be a list")

        if "project" in query_filter:
            for project_id in query_filter["project"]:
                if self.get_project_by_id(project_id=project_id) is None:
                    raise ValueError(f"project {project_id} not found")

        if "itemType" in query_filter:
            for item_type in query_filter["itemType"]:
                if item_type not in self._supported_item_types:
                    raise ValueError(f"itemType {item_type} not supported")

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
        internal_type, item_type = destination.type.split(":")
        if internal_type not in self._supported_internal_types:
            raise ValueError(f"destination internal type {internal_type} is not supported")
        if item_type not in self._supported_item_types:
            raise ValueError(f"destination item type {item_type} is not supported")

        # The destination should contain an valid query to find a correct parent to create the synced items
        if not destination.query:
            raise ValueError("destination query has to be specified")

        dest_query = destination.query
        if not dest_query.filter:
            raise ValueError("destination query has to contain a filter")

        project = dest_query.filter.get("project")
        item_id = dest_query.filter.get("itemId")

        if not project:
            raise ValueError("destination query has to contain a project")
        if not item_id:
            raise ValueError("destination query has to contain an itemId")

        if project not in self._projects:
            raise ValueError(f"destination query project {project} not found")

        if item_id and not project:
            raise ValueError("destination query has to contain a project if provided an itemId")

        if item_id and project:
            work_items = self.get_work_items(project_id=project, item_id=item_id)
            if not work_items:
                raise ValueError(f"destination query item {item_id} not found in project {project}")
            if len(work_items) > 1:
                raise ValueError(f"destination query item {item_id} found multiple times in project {project}")

    def get_user_by_id(self, user_id: str) -> Optional[AzureUser]:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> Optional[AzureProject]:
        return self._projects.get(project_id)

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
        project_id = query_filter["project"]
        items = self.get_work_items(project_id=project_id)

        # Filter items by type
        if "itemType" in query_filter:
            items = [item for item in items if item["System.WorkItemType"] in query_filter["itemType"]]

        return items

    async def create_data(
        self, item_type: str, query: SyncRuleQuery, data: Dict[str, Any], dry_run: bool = False
    ) -> None:
        """
        Create data in the provider. For the azure devops workitems we have to create an json patch document.
        Which itself is an array of operations. As we create data in the destination we only have add operations.
        We have to make sure to add the correct path for nested objects,
        e.g. "/fields/System.Title".
        Additionally we have to add the workitem as child to the destination query workitem.

        Args:
            item_type: The internal type of data inside of data and the item type to create, e.g. "items:Feature"
            query: The destination query from the configuration of the sync rule
            data: Plain object; already run through the transformation and mapping to be in the right format
            dry_run: If True, the data will not be created but the operation will be logged
        """
        # Destination type is a concatenation of the internal type and the item type (e.g. "item:Feature")
        internal_type, work_item_type = item_type.split(":")

        # Get the project id
        project_id = query.filter["project"]
        if not project_id:
            raise ValueError("project has to be provided")

        # Get the destination work item
        item_id = query.filter["itemId"]
        parent_work_item_url = f"{self._config.organization_url}/_apis/wit/workitems/{item_id}"
        if item_id:
            logger.debug("Destination work item", parent_work_item_url=parent_work_item_url)
        else:
            logger.error("No parent relation will be created")

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

            patch_document.append({"op": "add", "path": f"/{key}", "value": correct_value})

        if item_id:
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
                type=work_item_type,
                bypass_rules=True,  # Needed to create as another user and also set the correct dates
            )
            logger.debug("Created work item", work_item_id=work_item.id, work_item=work_item)

    def get_work_items(
        self,
        project_id: str,
        item_id: Optional[str] = None,
        earliest_date: Optional[datetime] = None,
        latest_date: Optional[datetime] = None,
        created_by: Optional[str] = None,
        state: Optional[str] = None,
        assigned_to: Optional[str] = None,
    ) -> List[AzureWorkItem]:
        """Retrieve all work items for a given project using the project's name and optional filters."""
        # Find the project name using the project ID
        project_name = self._projects[project_id]["name"] if project_id in self._projects else None
        if not project_name:
            logger.error(f"Project with ID {project_id} not found.")
            return []

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
            all_work_items = [self._work_item_client.get_work_item(wi.id).fields for wi in query_result.work_items]
            logger.debug(f"Retrieved {len(all_work_items)} work items for project {project_name}.")
            return all_work_items
        except Exception as e:
            logger.error(f"Failed to retrieve work items for project {project_name}: {str(e)}")
            return []

    async def teardown(self) -> None:
        pass
