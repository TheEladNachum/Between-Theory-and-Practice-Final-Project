"""Tests for the comment-preserving, write-only .env updater."""

from __future__ import annotations

from app.envfile import update_ai_settings


def test_update_creates_from_template_and_preserves_other_lines(tmp_path):
    template = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    template.write_text(
        "# Keep this explanation\n"
        "AI_BASE_URL=https://old.example/v1\n"
        "AI_API_KEY=old-secret\n"
        "AI_MODEL=old-model\n"
        "# AI_MODEL=commented-provider-model\n"
        "MAX_OUTPUT_TOKENS=16000\n",
        encoding="utf-8",
    )

    result = update_ai_settings(
        api_key="new-secret",
        model="new-model",
        base_url="https://new.example/v1",
        env_path=env_file,
        example_path=template,
    )

    contents = env_file.read_text(encoding="utf-8")
    assert result is None
    assert "# Keep this explanation" in contents
    assert "# AI_MODEL=commented-provider-model" in contents
    assert "MAX_OUTPUT_TOKENS=16000" in contents
    assert "AI_BASE_URL=https://new.example/v1" in contents
    assert "AI_API_KEY=new-secret" in contents
    assert "AI_MODEL=new-model" in contents
    assert "old-secret" not in contents


def test_omitted_key_keeps_existing_key_and_missing_fields_are_appended(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# Minimal existing file\nAI_API_KEY=keep-this-secret\nOTHER=value",
        encoding="utf-8",
    )

    update_ai_settings(
        api_key=None,
        model="model-two",
        base_url="http://127.0.0.1:11434/v1",
        env_path=env_file,
        example_path=tmp_path / "missing-example",
    )

    contents = env_file.read_text(encoding="utf-8")
    assert "AI_API_KEY=keep-this-secret" in contents
    assert "OTHER=value" in contents
    assert "AI_BASE_URL=http://127.0.0.1:11434/v1" in contents
    assert "AI_MODEL=model-two" in contents


def test_all_active_duplicates_are_updated_but_commented_examples_are_not(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "AI_MODEL=first\n"
        "# AI_MODEL=example\n"
        "export AI_MODEL=last\n"
        "AI_BASE_URL=https://example.test/v1\n"
        "AI_API_KEY=old\n",
        encoding="utf-8",
    )

    update_ai_settings(
        api_key="new",
        model="replacement",
        base_url="https://example.test/v2",
        env_path=env_file,
    )

    contents = env_file.read_text(encoding="utf-8")
    assert "AI_MODEL=first" not in contents
    assert "export AI_MODEL=last" not in contents
    assert "AI_MODEL=replacement" in contents
    assert "export AI_MODEL=replacement" in contents
    assert "# AI_MODEL=example" in contents
