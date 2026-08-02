"""Small, testable helpers for updating IncidentIQ's local ``.env`` file.

Only the three browser-editable AI settings are touched.  Existing comments,
provider examples and unrelated settings remain exactly where they are.  The
API key is accepted only as write-only input: this module never returns or
logs it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from app import config

EDITABLE_KEYS = ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL")


def ensure_env_file(
    env_path: Path | None = None,
    example_path: Path | None = None,
) -> None:
    """Create ``.env`` from ``.env.example`` when it does not yet exist."""
    destination = Path(env_path) if env_path is not None else config.ENV_FILE
    template = Path(example_path) if example_path is not None else config.ENV_EXAMPLE_FILE

    if destination.exists():
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if template.is_file():
        destination.write_bytes(template.read_bytes())
    else:
        destination.write_text("", encoding="utf-8")


def update_ai_settings(
    *,
    api_key: str | None,
    model: str,
    base_url: str,
    env_path: Path | None = None,
    example_path: Path | None = None,
) -> None:
    """Persist browser-provided AI settings without exposing the secret.

    ``api_key=None`` intentionally keeps the existing key.  This lets the UI
    offer model/endpoint edits without ever reading the saved key back into the
    browser.  A supplied key replaces every active ``AI_API_KEY`` assignment,
    while commented provider examples are left untouched.
    """
    destination = Path(env_path) if env_path is not None else config.ENV_FILE
    ensure_env_file(destination, example_path)

    updates = {
        "AI_BASE_URL": _single_line(base_url, "AI_BASE_URL"),
        "AI_MODEL": _single_line(model, "AI_MODEL"),
    }
    if api_key is not None:
        updates["AI_API_KEY"] = _single_line(api_key, "AI_API_KEY")

    original = destination.read_text(encoding="utf-8")
    rendered = _replace_assignments(original, updates)
    destination.write_text(rendered, encoding="utf-8", newline="")


def _replace_assignments(contents: str, updates: Mapping[str, str]) -> str:
    """Replace active dotenv assignments and append keys that are absent."""
    lines = contents.splitlines(keepends=True)
    seen: set[str] = set()
    patterns = {
        key: re.compile(
            rf"^(?P<prefix>[ \t]*(?:export[ \t]+)?){re.escape(key)}[ \t]*=.*?"
            rf"(?P<newline>\r?\n)?$"
        )
        for key in updates
    }

    for index, line in enumerate(lines):
        for key, pattern in patterns.items():
            match = pattern.match(line)
            if not match:
                continue
            newline = match.group("newline") or ""
            lines[index] = f"{match.group('prefix')}{key}={updates[key]}{newline}"
            seen.add(key)
            break

    missing = [key for key in updates if key not in seen]
    if missing:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.extend(f"{key}={updates[key]}\n" for key in missing)

    return "".join(lines)


def _single_line(value: str, name: str) -> str:
    """Reject dotenv line injection while keeping ordinary provider values."""
    value = value.strip()
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be a single line.")
    return value
