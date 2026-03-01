from pydantic_settings import BaseSettings


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

    # App
    poll_interval_seconds: int = 300
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
