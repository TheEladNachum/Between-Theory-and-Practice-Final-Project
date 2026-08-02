# Reflective report - DRAFT

> **How to use this file.**
>
> The sections describing *the system* are written for you and are factually
> accurate about this codebase - check them, edit the wording into your own
> voice, and keep them.
>
> The sections describing *your experience* are marked **▶ WRITE THIS
> YOURSELF**. They cannot be pre-written honestly, because they are about what
> you observed while building and running the tool. The brief is explicitly
> asking for evidence that you tested and challenged the AI. Run the tool on
> the examples, keep notes, and fill those sections in from your own notes.
>
> Delete this box before submitting. Target length is 5-10 pages.

---

## 1. Project overview and purpose

IncidentIQ is a web tool that helps a development, DevOps or SRE team
investigate a production incident. It takes the raw material an incident
actually produces - application logs, stack traces, monitoring alerts,
deployment notes, support tickets - and produces a structured investigation:
a summary, a reconstructed timeline, several competing root-cause hypotheses,
a reasoning-risks section, recommended next steps, and a draft postmortem.

The design goal was not to build something that answers "what broke". It was to
build something that is *useful while remaining honest about what it does not
know*. Production incidents are the textbook case of reasoning under
uncertainty: the logs are incomplete, the loudest error is often a symptom
rather than a cause, and the first plausible explanation is frequently wrong.
A tool that produces a confident answer in that situation is not helping - it
is adding a new failure mode, because a fluent answer is hard to argue with.

Three commitments follow from that, and they shaped every part of the system:

1. **Facts, assumptions, hypotheses and actions are kept apart** - in the data
   model, in the prompts, and in the interface.
2. **Every factual claim must quote the evidence it came from, and every quote
   is checked** against the input automatically. Quotes that cannot be found
   are shown to the user as suspected hallucinations.
3. **Nothing is ever presented as the root cause.** Hypotheses carry a
   confidence level, the evidence for *and against*, and a test that would
   settle the question.

---

## 2. System architecture

### 2.1 Shape

A Python backend serving a browser frontend, with a clear separation between
the layer that talks to the model and everything else.

```
static/                     Browser UI (no build step, ES modules)
  index.html
  css/styles.css
  js/
    main.js                 Wiring only
    api.js                  All network calls, SSE stream parsing
    state.js                Observable store
    dom.js                  DOM helpers
    report.js               Markdown export
    components/             One render function per result tab

app/
  main.py                   HTTP routes, static files, SSE endpoint
  config.py                 All configuration, read from .env
  schemas.py                The data model - Fact/Assumption/Hypothesis/Action
  ai/
    client.py               The only file that imports the Anthropic SDK
    prompts.py              Every prompt, in one place
    parsing.py              Pydantic model -> strict JSON schema, and back
  core/
    biases.py               The eight biases from the brief, as data
    evidence.py             Citation verification
  services/
    summary.py  timeline.py  hypotheses.py
    reasoning_risks.py  actions.py  postmortem.py
    pipeline.py             Sequences the stages, assembles the result

examples/                   Three realistic incident datasets
tests/                      51 tests, no API key required
docs/                       This file and PROMPTS.md
```

The dependency direction is one-way: `services` depend on `ai` and `core`,
`core` depends on nothing but `schemas`. Nothing outside `app/ai/` imports the
Anthropic SDK, so changing model provider would touch one file.

### 2.2 The analysis pipeline

Six stages run in sequence, each seeing the results of the previous ones:

| # | Stage | Produces |
| --- | --- | --- |
| 1 | Summary | Prose summary, facts (cited), assumptions (with how to verify) |
| 2 | Timeline | Ordered events, each marked read-from-evidence or inferred |
| 3 | Hypotheses | 3-5 competing causes, evidence for/against, confidence, a test |
| 4 | Reasoning risks | Biases and fallacies affecting *this* investigation |
| 5 | Actions | Prioritised next steps, plus the open questions |
| 6 | Postmortem | A complete draft incident report in Markdown |

Two decisions here are worth defending in a viva.

**A failed stage does not abort the run.** If the hypothesis stage fails, the
summary and timeline are still worth having. The interface shows which stage
failed and why. A tool that discards four good stages because the fifth failed
is not usable during an actual incident.

