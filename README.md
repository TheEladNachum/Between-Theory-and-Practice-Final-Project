# IncidentIQ

An AI-powered incident response and root-cause analysis tool.

IncidentIQ takes the messy evidence a production incident actually produces -
logs, stack traces, monitoring alerts, deployment notes, support tickets - and
turns it into a structured investigation: a summary, a reconstructed timeline,
several competing root-cause hypotheses with the evidence for **and against**
each one, a reasoning-risks section that flags cognitive biases, concrete next
debugging steps, and a draft postmortem.

The tool deliberately **never tells you the answer**. It separates **facts**
from **assumptions** from **hypotheses** from **actions**, attaches a confidence
level to every hypothesis, and names the test that would settle it. Then it
checks its own citations against your input and tells you which ones it could
not find.

---

## Quick start

### Windows

Double-click **`run.bat`**.

On first run it creates a virtual environment, installs the dependencies,
creates the local `.env` file from the safe template, starts the server, and
opens the browser. The project opens even when no API key is configured.

### macOS / Linux

```bash
chmod +x run.sh   # first time only
./run.sh
```

The server and browser start even when no API key is configured.

### Manual setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

python -m uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>.

### The API key

IncidentIQ works with any OpenAI-compatible provider. The default settings use
**Google Gemini**, which has a free tier - get a free key at
<https://aistudio.google.com/apikey>. In the running app, click **Edit AI
settings**, paste the key, and choose **Save & test connection**.

The same panel contains presets for Groq, OpenRouter, a local Ollama model,
OpenAI, and Anthropic, plus a custom endpoint option. The saved key is
write-only: it is written to `.env`, but the backend never returns it to the
browser. `.env` is git-ignored and must never be committed.

The connection indicator is deliberately stricter than a "key loaded" badge:

- **Red** - no key is configured, or the provider rejected the connection.
- **Orange** - settings exist but are unverified, or a check is in progress.
- **Green** - the configured provider accepted a real minimal request.

---

## Trying it out

Pick **Load example…** in the top right of the input panel. Three incidents are
included, each containing deliberate reasoning traps:

| Example | The trap it sets |
| --- | --- |
| **Checkout failures after v2.4.1** | The deploy is the obvious suspect. The errors start 14 minutes *before* it, and the rollback does not fix anything. |
| **Course registration slow at peak** | Looks like a load problem. It is an unindexed 2.8M-row table, and the shared Redis instance is a second, separate issue. |
| **Appointment booking 500s** | The helpdesk has already concluded "load related". Exactly one node out of four fails, and CPU never exceeds 35%. |

Then click **Analyse incident**. The six stages report progress as they land.

---

## What it does

| Stage | Output |
| --- | --- |
| **Summary** | Prose summary, plus facts (each quoting the evidence) and assumptions (each with how to verify it) |
| **Timeline** | Ordered events, with anything *deduced* rather than read from the data visibly marked as inferred |
| **Hypotheses** | Three to five genuinely competing causes, each with evidence for and against, a confidence level with the reason for it, and a test that could come out either way |
| **Reasoning risks** | Which of the eight briefed biases this investigation is exposed to, and where specifically |
| **Actions** | Prioritised, checkable next steps tied to evidence - plus the questions the data cannot answer |
| **Postmortem** | A complete draft incident report, readable by a manager |

Everything exports to a single Markdown file.

### Things it does that most AI tools do not

- **It checks its own quotes.** Every citation is verified against the input it
  named. Quotes that cannot be found are shown as suspected hallucinations,
  both in the Reasoning risks tab and inline where they were used.
- **It flags its own confirmation bias.** A hypothesis with no counter-evidence
  gets a warning label rather than looking like a strong result.
- **It cannot invent a bias.** The eight biases come from the brief, live in
  code as a closed vocabulary, and anything outside that set is discarded and
  reported.
- **It degrades instead of failing.** If one stage fails, the others still run
  and you are told which one broke and why.

---

## Configuration

AI provider settings can be changed from the browser. Advanced and server
settings remain in `.env`; see `.env.example` for the annotated version. A
browser save updates only `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL`, preserves
the rest of the file, and becomes active immediately without a restart.

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_BASE_URL` | Gemini's OpenAI-compatible endpoint | The chat endpoint to call. |
| `AI_API_KEY` | *(none)* | **Required.** Your key for that endpoint. |
| `AI_MODEL` | `gemini-2.5-flash` | Which model to use. |
| `MAX_OUTPUT_TOKENS` | `16000` | Output cap per stage. |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | Where the server listens. |
| `LOG_PROMPTS` | `false` | Print every prompt to the console before sending. |

---

## Project structure

```
static/            Browser UI - no build step, ES modules
  js/components/   One render function per result tab
  js/settings.js   Write-only AI setup and live connection status
app/
  main.py          HTTP routes and the streaming analysis endpoint
  config.py        All configuration
  envfile.py       Comment-preserving local .env updates
  schemas.py       The data model: Fact / Assumption / Hypothesis / Action
  ai/              Talks to any OpenAI-compatible provider
    prompts.py     Every prompt, in one place
    client.py      Structured output, with a plain-JSON fallback
    connection.py  Minimal real provider connection check
    parsing.py     Pydantic model -> JSON schema (and prompt hint), and back
  core/
    biases.py      The eight biases from the brief, as data
    evidence.py    Citation verification
  services/        One module per stage, plus pipeline.py
examples/          Three realistic incident datasets
tests/             69 tests - no API key needed
docs/              Prompt documentation and the final reflective report
tools/             Reproducible reflective-report DOCX builder
```

---

## Tests

```bash
.venv\Scripts\python.exe -m pytest      # Windows
.venv/bin/python -m pytest              # macOS / Linux
```

69 tests, none of which call a live provider or need a key. They cover the
citation checker (the component the tool's credibility rests on), schema
generation, the HTTP layer, safe `.env` updates, mocked connection validation,
and the pipeline's behaviour when stages fail.

---

## Documentation

- **[docs/PROMPTS.md](docs/PROMPTS.md)** - every prompt, why it is worded that
  way, and the table of prompt iterations that did not work.
- **[docs/REFLECTIVE_REPORT.md](docs/REFLECTIVE_REPORT.md)** - the completed
  first-person reflective report.
- **[docs/REFLECTIVE_REPORT.docx](docs/REFLECTIVE_REPORT.docx)** - the formatted
  10-page Word submission generated from the Markdown source.

---

## Known limitations

- **Nothing is redacted before being sent.** Real logs contain personal data and
  secrets. This tool would need redaction before any production use.
- **Input is limited by the context window.** There is no chunking or retrieval,
  so very large log files must be trimmed by hand.
- **Investigations are not saved.** A refresh loses the result; export first.
- **Accuracy is not measured.** The examples have no ground truth, so the
  hypotheses cannot be scored. This is discussed in the reflective report.

---

## Licence

Coursework submission for *Computer Science: Critical Thinking, Problem Solving
and 21st-Century Skills*. Not licensed for reuse.
