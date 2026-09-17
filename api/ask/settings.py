from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from ask.service import PLACEHOLDER_CORPUS_CUTOFF


class Settings(BaseSettings):
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    corpus_cutoff: date = PLACEHOLDER_CORPUS_CUTOFF
    database_url: str = ""
    web_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