**Citation checking happens once, at the end, over everything.** Every quote
produced by every stage is checked against the input section it named. Failures
are attached to the result and surfaced in the interface - not written to a log
nobody reads.

### 2.3 Main features

- Paste or upload evidence across seven input types
- Live per-stage progress (Server-Sent Events, not a spinner)
- Facts and assumptions rendered as visually distinct blocks
- Timeline with inferred events visibly marked
- Hypotheses with side-by-side evidence-for / evidence-against
- Automatic "possible confirmation bias" flag on any hypothesis with no
  counter-evidence
- Automatic hallucination detection on all citations
- Bias detector restricted to the eight biases from the brief, validated in code
- Draft postmortem, and full Markdown export of the whole investigation
- Three example incidents, each containing deliberate reasoning traps
- Light/dark theme, responsive layout
- One-click launcher (`run.bat` / `run.sh`)

---

## 3. Technologies used

| Area | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.10+, FastAPI, Uvicorn | Async streaming endpoint, automatic request validation from type hints, no boilerplate |
| Validation | Pydantic v2 | The same models generate the JSON schema sent to the model *and* validate what comes back |
| AI | Anthropic API, `claude-opus-4-8` | Structured outputs and adaptive thinking; model configurable via `.env` |
| Frontend | Vanilla ES modules, CSS custom properties | No build step - the lecturer runs one file and it works. A framework would add a toolchain without adding capability here |
| Streaming | Server-Sent Events | Six model calls take a while; per-stage feedback is worth the small complexity |
| Tests | pytest | 51 tests, none of which need an API key |
| Config | pydantic-settings + `.env` | Secrets never touch the repository |

**Why no frontend framework.** The UI has one data source and six render
functions. React would have added a build step, a dependency tree, and a
`node_modules` directory to a project whose main risk was that it would not run
on someone else's machine. The `state.js` store is about forty lines and does
the one thing a framework would have been used for.

---

## 4. How AI was used

Full detail is in [`PROMPTS.md`](PROMPTS.md). Summary:

**AI is the analysis engine.** All six stages are model calls. The code around
them does the work the model should not be trusted with: enforcing the output
shape, verifying citations, validating bias ids, and ranking hypotheses.

**Structured outputs, not free-form.** Each stage sends a JSON schema derived
from a Pydantic model. This removes a class of parsing bugs, but the real
benefit is that it removes the temptation to accept a well-written prose answer
that has quietly blurred a guess into a fact. The shape *is* the discipline.

**A closed vocabulary for biases.** The bias catalogue lives in
`app/core/biases.py` as data. The detector prompt is generated from it, and
anything the model returns outside the catalogue is discarded in code. This is
the pattern I would reuse: give the model a fixed set of labels, then verify it
stayed inside the set.

**Prompt caching by construction.** The system prompt and evidence block are
byte-identical across all six stages and are sent first, so the six calls share
one cached prefix instead of re-reading the evidence six times.

**AI was also used while building the project** - generating the synthetic
incident data, drafting code, and reviewing my own reasoning.

> **▶ WRITE THIS YOURSELF**
>
> Describe how *you* used AI while building this. Be specific and concrete:
> - Which tool(s), for what (code, synthetic data, debugging, writing)?
> - One case where AI clearly saved you time. What did you ask, what did it give
>   you, what did you change?
> - One case where you compared two prompts, or two models, and got materially
>   different answers. Show both.
> - One case where you asked the AI to argue against its own conclusion. Did it
>   actually find a real objection, or produce a token one?
> - One case where a small prompt change changed the answer substantially. This
>   is the most interesting evidence you can present - the brief asks for it
>   explicitly.

---

## 5. Examples of useful AI output

