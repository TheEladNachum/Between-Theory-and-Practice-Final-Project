# IncidentIQ

An AI-powered incident response and root-cause analysis tool.

IncidentIQ takes the messy evidence produced by a production incident - logs,
error traces, monitoring alerts, deployment notes, user complaints - and turns
it into a structured investigation: a summary, a timeline, several competing
root-cause hypotheses with evidence for and against each one, a reasoning-risks
section that flags cognitive biases, concrete next debugging steps, and a draft
postmortem.

The tool deliberately **does not** try to tell you the answer. It separates
**facts** from **assumptions** from **hypotheses** from **actions**, and it
labels how confident it is and why. The point is to support human judgement
under uncertainty, not to replace it.

## Project status

Scaffolding. See the commit history for how the tool was built up.

## Requirements

- Python 3.10 or newer
- An Anthropic API key

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

Then copy `.env.example` to `.env` and paste your API key into it:

```
ANTHROPIC_API_KEY=sk-ant-...
```

`.env` is git-ignored and must never be committed.

## Configuration

All configuration lives in `.env`. See `.env.example` for the full list of
options and what each one does.

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | *(none)* | Required. Your API key. |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Which Claude model to use. |
| `ANTHROPIC_EFFORT` | `high` | Reasoning depth vs. cost. |
| `MAX_OUTPUT_TOKENS` | `16000` | Output cap per analysis stage. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Where the web server listens. |
| `LOG_PROMPTS` | `false` | Print every prompt before sending it. |

## Licence

Coursework submission. Not licensed for reuse.
