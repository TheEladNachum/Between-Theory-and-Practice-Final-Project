# Prompt documentation

Every prompt the system sends lives in [`app/ai/prompts.py`](../app/ai/prompts.py).
This document explains why each one is worded the way it is, and records the
earlier versions that did not work.

To capture the exact text of a live run, set `LOG_PROMPTS=true` in `.env`. Every
prompt is then printed to the console before it is sent.

---

## 1. Request structure

Each stage sends two messages over the OpenAI-compatible chat protocol:

```
system:   SYSTEM_PROMPT                  (identical for all six stages)
user:     evidence block                 (identical for all six stages)
          + prior context                (varies: results of earlier stages)
          + stage instruction            (varies)
```

The user message is assembled constant-first on purpose: the evidence block,
which is the same for every stage, comes before the prior context and the
stage instruction, which change. The rationale is that a provider which caches
identical prefixes can reuse the evidence across the six calls - but nothing in
the code depends on that. Prefix caching is a provider-specific optimisation,
and this tool is provider-agnostic, so the ordering is a free win where it
applies and harmless where it does not.

---

## 2. The system prompt

Shared by every stage, so the same standard applies everywhere rather than only
where it was convenient to write it down. It carries four rules.

**Rule 1 - separate the layers.** Defines fact, assumption, hypothesis and
action, and forbids one masquerading as another. This is enforced structurally
as well: `Fact`, `Assumption`, `Hypothesis` and `Action` are four distinct
Pydantic types in [`app/schemas.py`](../app/schemas.py), so a fact without
evidence is not merely discouraged, it fails validation.

**Rule 2 - cite or don't claim.** The prompt states that quotes are checked
automatically after the fact. This matters: telling the model that verification
happens changes its behaviour more reliably than asking it to be careful.

**Rule 3 - argue against yourself.** Instructs the model to search for
disconfirming evidence and to say explicitly when it found none, rather than
leaving the field empty. An empty field is ambiguous - it could mean "I looked
and found nothing" or "I did not look". Forcing the distinction is the whole
point.

**Rule 4 - do not resolve uncertainty you have not earned.** Bans "the root
cause is". Requires a confidence level plus what would change it.

The closing constraints target specific failure modes the brief names:
post hoc reasoning, anchoring on the loudest error, and base-rate neglect.

---

## 3. The evidence block

Rendered by `build_evidence_block()`. Three deliberate features:

**Explicit source keys.** The block prints the list of valid `source` values and
delimits each section with `===== BEGIN ... (source key: logs) =====`. The
citation checker looks a quote up in the section whose key the model named, so
this vocabulary has to be closed and visible. Before the keys were printed
explicitly, the model invented plausible source names like `"application_logs"`
and every citation failed verification.

**An explicit closed-world statement.** "The evidence below is everything that is
known. Anything not present here is not known." Without this the model filled
gaps with reasonable-sounding defaults - typical connection pool sizes, plausible
timestamps - that were not in the data.

**A list of what was not provided.** Naming the empty sections stops the model
speculating about what they would have contained.

---

## 4. Stage instructions

### Stage 1 - summary and the facts/assumptions split

Asks for prose, then facts, then assumptions. Two clauses do real work:

- *"Do not name a cause - that is a later stage."* Without it the summary
  announced a root cause in sentence two, and every later stage anchored on it.
- *"An empty assumptions list on noisy real-world data is almost always wrong."*
  Early runs returned zero assumptions and a long facts list, because listing
  facts feels more useful. Naming the expectation fixed it.

### Stage 2 - timeline