> **▶ WRITE THIS YOURSELF**
>
> Run the tool on `examples/checkout-v241.json` and keep the output. Then pick
> two or three genuinely useful results and paste them, with a sentence on why
> each was useful.
>
> Things to look for in that example specifically:
> - The connection-pool timeouts in the logs begin at **08:58**, but the deploy
>   is at **09:12**. Did the tool notice the errors *predate* the deploy?
> - The `reporting-worker` pool size was raised from 5 to 40 the previous day
>   (in `extra`). Did any hypothesis connect that to pool exhaustion?
> - The rollback at 09:34 did **not** reduce the error rate. Did the tool treat
>   that as evidence against the deploy hypothesis?
> - The `orders_daily_rollup` error is from a different service and is a red
>   herring. Did the tool avoid it, or chase it?
>
> Quote the actual output. Do not paraphrase it favourably.

---

## 6. Examples of incorrect, misleading or overconfident AI output

This section is worth more marks than section 5. The brief asks for evidence of
hallucination, overconfidence and unsupported assumptions - and the tool was
built to make them easy to find.

Where to look:

- **The Reasoning risks tab** lists any citation whose quoted text was not found
  in the evidence. Each one is a hallucination the tool caught. Screenshot them.
- **Hypotheses with an empty "evidence against" column** are flagged in the UI.
  Check whether counter-evidence genuinely was absent, or simply not looked for.
- **The `inferred` markers on the timeline.** Check a few by hand. Is anything
  marked as read-from-evidence that was actually deduced?
- **Run the same incident twice.** Compare the hypothesis rankings. Instability
  between identical runs is itself a finding worth reporting.

> **▶ WRITE THIS YOURSELF**
>
> Give at least three concrete failures with the actual output pasted in. For
> each: what the model claimed, what the evidence actually said, how you noticed,
> and what (if anything) in the system caught it.
>
> A failure the *system* caught is a good result for the project. A failure only
> *you* caught is a better finding for the report - it shows the limits of the
> automatic checks.

---

## 7. Problems encountered and how they were solved

The technical problems solved in the codebase:

| Problem | Solution |
| --- | --- |
| The model invented source names, so every citation failed verification | The evidence block prints the exact list of valid `source` keys, and each section is delimited with its key |
| The model filled gaps with plausible invented details (pool sizes, timestamps) | An explicit closed-world statement, plus a list of which inputs were *not* provided |
| Every hypothesis blamed the most recent deploy | The hypothesis prompt requires at least one hypothesis unrelated to the recent change, and one considering ordinary operational causes |
| The model invented weak counter-evidence to look balanced | The prompt permits an empty `contradicting_evidence` list *provided* the absence is explained; the UI flags it |
| The model reported biases that were not in the brief | The catalogue is injected as a closed vocabulary and validated in code; anything else is discarded and reported |
| Free-form JSON output failed in a new way each run | Structured outputs with a schema generated from the Pydantic model by `strict_schema()` |
| Six model calls exceeded a comfortable request timeout | Streaming responses, and SSE so the UI shows per-stage progress |
| One failing stage lost the whole investigation | The pipeline records the failure, warns the user, and continues |

> **▶ WRITE THIS YOURSELF**
>
> Add the problems *you* hit that are not in this table - environment setup, an
> API error you had to interpret, something that took an afternoon. Include at
> least one where the AI's suggested fix was wrong and you had to work it out
> yourself. That is the most credible thing you can put in this section.

---

## 8. Cognitive biases and fallacies encountered

The brief asks for at least three; strong reports discuss five or more. The
eight in the catalogue are defined in `app/core/biases.py`. Below are the four
that showed up most clearly in the tool's own behaviour - discuss these plus
any you noticed in your own reasoning.

**Post hoc fallacy.** The strongest and most persistent failure. Given the
`checkout-v241` example, the natural reading is "deploy at 09:12, errors after,
therefore the deploy". The evidence contradicts it twice: the pool timeouts
begin at 08:58, and the rollback did not reduce the error rate. Early prompt
versions blamed the deploy anyway. The fix was to require a *mechanism*, not an
ordering - and the example was built specifically to punish the shortcut.

**Confirmation bias.** Early hypotheses had long supporting-evidence lists and
empty contradicting-evidence lists. The system now makes this visible rather
than only discouraging it: the two columns sit side by side, and an empty
"against" column gets a warning label.

**Automation bias.** The most uncomfortable one, because it is about the user
rather than the model. The output is well-formatted, professionally worded, and
cites its sources - which makes it *feel* verified. The citation checker exists
precisely because that feeling is not evidence, and the tool is asked to audit
itself for this bias in stage 4.

