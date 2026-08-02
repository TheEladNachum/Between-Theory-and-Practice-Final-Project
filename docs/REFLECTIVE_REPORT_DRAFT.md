# IncidentIQ — reflective report

> This is a working draft in the first person. Edit it into your own voice.
> A few spots marked «like this» are for observations only you can supply,
> from running the tool yourself. Everything else describes the project as it
> actually is.

---

## 1. Overview and purpose

I built IncidentIQ to help a software team investigate a production incident
without letting the AI decide the answer for them. It takes the raw material an
incident produces — logs, stack traces, monitoring alerts, deployment notes,
support tickets — and produces a structured investigation: a summary, a
reconstructed timeline, several competing root-cause hypotheses with the
evidence for and against each one, a reasoning-risks section, prioritised next
steps, and a draft postmortem.

My goal from the start was a tool that stays honest about what it does not know.
A production incident is the clearest everyday case of reasoning under
uncertainty: the logs are incomplete, the loudest error is often a symptom
rather than a cause, and the first plausible explanation is frequently wrong. A
tool that answers confidently in that situation is not helping — it adds a new
way to be wrong, because a fluent answer is hard to argue with.

Three commitments followed from that, and I let them drive every part of the
build:

1. Facts, assumptions, hypotheses and actions are kept apart — in the data
   model, in the prompts, and in the interface.
2. Every factual claim quotes the evidence it came from, and every quote is
   checked against the input automatically. Quotes that cannot be found are
   shown as suspected hallucinations.
3. Nothing is presented as the root cause. Hypotheses carry a confidence level,
   the evidence for and against, and a test that would settle the question.

---

## 2. System architecture

A Python backend serves a browser frontend, with a hard separation between the
layer that talks to the AI and everything else.

```
static/                     Browser UI (no build step, ES modules)
  js/main.js                Wiring only
  js/api.js                 Network calls, streaming
  js/state.js               Observable store
  js/components/            One render function per result tab

app/
  main.py                   HTTP routes, static files, streaming endpoint
  config.py                 All configuration, read from .env
  schemas.py                The data model — Fact/Assumption/Hypothesis/Action
  ai/
    client.py               The only file that talks to the AI provider
    prompts.py              Every prompt, in one place
    parsing.py              Pydantic model -> JSON schema (and prompt hint)
  core/
    biases.py               The eight biases the tool targets, as data
    evidence.py             Citation verification
  services/
    summary/timeline/hypotheses/reasoning_risks/actions/postmortem.py
    pipeline.py             Sequences the stages, assembles the result

examples/                   Three realistic incident datasets
tests/                      61 tests, no API key required
```

I kept the dependency direction one-way on purpose: `services` depend on `ai`
and `core`; `core` depends on nothing but `schemas`. Only `app/ai/client.py`
knows how to reach the AI provider. That isolation is a design decision I made
early, and section 5 is about how it paid off.

### The analysis pipeline

Six stages run in sequence, each seeing the results of the previous ones:
summary (facts + assumptions), timeline, hypotheses, reasoning risks, actions,
postmortem.

Two decisions in the pipeline are ones I would defend in a viva.

A failed stage does not abort the run. If the hypothesis stage fails, the
summary and timeline are still worth having, and the interface says which stage
failed and why. A tool that throws away four good stages because the fifth
failed would be useless during a real incident.

Citation checking happens once, at the end, over everything. Every quote from
every stage is checked against the input section it named, and the failures are
surfaced in the interface rather than written to a log nobody reads.

---

## 3. Technologies used

| Area | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.10+, FastAPI, Uvicorn | Async streaming endpoint and request validation from type hints, with little boilerplate |
| Validation | Pydantic v2 | The same models generate the JSON schema sent to the provider and validate what comes back |
| AI transport | The OpenAI SDK, used as a generic client for any OpenAI-compatible endpoint | See below — this is a deliberate choice, not a choice to use OpenAI |
| Frontend | Vanilla ES modules, CSS custom properties | No build step, so the tool runs from a single launcher on any machine |
| Streaming | Server-Sent Events from server to browser | Six calls take a while; per-stage progress is worth the small complexity |
| Tests | pytest | 61 tests, none of which need a key |
| Config | pydantic-settings + `.env` | Secrets never touch the repository |

