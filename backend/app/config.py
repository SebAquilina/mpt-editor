"""Application settings loaded from environment / .env."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GEMINI_API_KEY: str = ""
    PEXELS_API_KEY: str = ""
    STORAGE_DIR: str = "./data"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173"

    GEMINI_MODEL: str = "gemini-3.5-flash"
    DEFAULT_VOICE: str = "en-US-GuyNeural"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        for sub in ("projects", "clips", "renders", "uploads"):
            (p / sub).mkdir(exist_ok=True)
        return p

settings = Settings()
