from typing import Tuple, Type

from pydantic import Field
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings class for the sync_tool
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", json_file="config.json", json_file_encoding="utf-8"
    )

    # Jama API settings
    jama_base_url: str = Field(alias="JAMA_BASE_URL")
    jama_client_id: str = Field(alias="JAMA_CLIENT_ID")
    jama_client_secret: str = Field(alias="JAMA_CLIENT_SECRET")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),
        )
