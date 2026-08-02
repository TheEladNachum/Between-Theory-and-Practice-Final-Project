"""Tests for the HTTP layer and the bias catalogue.

These do not call the model - they cover the routing, validation and guard
behaviour that must hold whether or not an API key is present.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.config as config_module
import app.main as main_module
from app.ai.client import ModelError
from app.config import EXAMPLES_DIR, get_settings
from app.core.biases import BIAS_CATALOGUE, VALID_BIAS_IDS, catalogue_for_prompt, is_known
from app.main import app
from app.schemas import IncidentInput

client = TestClient(app)


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    """Point the cached settings and writer at a disposable dotenv file."""
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"
    initial = (
        "AI_BASE_URL=https://old.example/v1\n"
        "AI_API_KEY=old-test-secret\n"
        "AI_MODEL=old-model\n"
        "MAX_OUTPUT_TOKENS=16000\n"
    )
    example_file.write_text(initial, encoding="utf-8")
    env_file.write_text(initial, encoding="utf-8")
    monkeypatch.setattr(config_module, "ENV_FILE", env_file)
    monkeypatch.setattr(config_module, "ENV_EXAMPLE_FILE", example_file)
    for name in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()


# --- routes -----------------------------------------------------------------


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_config_never_leaks_the_key():
    body = client.get("/api/config").json()
    assert set(body) == {
        "configured", "provider", "model", "base_url", "status", "version"
    }
    # No form of the key, or the field that holds it, may appear in the payload.
    dumped = json.dumps(body).lower()
    assert "ai_api_key" not in dumped
    assert "api_key" not in dumped
    assert "sk-" not in dumped


def test_save_config_refreshes_cache_without_returning_key(isolated_settings):
    # Prime the lru_cache with the old file values before the browser edit.
    assert get_settings().ai_model == "old-model"

    response = client.post(
        "/api/config",
        json={
            "api_key": "new-browser-secret",
            "model": "new-model",
            "base_url": "https://new.example/v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["model"] == "new-model"
    assert body["status"] == "unverified"
    assert "new-browser-secret" not in response.text
    assert "api_key" not in response.text.lower()
    # The endpoint cleared the cache, so no process restart is necessary.
    assert get_settings().ai_api_key == "new-browser-secret"
    assert get_settings().ai_model == "new-model"
    assert "MAX_OUTPUT_TOKENS=16000" in isolated_settings.read_text(encoding="utf-8")


def test_connection_endpoint_reports_mocked_success_without_key(
    isolated_settings, monkeypatch
):
    seen = []

    def fake_check(settings):
        seen.append((settings.provider_name, settings.ai_model))

    monkeypatch.setattr(main_module, "check_connection", fake_check)

    response = client.post("/api/config/test")

    assert response.status_code == 200
    assert response.json()["status"] == "valid"
    assert response.json()["ok"] is True
    assert seen == [("old.example", "old-model")]
    assert "old-test-secret" not in response.text


def test_connection_endpoint_surfaces_mocked_provider_error(
    isolated_settings, monkeypatch
):
    def rejected(_settings):
        raise ModelError("The provider refused the request (403).")

    monkeypatch.setattr(main_module, "check_connection", rejected)

    response = client.post("/api/config/test")

    assert response.status_code == 200
    assert response.json() == {
        "ok": False,
        "status": "invalid",
        "message": "The provider refused the request (403).",
        "provider": "old.example",
        "model": "old-model",
    }


def test_index_is_served():
    assert client.get("/").status_code == 200


def test_examples_are_listed_and_loadable():
    listing = client.get("/api/examples").json()["examples"]
    assert listing, "no example incidents were found"

    for entry in listing:
        body = client.get(f"/api/examples/{entry['id']}")
        assert body.status_code == 200
        # Every example must be a valid IncidentInput with real evidence in it.
        incident = IncidentInput(**body.json())
        assert not incident.is_empty()


def test_unknown_example_is_404():
    assert client.get("/api/examples/does-not-exist").status_code == 404


def test_example_route_rejects_path_traversal():
    for attempt in ("../requirements", "..%2f..%2frequirements", "....//requirements"):
        assert client.get(f"/api/examples/{attempt}").status_code in (404, 400)


def test_analyse_rejects_empty_evidence():
    response = client.post("/api/analyse", json={"title": "nothing here"})
    assert response.status_code in (400, 503)


# --- example data quality ---------------------------------------------------


def test_examples_are_messy_enough_to_be_useful():
    """Each example must exercise several evidence types, not just one blob."""
    for path in EXAMPLES_DIR.glob("*.json"):
        incident = IncidentInput(**json.loads(path.read_text(encoding="utf-8")))
        sources = incident.evidence_sources()
        assert len(sources) >= 4, f"{path.name} has too few evidence types"
        assert incident.title, f"{path.name} has no title"


# --- bias catalogue ---------------------------------------------------------


def test_catalogue_has_the_eight_briefed_biases():
    assert len(BIAS_CATALOGUE) == 8


def test_bias_ids_are_unique():
    assert len(set(VALID_BIAS_IDS)) == len(VALID_BIAS_IDS)


def test_every_bias_is_fully_specified():
    for bias in BIAS_CATALOGUE:
        assert bias.name and bias.how_it_appears and bias.detection_hint and bias.mitigation


def test_prompt_block_lists_every_id():
    block = catalogue_for_prompt()
    for bias_id in VALID_BIAS_IDS:
        assert bias_id in block


def test_is_known_rejects_invented_biases():
    assert is_known("confirmation_bias")
    assert not is_known("recency_bias")
