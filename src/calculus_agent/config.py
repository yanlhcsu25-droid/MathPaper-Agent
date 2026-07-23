from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CALCULUS_AGENT_")

    app_name: str = "Chinese Math Paper Agent"
    database_url: str = "sqlite:///./calculus_agent.db"
    ollama_base_url: str = "http://127.0.0.1:11434"
    solver_model: str = "qwen3:14b"
    solver_timeout_seconds: float = 120.0
    external_data_root: Path = Path("../data/external/ugmathbench")


@lru_cache
def get_settings() -> Settings:
    return Settings()