**On the AI transport.** IncidentIQ does not depend on any single AI vendor. It
talks to any endpoint that speaks the OpenAI chat protocol, and the endpoint,
key and model are chosen entirely in `.env` (`AI_BASE_URL`, `AI_API_KEY`,
`AI_MODEL`). The OpenAI SDK is used only because it is a convenient, well-tested
client for that wire format. In practice I run it against Google Gemini (which
has a free tier); the same code runs unchanged against Groq, OpenRouter, a local
Ollama model, or OpenAI, by uncommenting a block in `.env`.

**Why no frontend framework.** The interface has one data source and six render
functions. A framework would have added a build step and a dependency tree to a
project whose main practical risk was that it would not run on someone else's
machine. My `state.js` store is about forty lines and does the one thing a
framework would have been brought in for.

---

## 4. How I used AI

Full detail is in [`PROMPTS.md`](PROMPTS.md). In summary:

**AI is the analysis engine.** All six stages are model calls. The code around
them does the work I decided the model should not be trusted with on its own:
enforcing the output shape, verifying citations, validating bias ids, and
ranking hypotheses.

**Structured output, not free-form.** Each stage asks for a JSON object matching
a schema I derive from the Pydantic model it must return. This removes a class
of parsing bugs, but the reason I insisted on it is deeper: it removes the
temptation to accept a well-written prose answer that has quietly blurred a
guess into a fact. The shape is the discipline. Because providers differ in
whether they can enforce a formal schema, the client first asks for the
provider's `json_schema` response format and, if that is rejected, retries once
in plain-JSON mode with the schema described in the prompt — either way the
output is validated before I trust it.

**A closed vocabulary for biases.** The eight biases live in `app/core/biases.py`
as data. The bias-detector prompt is generated from that list, and anything the
model returns outside it is discarded in code. This is the pattern I would reuse
anywhere: give the model a fixed set of labels, then verify in code that it
stayed inside the set rather than hoping it did.

**AI while building.** I also used AI as a coding assistant while building the
project and while generating the synthetic incident data. I treated its
suggestions the same way the tool treats its own output — as proposals to check,
not answers to accept. Section 5 is the clearest example of that.

> «Add one or two concrete moments from your own building: a place where you
> compared two prompt wordings and got different behaviour, or where you asked
> the model to argue against its own conclusion and judged whether the objection
> was real. Quote what you actually saw.»

---

## 5. Critical evaluation: making the tool provider-agnostic

The change I am most willing to defend is one I made to my own earlier design.

From the beginning I had kept everything that talks to the model behind a single
boundary — one function, `complete_structured(...)`, in `app/ai/client.py`, with
the six stages calling it and knowing nothing about the provider underneath. I
did that deliberately, because I expected the AI layer to be the part most likely
to change, and I wanted that change to be containable.

When I had a working version, I stopped and evaluated it critically rather than
moving on. The thing I judged to be wrong was not a bug — the tool worked. It was
that the AI layer was tied to a single paid vendor. I asked myself why the one
part I had deliberately isolated was still coupled to one SDK, and what that cost:

- **Access.** Anyone wanting to run the tool needed a paid key from one specific
  company. That is a poor property for a tool meant to be picked up and run.
- **Comparison.** A core idea of the whole project is not trusting one source. A
  tool locked to one model cannot be pointed at a second model to see where they
  disagree — which is one of the strongest ways to expose uncertainty.
- **Modularity in name only.** I had told myself the AI layer was swappable, but
  "swappable in principle" is not the same as swappable. I had not actually
  proven the boundary was clean.

Having identified the fault, I specified the fix rather than reaching for the
biggest possible rewrite. The design I chose was a single generic client
speaking the OpenAI-compatible chat protocol, with the provider selected only in
`.env`. I preferred this to writing a separate class per vendor: it is *less*
code, not more, and it turns "switch provider" into editing three lines of
configuration. Because different providers accept different subsets of JSON
Schema, I added exactly one fallback — formal schema first, plain-JSON-with-hint
second — and stopped there rather than building an elaborate multi-stage
negotiation the project does not need.

