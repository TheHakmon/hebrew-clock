from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = 8765
    display_lag: int = 8
    # Defaults to the project root (parent of app/); override with FONT_DIR env var.
    font_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    gtag_id: str | None = None  # set GTAG_ID env var to enable Google Analytics

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
