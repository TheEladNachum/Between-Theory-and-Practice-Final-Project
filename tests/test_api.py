"""Tests for the HTTP layer and the bias catalogue.

These do not call the model - they cover the routing, validation and guard
behaviour that must hold whether or not an API key is present.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import EXAMPLES_DIR
from app.core.biases import BIAS_CATALOGUE, VALID_BIAS_IDS, catalogue_for_prompt, is_known
from app.main import app
from app.schemas import IncidentInput

client = TestClient(app)


# --- routes -----------------------------------------------------------------


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_config_never_leaks_the_key():
    body = client.get("/api/config").json()
    assert set(body) == {"configured", "model", "effort", "version"}
    assert "anthropic_api_key" not in json.dumps(body).lower()
    assert "sk-ant" not in json.dumps(body)


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
