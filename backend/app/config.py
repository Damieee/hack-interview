from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
ENV_CANDIDATES = [ROOT_DIR / ".env", BASE_DIR / ".env"]

ENV_FILE = ENV_CANDIDATES[0]
for candidate in ENV_CANDIDATES:
    if candidate.exists():
        ENV_FILE = candidate
        break

load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    redis_url: str = Field(..., alias="REDIS_URL")
    history_ttl_seconds: int = Field(60 * 60 * 24, alias="HISTORY_TTL_SECONDS")
    default_model: str = Field("gpt-4o-mini", alias="DEFAULT_MODEL")
    default_position: str = Field("Python Developer", alias="DEFAULT_POSITION")
    vision_model: str = Field("gpt-4o-mini", alias="VISION_MODEL")
    allow_origins: list[str] = Field(default=["*"])

    class Config:
        env_file = ENV_FILE
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
