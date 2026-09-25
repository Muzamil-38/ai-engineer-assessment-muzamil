from typing import Literal

from pydantic import AliasChoices, Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    superhero_api_key: SecretStr = Field(min_length=1)
    llm_base_url: HttpUrl = Field(
        validation_alias=AliasChoices("LLM_BASE_URL", "VLLM_BASE_URL")
    )
    llm_api_key: SecretStr = Field(
        default=SecretStr("EMPTY"),
        validation_alias=AliasChoices("LLM_API_KEY", "VLLM_API_KEY"),
    )
    llm_model: str = Field(
        min_length=1, validation_alias=AliasChoices("LLM_MODEL", "VLLM_MODEL")
    )
    llm_request_timeout: float = Field(
        default=300, gt=0, le=600,
        validation_alias=AliasChoices("LLM_REQUEST_TIMEOUT", "VLLM_REQUEST_TIMEOUT"),
    )
    llm_max_tokens: int = Field(default=1800, gt=0)
    llm_token_limit_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
