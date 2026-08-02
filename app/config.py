"""Application configuration.

Every tunable value lives here and is read from environment variables (see
`.env.example`). Nothing else in the codebase should read `os.environ`
directly - that keeps configuration in exactly one place.

The AI provider is not hard-coded. The tool talks to any OpenAI-compatible chat
endpoint, chosen entirely by three values in `.env`: `AI_BASE_URL`,
`AI_API_KEY` and `AI_MODEL`. Switching from Gemini to Groq, OpenRouter, a local
Ollama model or OpenAI is a change to `.env` alone - never to the code.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"
EXAMPLES_DIR = PROJECT_ROOT / "examples"

# Human-readable names for the hosts we expect to see in AI_BASE_URL. Purely
# cosmetic - used in the UI and the logs so the user can see which endpoint is
# actually being called.
_KNOWN_HOSTS = {
    "generativelanguage.googleapis.com": "Google Gemini",
    "api.groq.com": "Groq",
    "openrouter.ai": "OpenRouter",
    "api.openai.com": "OpenAI",
    "api.anthropic.com": "Anthropic",
    "localhost": "local model",
    "127.0.0.1": "local model",
}


class Settings(BaseSettings):
    """Typed view over the environment. Validated once at startup."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- AI provider (any OpenAI-compatible endpoint) -----------------------
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    ai_api_key: str = ""
    ai_model: str = "gemini-2.5-flash"

    # -- shared -------------------------------------------------------------
    max_output_tokens: int = 16000
    host: str = "127.0.0.1"
    port: int = 8000
    log_prompts: bool = False

    @property
    def is_configured(self) -> bool:
        """True only when both a base URL and a key are present.

        Both are required: a key with no endpoint, or an endpoint with no key,
        cannot make a request. The UI uses this to warn instead of crash.
        """
        return bool(self.ai_base_url.strip()) and bool(self.ai_api_key.strip())

    @property
    def provider_name(self) -> str:
        """A readable name for the configured endpoint, derived from its host."""
        host = (urlsplit(self.ai_base_url).hostname or "").lower()
        if host in _KNOWN_HOSTS:
            return _KNOWN_HOSTS[host]
        return host or "unknown provider"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the .env file is parsed only once per process."""
    return Settings()