The `inferred` flag is the point of this stage. The instruction defines
inference broadly ("ordering two events by reasoning about causality rather
than by their timestamps counts as inferred") because the first version let the
model mark only events with missing timestamps, and quietly presented a deduced
ordering as if it had been read from the data.

The closing line - *"Being marked inferred is not a flaw; hiding that something
was inferred is"* - was added after the model began dropping uncertain events
entirely rather than marking them.

### Stage 3 - hypotheses

The most heavily constrained instruction, because this is where the reasoning
goes wrong. Three hard requirements:

1. **At least one hypothesis must not involve the most recent change.** Without
   it, on the `checkout-v241` example every hypothesis was a variant of "the
   deploy did it" - textbook anchoring, and wrong.
2. **At least one must consider an ordinary operational cause.** Directly
   targets base-rate neglect.
3. **Blaming a change requires a mechanism.** Targets the post hoc fallacy.
   "It happened just before" is explicitly rejected as an argument.

The `contradicting_evidence` instruction tells the model to return an empty list
and explain, rather than manufacture weak counter-evidence to look balanced.
An earlier version that just said "include contradicting evidence" produced
padding - trivial objections invented to fill the field, which is worse than
an honest empty list because it looks like rigour.

`recommended_test` must be able to come out either way. Without that clause the
model proposed tests that could only confirm.

### Stage 4 - reasoning risks

Built at runtime from [`app/core/biases.py`](../app/core/biases.py) by
`risks_instruction()`, so the eight biases from the brief are injected as a
closed vocabulary with ids the model must copy exactly. Anything outside the
catalogue is discarded in `app/services/reasoning_risks.py` and reported to the
user as a warning - a closed vocabulary is only closed if something enforces it.

*"A generic definition of the bias is not an answer."* Early output restated
textbook definitions. Requiring the model to point at a specific hypothesis or
gap in this investigation forced it to do the work.

The last line makes the model audit its own output for automation bias. It is
the only place the tool is asked to be suspicious of itself.

### Stage 5 - actions and open questions

*"Reject anything that would be equally true of any incident"* plus the named
examples ("check the logs", "monitor the situation") removes generic advice.
Requiring a named log, metric, service or config key is what makes an action
checkable.

The open-questions section closes with *"if it is empty, you have almost
certainly overreached somewhere above"* - the same expectation-setting trick
used for assumptions in stage 1, and it works the same way.

### Stage 6 - postmortem

Prescribes the section list exactly, so output is comparable between runs and
between incidents. Two global rules: do not declare a root cause found, and do
not introduce any fact that is not in the material above. The second exists
because the postmortem stage sees the most context and was the stage most prone
to inventing a tidy detail to round out a sentence.

---

## 5. Prompt iterations worth reporting

| Change | Symptom before | Result after |
| --- | --- | --- |
| Print the valid `source` keys in the evidence block | Model invented source names; every citation failed verification | Citations resolve |
| Add "the evidence below is everything that is known" | Plausible invented pool sizes and timestamps | Gaps reported as unknown |
| Move cause-naming out of the summary stage | Summary announced a cause; later stages anchored on it | Hypotheses stay open |
| Require one hypothesis unrelated to the recent change | All hypotheses blamed the deploy | Genuinely competing explanations |
| Allow an empty `contradicting_evidence` list *with an explanation* | Invented weak objections to look balanced | Honest empty lists, flagged in the UI |
| Broaden the definition of `inferred` | Deduced orderings presented as read from data | Inference is visible |
| Inject the bias catalogue as a closed vocabulary | Model reported biases not in the brief | Only the eight, ids validated in code |
| Require risks to point at a specific hypothesis | Textbook definitions restated | Findings specific to the run |

---

## 6. Model settings

The tool talks to any OpenAI-compatible endpoint, chosen entirely in `.env`.
Nothing here is tied to a particular provider.

| Setting | Value | Why |
| --- | --- | --- |
| Endpoint / model | `AI_BASE_URL` / `AI_MODEL` | Set in `.env`. The default is Google Gemini (`gemini-2.5-flash`), which has a free tier. Groq, OpenRouter, a local Ollama model, OpenAI and Anthropic are one uncommented block away. |
| Output | structured JSON | The request first asks for the provider's formal `json_schema` response format, generated from the Pydantic model by `strict_schema()`, so the contract cannot drift from the parsing code. |
| Fallback | plain JSON object | If a provider cannot enforce the schema, the client retries once in `json_object` mode with the schema described in the prompt (`schema_hint()`). Either way the output is validated by `parse_into()`. |
| Streaming | on | The response is streamed and reassembled, so a slow provider does not trip a single-request timeout. |

Two settings that an earlier version had are deliberately gone: **prompt
caching** and **adaptive thinking / effort**. Both were specific to a single
vendor's API. The reflective report records why they were dropped when the tool
became provider-agnostic.

Structured output is worth one closing note. Asking a model to "reply in JSON"
and parsing whatever comes back means every stage can fail in a new way.
Constraining the response to a schema removes that class of bug - but more
importantly it removes the temptation to accept a well-written prose answer
that has quietly blurred a guess into a fact. The shape is the discipline.

---

## 7. Provider portability and the prompts

Making the tool provider-agnostic did **not** require changing a single prompt.
Every instruction in `app/ai/prompts.py` is written in plain language about
evidence, citation and uncertainty - none of it depends on a vendor-specific
feature. That is why the same prompts run unchanged against Gemini, Groq, a
local model, or any other OpenAI-compatible endpoint.

The one provider-shaped concern - that not every endpoint can enforce a formal
JSON schema - is handled in the client, not the prompts, by the fallback in
section 6. The prompts stayed a stable, portable contract while the transport
underneath them changed.
