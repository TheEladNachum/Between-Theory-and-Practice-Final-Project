"""Application configuration.

Every tunable value lives here and is read from environment variables (see
`.env.example`). Nothing else in the codebase should read `os.environ`
directly - that keeps configuration in exactly one place.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

# Effort levels accepted by the Claude API, cheapest/fastest first.
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")


class Settings(BaseSettings):
    """Typed view over the environment. Validated once at startup."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    anthropic_effort: str = "high"
    max_output_tokens: int = 16000

    host: str = "127.0.0.1"
    port: int = 8000
    log_prompts: bool = False

    @property
    def is_configured(self) -> bool:
        """True when an API key is present, so the UI can warn instead of crash."""
        return bool(self.anthropic_api_key.strip())

    @property
    def effort(self) -> str:
        """The effort level, falling back to 'high' if someone typos the env var."""
        value = self.anthropic_effort.strip().lower()
        return value if value in VALID_EFFORTS else "high"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