I also made a deliberate subtraction. My earlier version used two features that
were specific to one vendor's API: prompt caching (reusing an identical prefix
across the six calls) and adaptive thinking with an effort control. Going generic
meant dropping both, because they do not exist across providers. I decided this
was the right trade: portability across any provider, including free and local
ones, is worth more to this tool than a per-call optimisation that only one
vendor offered. Keeping them would have re-coupled the tool to the thing I was
trying to decouple from.

The result is the clean version of the boundary I had claimed to have all along.
The six stages did not change. The prompts did not change by a single character —
which is itself evidence that they were written about evidence and reasoning, not
about a vendor's features. Only `app/ai/client.py` and the configuration changed.
That is the property I wanted the isolation to give me, and evaluating my own
working code critically — instead of declaring it done — is what surfaced it.

---

## 6. Examples of useful AI output

The `checkout-v241` example is the best one to run, because it is built to punish
the obvious answer: the connection-pool timeouts in the logs begin at 08:58, but
the deploy everyone blames is at 09:12, and the rollback does not reduce the
error rate.

> «Run that example and record two or three genuinely useful results — for
> instance, whether the tool noticed the errors predate the deploy, whether any
> hypothesis connected the raised reporting-worker pool size to the exhaustion,
> and whether it treated the ineffective rollback as evidence against the deploy
> hypothesis. Quote the actual output rather than describing it.»

---

## 7. Examples of incorrect, misleading or overconfident output

I built the tool so its own failures are easy to find rather than hidden.

- The **Reasoning risks** tab lists any citation whose quoted text was not found
  in the evidence. Each one is a hallucination the tool caught on its own output.
- A **hypothesis with an empty "evidence against" column** is flagged in the
  interface — a prompt to check whether counter-evidence was genuinely absent or
  simply never sought.
- The **inferred** markers on the timeline can be checked by hand against the
  evidence.
- Running the **same incident twice** and comparing the hypothesis rankings shows
  how stable, or unstable, the output is.

> «Give two or three concrete failures you actually found, with the output
> quoted: what the model claimed, what the evidence really said, how you noticed,
> and whether the tool's own checks caught it or you did. A failure only you
> caught is the more interesting one, because it shows the limits of the
> automatic checks.»

---

## 8. Problems encountered and how I solved them

| Problem | How I solved it |
| --- | --- |
| The model invented source names, so every citation failed verification | The evidence block prints the exact list of valid `source` keys, and each section is delimited with its key |
| The model filled gaps with plausible invented details (pool sizes, timestamps) | An explicit closed-world statement in the prompt, plus a list of which inputs were *not* provided |
| Every hypothesis blamed the most recent deploy | The hypothesis prompt requires at least one hypothesis unrelated to the recent change, and one considering ordinary operational causes, and demands a mechanism rather than an ordering |
| The model invented weak counter-evidence to look balanced | The prompt permits an empty `contradicting_evidence` list *provided* the absence is explained; the interface flags it |
| The model reported biases outside the tool's catalogue | The catalogue is injected as a closed vocabulary and validated in code; anything else is discarded and reported |
| Free-form JSON failed in a new way each run | Structured output with a schema generated from the Pydantic model, plus a single plain-JSON fallback for providers that cannot enforce it |
| One failing stage lost the whole investigation | The pipeline records the failure, warns the user, and continues |
| The tool was locked to one paid vendor | Rebuilt the AI layer as a provider-agnostic OpenAI-compatible client (section 5) |

> «Add the problems you hit that are not in this table — setting up the
> environment, interpreting an API error, or a moment where an AI coding
> suggestion was wrong and you had to work the fix out yourself. That last kind
> is worth including, because it shows where you did not take the AI's word.»

---

## 9. Cognitive biases and fallacies

The tool works with the eight biases defined in `app/core/biases.py` —
confirmation, anchoring, automation, post hoc, availability, overconfidence,
hindsight and base-rate neglect. These are the biases that actually threaten an
incident investigation, which is why the catalogue is limited to them rather than
to a general list of every named bias. The four that showed up most clearly in
the tool's own behaviour:

