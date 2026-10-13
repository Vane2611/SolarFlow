from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str = "sqlite:///./solarflow.db"
    SIMULATION_MODE: bool = True
    SIMULATION_INTERVAL_SECONDS: int = 5
    GREENHOUSE_ID: str = "greenhouse-01"
    LOG_LEVEL: str = "info"


settings = Settings()
