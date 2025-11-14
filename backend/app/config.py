from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    default_model: str = Field("gpt-4o-mini", alias="DEFAULT_MODEL")
    default_position: str = Field("Python Developer", alias="DEFAULT_POSITION")
    vision_model: str = Field("gpt-4o-mini", alias="VISION_MODEL")
    allow_origins: list[str] = Field(default=["*"])

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
