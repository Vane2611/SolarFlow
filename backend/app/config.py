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

    # -----------------------------------------------------------------------
    # Crop configuration — tomato defaults
    # -----------------------------------------------------------------------
    TEMP_MAX_C: float = 32.0        # Fan activates reactively above this
    TEMP_WARN_C: float = 30.0       # Warning threshold (predictive trigger)
    HUMIDITY_MAX_PCT: float = 85.0  # Upper humidity limit
    HUMIDITY_MIN_PCT: float = 50.0  # Lower humidity limit
    HYSTERESIS_C: float = 2.0       # Hysteresis below TEMP_MAX_C to turn fan off
    MIN_FAN_RUN_SECONDS: int = 120  # Minimum time fan must stay on
    MIN_FAN_OFF_SECONDS: int = 60   # Minimum time fan must stay off

    # -----------------------------------------------------------------------
    # Hardware
    # -----------------------------------------------------------------------
    SERIAL_PORT: str | None = None  # e.g. "COM3" or "/dev/ttyUSB0"
    SERIAL_BAUD: int = 9600


settings = Settings()