**Post hoc fallacy.** The most persistent one. In the `checkout-v241` example the
natural read is "deploy at 09:12, errors after, therefore the deploy" — and the
evidence contradicts it twice, because the timeouts begin before the deploy and
the rollback does not help. I addressed it by requiring a *mechanism* in the
prompt, not just an ordering.

**Confirmation bias.** A hypothesis with a long list of supporting evidence and
an empty "against" list is its visual signature. I chose to make it visible
rather than only discourage it: the two columns sit side by side, and an empty
"against" column is labelled.

**Automation bias.** The uncomfortable one, because it is about the user, not the
model. Output that is well-formatted and cites its sources *feels* verified. The
citation checker exists precisely because that feeling is not evidence, and the
tool is asked to audit its own confident-but-thin claims in the reasoning-risks
stage.

**Anchoring bias.** The first or loudest error tends to dominate. In
`checkout-v241` the `orders_daily_rollup` error is loud, from a different service,
and irrelevant; in `appointment-booking-500s` the helpdesk note already asserts
"suspect load related" while the evidence shows one node failing and CPU under
35%.

> «For each bias, add the part about your own thinking: where it appeared in how
> *you* read an incident, how you noticed it, and what you did about it. If you
> found yourself trusting the tool's output more readily as the project went on,
> that is automation bias observed in yourself, and it is worth writing down
> honestly.»
>
> The course material on cognitive biases (the general list handed out) is a
> reasonable source to cite here if you want to bring in biases beyond the eight,
> such as groupthink or the fundamental attribution error, when discussing your
> own reasoning — though I kept the tool's catalogue to the eight that fit
> incident analysis.

---

## 10. Ethical and professional considerations

**Over-trust.** The central risk. Fluent output invites acceptance. What I built
in against it: no root cause is ever declared, confidence levels are mandatory,
citations are checked, and hypotheses are competing candidates. None of this
removes the risk — it only keeps the seams visible so a person can see where to
push.

**Data leaving the organisation.** Production logs routinely contain personal
data, session tokens, internal hostnames and keys. The tool sends whatever is
pasted into it to a third-party endpoint. A real deployment would need redaction
before transmission and an explicit policy about which systems may be analysed
this way. The current version redacts nothing, and I consider that a genuine
limitation rather than an oversight. Making the tool provider-agnostic gives one
partial answer to this: it can be pointed at a local model (Ollama), so the
evidence never leaves the machine at all.

**Showing uncertainty to users.** I treated this as an interface problem, not
just a prompt problem. Confidence is a label on every hypothesis; inferred
timeline events look different from observed ones; unverified citations get their
own styling; an unchallenged hypothesis is flagged. The uncertainty is shown
where the claim is, not buried in a disclaimer.

**Responsibility for harmful actions.** If the tool recommends restarting a
database and that loses data, responsibility rests with the engineer who ran the
command — which is why every action names a specific, checkable step rather than
a vague instruction, and why the tool never presents itself as having decided.

**Secrets.** `.env` is git-ignored, `.env.example` ships with an empty key, and
the `/api/config` endpoint returns no part of the key. There is a test that
asserts the key never appears in that payload.

---

## 11. Future improvements

- **Redaction before transmission** — the most important gap. Logs should be
  scanned for tokens, emails and internal hostnames before anything is sent.
- **Retrieval over large logs** — everything currently goes into the context
  window, which caps the input size. Chunking with retrieval would let the tool
  work on real log volumes.
- **Model comparison** — now that the provider is configurable, running two
  models on the same incident and showing where they disagree is a natural next
  step, and would surface uncertainty better than any single model's
  self-reported confidence.
- **Persistence** — investigations are not saved; a refresh loses them.
- **Measuring accuracy** — the examples have no ground truth, so the hypotheses
  cannot be scored. A proper evaluation would need incidents with known causes
  and a measure of how often the true cause appears in the top three.

---

## Appendix A — running the tool

See [`README.md`](../README.md). In short: `run.bat` (Windows) or `./run.sh`
(macOS/Linux), then paste an API key into `.env` when prompted. A free Google
Gemini key works with the default settings.

## Appendix B — prompts

See [`PROMPTS.md`](PROMPTS.md) for every prompt, the reasoning behind each
instruction, the table of prompt iterations, and the note on why the tool stays
portable across providers.
