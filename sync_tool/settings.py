from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Settings class for the sync_tool
    """

    # Jama API settings
    jama_base_url: str = Field(alias="JAMA_BASE_URL")
    jama_client_id: str = Field(alias="JAMA_CLIENT_ID")
    jama_client_secret: str = Field(alias="JAMA_CLIENT_SECRET")
