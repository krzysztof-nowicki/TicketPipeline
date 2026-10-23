
from functools import lru_cache

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Temporal Settings
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "ticket-processing-queue"

    # LLM Settings
    LLM_MODE: str = "fake"  # 'fake' or 'openai' or 'local'
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Local LLM Server Settings (for llama.cpp, ollama, etc.)
    LOCAL_SERVER_URL: str = Field(
        default="http://localhost:11434/v1",
        validation_alias=AliasChoices(
            "LOCAL_SERVER_URL",
            "LOCAL_LLM_URL",
            "LOCAL_LLM_SERVER",
            "LOCAL_SERVER",
        ),
    )
    LOCAL_LLM_MODEL: str = "llama3.gguf" # example name of a local model file
    LOCAL_LLM_API_KEY: str = "not-needed"

    @property
    def LOCAL_LLM_URL(self) -> str:
        return self.LOCAL_SERVER_URL

    # Fake simulation settings for testing purposes
    ACTIVITYTOOLS_FAILURE_RATE: float = 0.0

    # Service & Logging
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    LOG_LEVEL: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings()