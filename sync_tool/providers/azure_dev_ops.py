from typing import Any, Dict, List, Optional
import structlog
from pydantic import BaseModel
from datetime import datetime
from azure.devops.connection import Connection
from azure.devops.v7_0.core.core_client import CoreClient
from azure.devops.v7_0.work_item_tracking.work_item_tracking_client import WorkItemTrackingClient
from azure.devops.v7_0.work_item_tracking.models import Wiql
from msrest.authentication import BasicAuthentication
import requests

logger = structlog.getLogger(__name__)

AzureUser = Dict[str, Any]
AzureProject = Dict[str, Any]
AzureWorkItem = Dict[str, Any]


class AzureDevOpsConfig(BaseModel):
    organization_url: str
    personal_access_token: str


class AzureDevOpsProvider:
    """Azure DevOps API wrapper used for fetching and updating data from Azure DevOps."""

    _config: AzureDevOpsConfig
    _connection: Optional[Connection] = None
    _core_client: Optional[CoreClient] = None
    _work_item_client: Optional[WorkItemTrackingClient] = None
    _users: Dict[str, AzureUser] = {}
    _projects: Dict[str, AzureProject] = {}

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
        credentials = BasicAuthentication('', self._config.personal_access_token)
        self._connection = Connection(
            base_url=self._config.organization_url,
            creds=credentials
        )
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
                    members_url = f"{self._config.organization_url}/_apis/projects/{project_id}/teams/{team_id}/members?api-version=6.0"
                    response = requests.get(members_url, auth=('', self._config.personal_access_token))

                    if response.status_code == 200:
                        members_data = response.json()
                        for member in members_data.get('value', []):
                            user_id = str(member['identity']['id'])

                            if user_id not in self._users:
                                self._users[user_id] = {
                                    "id": member['identity']['id'],
                                    "display_name": member['identity']['displayName'],
                                    "unique_name": member['identity']['uniqueName'],
                                    "url": member['identity']['url']
                                }
                                logger.debug("loaded user", user_id=user_id, user_details=self._users[user_id])
                    else:
                        logger.error(f"Failed to get team members for team {team_id} in project {project_id}: {response.text}")
            except Exception as e:
                logger.error(f"Failed to get teams or team members for project {project_id}: {str(e)}")

    def get_user_by_id(self, user_id: str) -> Optional[AzureUser]:
        return self._users.get(user_id)

    def get_project_by_id(self, project_id: str) -> Optional[AzureProject]:
        return self._projects.get(project_id)

    def get_work_items(self, project_id: str, earliest_date: Optional[datetime] = None,
                                     latest_date: Optional[datetime] = None, created_by: Optional[str] = None,
                                     state: Optional[str] = None, assigned_to: Optional[str] = None) -> List[AzureWorkItem]:
        """Retrieve all work items for a given project using the project's name and optional filters."""
        # Find the project name using the project ID
        project_name = self._projects[project_id]['name'] if project_id in self._projects else None
        if not project_name:
            logger.error(f"Project with ID {project_id} not found.")
            return []

        # Build the WIQL query dynamically based on provided parameters
        query_parts = [f"Select [Id], [Title], [State] From WorkItems Where [System.TeamProject] = '{project_name}'"]
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
            print(self._work_item_client.get_work_item(query_result.work_items[1].id).fields)
            all_work_items = [self._work_item_client.get_work_item(wi.id).fields for wi in query_result.work_items]
            logger.debug(f"Retrieved {len(all_work_items)} work items for project {project_name}.")
            return all_work_items
        except Exception as e:
            logger.error(f"Failed to retrieve work items for project {project_name}: {str(e)}")
            return []

    async def teardown(self) -> None:
        pass


# Example usage:
if __name__ == "__main__":
    provider = AzureDevOpsProvider(organization_url="https://dev.azure.com/detectomat-pu",
                                   personal_access_token="v7ke2bfdrc2rwqequb754z2wzrwmpimc2zsabu2exshchfbqv7ha")

    import asyncio
    asyncio.run(provider.init())
    # Example of retrieving work items for a specific project
    project_id = "27adbf7c-82a2-4ba7-8cbd-8510ec4bbd41"
    work_items = provider.get_work_items(project_id=project_id,
                                         earliest_date=datetime(2024, 4,1,1,1,1,1),
                                         latest_date=datetime(2024, 7,1,1,1,1,1),
                                         state="Done",
                                         )
