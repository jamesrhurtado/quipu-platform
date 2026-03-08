from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives in the project root (one level above backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_gpt4o_deployment: str = "gpt-4o"
    azure_openai_gpt4o_mini_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-12-01-preview"

    # Database
    database_url: str = "postgresql://sentinel:sentinel@localhost:5432/sentinel"

    # NASA
    nasa_api_key: str = "DEMO_KEY"
    nasa_firms_map_key: str = ""

    # ReliefWeb
    reliefweb_appname: str = "sentinel-agent"

    # Bluesky
    bluesky_enabled: bool = False
    bluesky_handle: str = ""
    bluesky_app_password: str = ""
    bluesky_notifications_enabled: bool = True

    # Microsoft Teams
    teams_enabled: bool = True
    teams_webhook_url: str = ""

    # Dashboard
    dashboard_url: str = "http://localhost:3000"

    # App
    poll_interval_seconds: int = 300
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": str(_ENV_FILE), "extra": "ignore"}


settings = Settings()