**Anchoring bias.** The first or loudest error in a log tends to dominate. In
`checkout-v241` the `orders_daily_rollup` error is loud, is from a different
service, and is irrelevant. In `appointment-booking-500s` the helpdesk note
already asserts "suspect load related" - and the evidence flatly contradicts it
(CPU below 35%, one specific node failing).

> **▶ WRITE THIS YOURSELF**
>
> For each bias you discuss, the brief asks four things: **where it appeared,
> how it affected your thinking, how you noticed it, and how you reduced its
> effect.** The four above are written from the system's behaviour - add the
> part about *your own* thinking, which is what is actually being assessed.
>
> Worth considering honestly: did you find yourself accepting the tool's output
> more readily as the project went on? That is automation bias, observed in
> yourself, and reporting it is worth more than any of the above.

---

## 9. Ethical and professional risks

**Over-trust.** The central risk. Fluent output invites acceptance. Mitigations
built in: no root cause is ever declared, confidence levels are mandatory,
citations are checked, and hypotheses are presented as competing candidates.
None of this removes the risk - it only makes the seams visible.

**Data leaving the organisation.** Production logs routinely contain personal
data, session tokens, internal hostnames and API keys. This tool sends whatever
is pasted into it to a third-party API. In a real deployment this needs
redaction before transmission, an explicit data-handling policy, and an
organisational decision about which systems may be analysed this way at all.
The current version does not redact anything, and that is a genuine limitation
rather than an oversight.

**Responsibility for harmful recommendations.** If the tool recommends
restarting a database and that causes data loss, responsibility rests with the
engineer who ran the command - which is why every action names a specific,
checkable step rather than a vague instruction, and why destructive suggestions
should always be reviewed. A tool that recommends actions must not obscure who
is accountable for taking them.

**Automation of judgement.** The subtler risk is not a wrong answer but a
narrowed search. If the tool produces four hypotheses, the investigator is
unlikely to think of a fifth. The open-questions section is a partial
counterweight; it does not solve the problem.

**Secrets in the repository.** `.env` is git-ignored and `.env.example`
contains an empty key. The `/api/config` endpoint deliberately returns no part
of the key, and there is a test asserting that.

> **▶ WRITE THIS YOURSELF**
>
> The brief lists seven ethical questions. Answer the ones this section does not
> already cover - particularly *"how should uncertainty be shown to users?"*,
> where you can argue from concrete interface decisions you can point at.

---

## 10. Division of work

> **▶ WRITE THIS YOURSELF (pairs only)**
>
> If you submitted individually, say so and delete this section.

---

## 11. Future improvements

Honest assessment of what is missing:

- **Redaction before transmission.** The most important gap. Logs should be
  scanned for tokens, emails and internal hostnames before anything is sent.
- **Retrieval over large log files.** Everything currently goes into the
  context window, which caps the practical input size. Chunking with retrieval
  would let the tool work on real log volumes.
- **Interactive follow-up.** Being able to ask "why did you rule that out?"
  against a completed investigation.
- **Persistence.** Investigations are not saved; a refresh loses everything.
- **Role-based output.** The brief's advanced tier suggests separate views for
  engineer, manager and support. The postmortem stage half-does this; a proper
  version would generate distinct summaries.
- **Charts.** Error rates and timing are currently text only.
- **Measuring accuracy.** The largest gap intellectually. There is no ground
  truth for these examples, so the tool's hypotheses cannot be scored. A proper
  evaluation would need incidents with known causes and a measure of how often
  the true cause appears in the top three.
- **Multi-model comparison.** Running two models on the same incident and
  showing where they disagree would surface uncertainty far better than a single
  model's self-reported confidence.

---

## Appendix A - running the tool

See [`README.md`](../README.md). Short version: `run.bat` (Windows) or
`./run.sh` (macOS/Linux), then paste your API key into `.env` when prompted.

## Appendix B - prompts

See [`PROMPTS.md`](PROMPTS.md) for every prompt, the reasoning behind each
instruction, and the table of prompt iterations.
