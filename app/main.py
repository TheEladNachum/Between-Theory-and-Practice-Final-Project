"""HTTP layer: static files, config, examples, and the streaming analysis route.

The analysis endpoint streams Server-Sent Events rather than returning one
large JSON body. A full run is six model calls and can take a minute or more;
streaming each stage as it lands means the interface can show real progress
instead of a spinner, and a stage that fails is reported immediately rather
than at the end.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.ai.client import ClaudeClient, ModelError
from app.config import EXAMPLES_DIR, STATIC_DIR, get_settings
from app.schemas import IncidentInput
from app.services import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("incidentiq")

app = FastAPI(
    title="IncidentIQ",
    description="AI-assisted incident response and root-cause analysis.",
    version=__version__,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/api/config")
def config() -> Dict[str, Any]:
    """What the frontend needs to know at startup.

    Deliberately does not return the API key, or any prefix of it.
    """
    settings = get_settings()
    return {
        "configured": settings.is_configured,
        "model": settings.anthropic_model,
        "effort": settings.effort,
        "version": __version__,
    }


# --------------------------------------------------------------------------- #
# Example incidents
# --------------------------------------------------------------------------- #


@app.get("/api/examples")
def list_examples() -> Dict[str, List[Dict[str, str]]]:
    if not EXAMPLES_DIR.is_dir():
        return {"examples": []}

    examples = []
    for path in sorted(EXAMPLES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("skipping unreadable example: %s", path.name)
            continue
        examples.append({"id": path.stem, "name": data.get("title", path.stem)})
    return {"examples": examples}


@app.get("/api/examples/{example_id}")
def get_example(example_id: str) -> Dict[str, Any]:
    # The id comes from the URL, so it is untrusted; resolve it and confirm the
    # result is still inside the examples directory before reading anything.
    candidate = (EXAMPLES_DIR / f"{example_id}.json").resolve()
    if not candidate.is_relative_to(EXAMPLES_DIR.resolve()) or not candidate.is_file():
        raise HTTPException(status_code=404, detail="No such example.")

    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Example is unreadable: {exc}") from exc


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def _sse(event: Dict[str, Any]) -> str:
    """Encode one event as an SSE frame."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/analyse")
def analyse(incident: IncidentInput) -> StreamingResponse:
    settings = get_settings()

    if not settings.is_configured:
        raise HTTPException(
            status_code=503,
            detail="No ANTHROPIC_API_KEY configured. Copy .env.example to .env, add "
                   "your key, and restart the server.",
        )
    if incident.is_empty():
        raise HTTPException(
            status_code=400,
            detail="No evidence provided. Add a description, logs, or any other input.",
        )

    def stream() -> Iterator[str]:
        try:
            client = ClaudeClient(settings)
        except ModelError as exc:
            yield _sse({"type": "error", "message": str(exc)})
            return

        log.info("analysing %r", incident.title)
        try:
            for event in pipeline.run(client, incident):
                yield _sse(event)
        except Exception as exc:  # noqa: BLE001 - the stream must not die silently
            log.exception("analysis failed")
            yield _sse({"type": "error", "message": f"Analysis failed: {exc}"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Stops nginx and friends from buffering the stream into one lump.
            "X-Accel-Buffering": "no",
        },
    )
