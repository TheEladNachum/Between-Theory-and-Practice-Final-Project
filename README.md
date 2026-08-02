# IncidentIQ



**Demo video:** [Watch the IncidentIQ demonstration](https://drive.google.com/file/d/1atCCb-iVqRihPl3nfPx1juA51AX_elzq/view?usp=drive_link)



**Run IncidentIQ:** on Windows, double-click `run.bat`; on macOS or Linux, run
`./run.sh`. Wait for the browser to open at [http://127.0.0.1:8000](http://127.0.0.1:8000), click
**Edit AI settings**, paste the supplied Gemini API key, and click **Save \& test
connection**. When **AI connection verified** appears in green, load an example
and click **Analyse incident**. The project opens even without a key, and the
key is saved only in the local, Git-ignored `.env` file.

IncidentIQ is an AI-assisted incident investigation tool that transforms logs,
alerts, traces, and deployment notes into a structured, evidence-based
investigation. It separates facts, assumptions, hypotheses, and actions,
verifies citations, and keeps the final judgement with the human user.

\---

## Quick start

### Windows

1. Extract the project folder, open it, and double-click **`run.bat`**.
2. Wait for the browser to open. IncidentIQ opens even if no API key has been
configured yet.
3. Click **Edit AI settings** at the top of the page.
4. Keep the Google Gemini preset, or select another compatible provider and
model. Paste the API key supplied for the assessment into **API key**.
5. Click **Save \& test connection**. Continue when the status turns green and
says **AI connection verified**.
6. Load an example or enter incident evidence, then click **Analyse incident**.

On the first run, the launcher also creates a virtual environment, installs the
dependencies, and creates the local `.env` file from the safe template. Keep
the command window open while using the project.

**Model note:** The default model is `gemini-3-flash-preview`. If the provider reports that the model is unavailable or its quota has been exhausted, open \*\*Edit AI settings\*\* and copy one of these model IDs into the \*\*Model\*\* field:

* `gemini-3.1-flash-lite` — recommended first alternative; verified during the final project test.
* `gemini-3.5-flash-lite` — additional stable alternative.

Enter the model ID exactly as written, using lowercase letters and hyphens. Do not change the API base URL or API key. Click \*\*Save \& test connection\*\* and continue only after the green **AI connection verified** message appears.

### macOS / Linux

```bash
chmod +x run.sh   # first time only
./run.sh
```

The server and browser start even when no API key is configured. Then follow
steps 3-6 in the Windows instructions above.

### Manual setup

```bash
python -m venv .venv
.venv\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\Scripts\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

python -m uvicorn app.main:app --reload
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### The API key

IncidentIQ works with any OpenAI-compatible provider. The default settings use
**Google Gemini**, which has a free tier - get a free key at
[https://aistudio.google.com/apikey](https://aistudio.google.com/apikey). In the running app, click **Edit AI
settings**, paste the key into the **API key** field, and choose **Save \& test
connection**. For assessment, the instructor should use the API key supplied
separately by the project author; the key is intentionally not included in the
submitted project folder.

The same panel contains presets for Groq, OpenRouter, a local Ollama model,
OpenAI, and Anthropic, plus a custom endpoint option. The saved key is
write-only: it travels once from the form to the local backend and is written
to the local `.env` file, but the backend never returns it to the browser.
`.env` is git-ignored, is not included in the submission, and must never be
committed.

The connection indicator is deliberately stricter than a "key loaded" badge:

* **Red** - no key is configured, or the provider rejected the connection.
* **Orange** - settings exist but are unverified, or a check is in progress.
* **Green** - the configured provider accepted a real minimal request.

> \\\*\\\*Model note:\\\*\\\* The default model is `gemini-3-flash-preview`. If the
> provider reports that the model is unavailable or its quota has been
> exhausted, open \\\*\\\*Edit AI settings\\\*\\\* and copy one of these model IDs into the
> \\\*\\\*Model\\\*\\\* field:
>
> \\\* `gemini-3.1-flash-lite` - recommended first alternative; verified during
>   the final project test.
> \\\* `gemini-3.5-flash-lite` - additional stable alternative.
>
> Enter the model ID exactly as written, using lowercase letters and hyphens.
> Do not change the API base URL or API key. Click \\\*\\\*Save \\\& test connection\\\*\\\*
> and continue only after the green \\\*\\\*AI connection verified\\\*\\\* message appears.

\---

## Trying it out

Pick **Load example…** in the top right of the input panel. Three incidents are
included, each containing deliberate reasoning traps:

|Example|The trap it sets|
|-|-|
|**Checkout failures after v2.4.1**|The deploy is the obvious suspect. The errors start 14 minutes *before* it, and the rollback does not fix anything.|
|**Course registration slow at peak**|Looks like a load problem. It is an unindexed 2.8M-row table, and the shared Redis instance is a second, separate issue.|
|**Appointment booking 500s**|The helpdesk has already concluded "load related". Exactly one node out of four fails, and CPU never exceeds 35%.|

Then click **Analyse incident**. The six stages report progress as they land.

\---

## What it does

|Stage|Output|
|-|-|
|**Summary**|Prose summary, plus facts (each quoting the evidence) and assumptions (each with how to verify it)|
|**Timeline**|Ordered events, with anything *deduced* rather than read from the data visibly marked as inferred|
|**Hypotheses**|Three to five genuinely competing causes, each with evidence for and against, a confidence level with the reason for it, and a test that could come out either way|
|**Reasoning risks**|Which of the eight briefed biases this investigation is exposed to, and where specifically|
|**Actions**|Prioritised, checkable next steps tied to evidence - plus the questions the data cannot answer|
|**Postmortem**|A complete draft incident report, readable by a manager|

Everything exports to a single Markdown file.

### Things it does that most AI tools do not

* **It checks its own quotes.** Every citation is verified against the input it
named. Quotes that cannot be found are shown as suspected hallucinations,
both in the Reasoning risks tab and inline where they were used.
* **It flags its own confirmation bias.** A hypothesis with no counter-evidence
gets a warning label rather than looking like a strong result.
* **It cannot invent a bias.** The eight biases come from the brief, live in
code as a closed vocabulary, and anything outside that set is discarded and
reported.
* **It degrades instead of failing.** If one stage fails, the others still run
and you are told which one broke and why.

\---

## Configuration

AI provider settings can be changed from the browser. Advanced and server
settings remain in `.env`; see `.env.example` for the annotated version. A
browser save updates only `AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_BASE\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_URL`, `AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_API\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_KEY`, and `AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_MODEL`, preserves
the rest of the file, and becomes active immediately without a restart.

|Variable|Default|Purpose|
|-|-|-|
|`AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_BASE\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_URL`|Gemini's OpenAI-compatible endpoint|The chat endpoint to call.|
|`AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_API\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_KEY`|*(none)*|**Required.** Your key for that endpoint.|
|`AI\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_MODEL`|`gemini-3-flash-preview`|Which model to use.|
|`MAX\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_OUTPUT\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_TOKENS`|`16000`|Output cap per stage.|
|`HOST` / `PORT`|`127.0.0.1` / `8000`|Where the server listens.|
|`LOG\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\_PROMPTS`|`false`|Print every prompt to the console before sending.|

\---

## Project structure

```
static/            Browser UI - no build step, ES modules
  js/components/   One render function per result tab
  js/settings.js   Write-only AI setup and live connection status
app/
  main.py          HTTP routes and the streaming analysis endpoint
  config.py        All configuration
  envfile.py       Comment-preserving local .env updates
  portcheck.py     Detects an existing server before the browser is opened
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
tests/             87 tests - no API key needed
docs/              Prompt documentation and the final reflective report
tools/             Reproducible reflective-report DOCX builder
```

\---

## Tests

```bash
.venv\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\Scripts\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\python.exe -m pytest      # Windows
.venv/bin/python -m pytest              # macOS / Linux
```

87 tests, none of which call a live provider or need a key. They cover the
citation checker (the component the tool's credibility rests on), schema
generation, the HTTP layer, safe `.env` updates, mocked connection validation,
reasoning safeguards, static-file cache headers, launcher/port preflight, and
the pipeline's behaviour when stages fail.

\---

## Documentation

* [**docs/PROMPTS.md**](docs/PROMPTS.md) - every prompt, why it is worded that
way, and the table of prompt iterations that did not work.
* [**docs/REFLECTIVE\_REPORT.md**](docs/REFLECTIVE_REPORT.md) - the completed
first-person reflective report, including the Commit 12 human-review
addendum.
* [**docs/REFLECTIVE\_REPORT.docx**](docs/REFLECTIVE_REPORT.docx) - the formatted
Commit 12 report generated from the Markdown source.

\---

## Known limitations

* **Nothing is redacted before being sent.** Real logs contain personal data and
secrets. This tool would need redaction before any production use.
* **Input is limited by the context window.** There is no chunking or retrieval,
so very large log files must be trimmed by hand.
* **Investigations are not saved.** A refresh loses the result; export first.
* **Accuracy is not measured.** The examples have no ground truth, so the
hypotheses cannot be scored. This is discussed in the reflective report.

\---

## Licence

Coursework submission for *Computer Science: Critical Thinking, Problem Solving
and 21st-Century Skills*. Not licensed for reuse.

