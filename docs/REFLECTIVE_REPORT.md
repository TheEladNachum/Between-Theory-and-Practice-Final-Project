# IncidentIQ - Reflective Report

## 1. Project overview and purpose

I built IncidentIQ as an AI-assisted incident-response and root-cause analysis prototype. It accepts the kinds of incomplete material that a software team receives during a production incident - logs, stack traces, monitoring alerts, deployment notes, support messages, and an incident description - and turns that material into a structured investigation. Its outputs are a professional summary, a timeline, several competing hypotheses, evidence supporting and contradicting each hypothesis, reasoning risks, practical next actions, open questions, and a draft postmortem.

The most important design choice is that the system does not declare a root cause. Production incidents are uncertain: logs can be incomplete, a recent deployment can be an attractive but false explanation, and a loud error can be a symptom rather than a cause. An AI answer may sound confident even when its evidence is weak. I therefore designed IncidentIQ to support human judgement, not replace it.

The project follows the brief's four-part reasoning structure. A **fact** must be directly supported by the submitted evidence. An **assumption** may be reasonable but is not yet proven. A **hypothesis** is a possible explanation that must be tested. An **action** is a concrete next step, experiment, check, or communication task. These categories are separate in the Pydantic data model, the AI prompts, the pipeline, and the interface. This separation is not cosmetic. It prevents a plausible guess from becoming a "fact" merely because the model expresses it fluently.

I also required evidence citations, confidence levels, counter-evidence, and a test that could disprove each hypothesis. After generation, citations are checked against the exact input section named by the model. A quote that cannot be found is surfaced as unverified rather than silently accepted. This is my main answer to the project's central question: AI can organize evidence and propose possibilities, but its claims still need visible, mechanical, and human checks.

## 2. Architecture and main features

IncidentIQ has a Python/FastAPI backend and a browser frontend built with vanilla HTML, CSS, and JavaScript modules. FastAPI serves the static interface and API routes. Server-Sent Events provide stage-by-stage progress because six sequential AI calls can take time. The frontend has one renderer for each result area, while shared state and network calls remain separate. Avoiding a frontend build system makes the prototype easier for an instructor to run on a new computer.

The backend is divided into clear layers:

- `app/schemas.py` defines facts, assumptions, hypotheses, actions, timelines, risks, and the complete investigation result.
- `app/ai/client.py` is the only layer that communicates with an AI endpoint.
- `app/ai/prompts.py` contains the common reasoning rules and stage-specific instructions.
- `app/core/evidence.py` verifies citations, while `app/core/biases.py` defines the closed catalogue of reasoning risks.
- `app/services/` contains the six analysis stages and the pipeline that coordinates them.
- `app/main.py` exposes the browser application, configuration information, examples, and analysis stream.

The six pipeline stages are summary, timeline, hypotheses, reasoning risks, actions, and postmortem. Later stages receive selected earlier results. A stage failure does not erase completed work; the pipeline records a warning and continues where possible.

Structured output is central to the architecture. The client derives JSON schemas from the same Pydantic models used for validation. It first asks the provider to enforce a formal schema. If that response format is unsupported, it retries in JSON-object mode with the expected schema included in the prompt. Either route still ends with local validation. This reduces parsing failures and makes it harder to accept polished prose that has mixed facts with guesses.

## 3. Technologies and engineering choices

I used Python 3.10+, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`, the OpenAI SDK as a generic transport for OpenAI-compatible endpoints, vanilla JavaScript modules, CSS custom properties, Server-Sent Events, and pytest. Configuration is stored in `.env`; the distributable template is `.env.example`, with an empty key.

The OpenAI SDK supplies a common chat-completions transport; it does not fix the project to OpenAI. A base URL, API key, and model select compatible providers without editing analysis services. I preferred one generic boundary to duplicated vendor classes.

I chose a simple browser interface because usability is part of correctness for this project. A system that technically works only after an instructor edits hidden files in a terminal is not a convincing one-click prototype. This lesson became especially important in Commit 11.

## 4. My development process and use of AI

I used AI extensively both as the analysis engine inside IncidentIQ and as a development assistant. However, the difficult part was not asking AI to generate more code. It was deciding what to trust, what to test, what to reject, and what question to ask next. Between commits I repeatedly stopped, inspected the result, asked follow-up questions, and compared the proposal with the brief. This made the work slower than blindly accepting a large generated solution, but it made each commit more defensible.

My prompt iterations followed observed failure modes. When the model invented plausible source names, I printed the exact allowed source keys. When it filled missing evidence with typical pool sizes or timestamps, I added a closed-world instruction stating that absent information is unknown. When a summary named a cause too early and anchored later stages, I explicitly prevented cause selection in the summary. When all hypotheses blamed the most recent deployment, I required one hypothesis unrelated to that change and one ordinary operational explanation. When the request for counter-evidence produced artificial objections, I allowed an honest empty list only with an explanation. I did not change wording merely because it sounded better; each change targeted a specific reasoning or validation problem.

I also used the assistant to review implementation choices. Useful assistance included identifying that the launcher should be simplified so the server always starts, recognizing that a browser settings form must never read the stored secret back, and noticing that cached settings would remain stale after `.env` was changed. These were proposals, not proof. I checked them against the code: `get_settings()` was decorated with `lru_cache`, the existing `/api/config` response intentionally excluded the key, and the old launchers really did stop when the key was empty.

The development experience was personal and demanding. I worked through ten incremental snapshots and did not simply request the final application in one prompt. I asked questions between commits, checked how the pieces connected, and challenged convenient answers. My conversation with Claude eventually reached its token or usage limit just as work on an `.env` writer was beginning. That created an ambiguous hand-off: an assistant message indicated that a file had been started, but the overall commit was not complete. I learned not to equate an AI progress statement with a verified repository state. The correct response was to inspect the files and requirements again, then continue deliberately rather than assume the interrupted work was finished.

This experience mirrors IncidentIQ itself. A model can propose a likely state, but the repository is the evidence. I treated AI-generated code and explanations as hypotheses to verify through inspection, comparison, automated checks, and actual behavior.

## 5. Critical change from Commit 9 to Commit 10

Commit 9 completed the documentation around a working but vendor-specific design. Before moving on, I asked whether the architecture really satisfied the portability and critical-use goals. The answer was no. Although AI access was isolated behind one client, the implementation was tied to Claude-specific settings and features. It required a particular paid provider, used vendor-specific adaptive reasoning and prompt-caching controls, and had not demonstrated that the supposedly replaceable boundary was actually replaceable.

Commit 10 changed the provider layer to an OpenAI-compatible interface controlled by `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL`. It replaced the provider-specific client while leaving the six services and their reasoning prompts conceptually stable. It also added a fallback for providers that do not support formal JSON Schema and improved error mapping for authentication, permission, missing model, rate limit, and connection failures. Ready-to-edit provider blocks were added to the environment template.

This change shows critical evaluation because I revised a solution that already looked complete. I accepted a trade-off: vendor-specific prompt caching and effort controls were removed because they did not generalize. Portability, comparison between models, access to free tiers, and the possibility of using a local model mattered more than preserving optimizations for one service.

The API-key experience then revealed a second weakness. A key could be present while the provider still rejected it, including a permission or access failure. The interface's green "key loaded" state only proved that text existed in configuration; it did not prove that the key, endpoint, and model formed a working connection. I questioned the earlier assumption directly: **does having a key mean having a valid key?** It does not. That distinction motivated Commit 11.

## 6. Critical change from Commit 10 to Commit 11

Commit 11 focuses on the first-run experience and on making configuration status truthful. In Commit 10, the launcher checked for an empty key, opened a text editor, and stopped. This meant the user could not reach the interface that already knew how to explain the missing configuration. It was technically understandable but poor product behavior, especially for an instructor who should be able to double-click `run.bat` and immediately see the project.

The revised flow starts the server and opens the browser even when no API key exists. If `.env` is absent, the launcher creates it from `.env.example` without putting a real key in the archive. The page remains usable for reading the interface and loading examples. Analysis is unavailable until configuration is supplied, but the application itself no longer fails to appear.

The browser adds a settings control for entering a new API key and selecting or editing the model and provider endpoint. On save, the server updates only the relevant `.env` values instead of replacing the whole file, so comments and unrelated options can remain intact. The existing key is never returned to the browser; the form permits replacement, not retrieval. This is a deliberate one-way secret flow: browser to local server to `.env`.

Status is communicated with both words and color. **Red** means configuration is missing or a real check has failed. **Orange** means values are present but not yet verified, or a connection check is in progress. **Green** is reserved for a successful provider connection. The text remains essential because color alone is not accessible and cannot explain the reason for failure. A real validation request distinguishes "a string was saved" from "this provider accepts this key for this model." If validation fails, the user should see an actionable provider error instead of a misleading success badge.

One subtle technical issue was the settings cache. `get_settings()` uses `lru_cache` to avoid parsing `.env` repeatedly. Without invalidation, saving a new key in the browser would change the file but the running process would continue using the old Settings object. That would make a correct save look broken and would encourage unnecessary restarts. Commit 11 therefore clears the cache after a successful write and reloads the configuration before reporting status or starting analysis.

This transition required careful, intelligent use of AI tools. I did not accept the first suggestion to add more launch-time checks, because the simpler behavior was to remove the blocking check and let the interface explain state. I asked specifically when `.env` should be created, what the browser can see, whether saving a key exposes it, and why a saved value might not take effect. I also reduced scope where a proposed protection could create last-minute bugs without addressing the immediate coursework need. The result is a smaller and more coherent commit: launch immediately, configure locally, refresh cached settings, and validate the actual connection.

## 7. Useful and misleading AI assistance

I can report the development interaction honestly without inventing model-output quotations. The most useful outputs were process-level design critiques. The assistant recognized that several requested features were already partly present and that the launcher was the obstruction. It identified cache invalidation as a hidden failure mode. It also separated two security questions that I initially mixed together: writing a new key from a local page is different from sending the existing key back to that page. This helped me preserve the one-way design.

The AI was also useful in producing structured drafts, test ideas, and alternatives quickly. It could enumerate failure modes such as 401 authentication failure, 403 permission failure, an unavailable model, or an unsupported response format. That breadth accelerated my review, but I still had to decide which behaviors belonged in the current commit.

The misleading part was not necessarily a single false sentence. It was the cumulative impression that earlier generated work was more complete than it was. The original vendor-specific design looked modular because communication lived in one file, yet it still depended on one provider's API and features. Later, the green badge said a key was loaded even though the provider could reject every request. The old launcher had been generated as a helpful setup flow, but in practice it prevented the no-key interface from opening. Finally, Claude's interrupted session demonstrated that a confident progress update can outlive the available context and leave unfinished integration.

I therefore distinguish three levels of evidence. I directly observed the launcher behavior, configuration fields, cache decorator, provider rejection, and assistant usage limit. I inferred design risks from those observations. I did **not** invent successful incident-analysis responses, exact hallucinated sentences, or live-provider test results that I did not obtain. That honesty is more valuable than filling the report with impressive but unverifiable examples.

## 8. Facts, assumptions, hypotheses, and actions in my own reasoning

I used the same structure on my development decisions. A fact was that `.env` contained a non-empty string; an assumption was that the string might be a valid key; the hypothesis was that the configured endpoint and model would accept it; the action was a small connection test. The old badge collapsed the fact and hypothesis. Commit 11 keeps them separate.

Another fact was that `get_settings()` was cached. An assumption was that writing `.env` would immediately affect the running server. Inspection contradicted that assumption. The hypothesis was that clearing the cache after writing would make the next read current; the action was to invalidate and reload settings, then verify behavior.

For the provider redesign, the fact was that six services called one AI boundary. The assumption was that this made the tool provider-independent. Comparing settings, imports, request fields, and dependencies showed that assumption was false. The resulting action was a bounded client/configuration rewrite rather than a change to every service.

## 9. Cognitive biases and fallacies encountered

### Confirmation bias

Once the recent deployment became the obvious suspect in the checkout scenario, it was easy to collect only supporting details. I noticed this because the evidence also said that errors began before the deployment and persisted after rollback. I reduced the bias by requiring evidence both for and against every hypothesis and by allowing a test to disconfirm it. In my development work, I also searched for evidence that the provider-agnostic change had failed rather than only confirming that configuration names had changed.

### Anchoring bias

The first error message, first hypothesis, or first AI proposal can establish the frame for everything that follows. Early summaries that named a cause caused later stages to repeat it. I moved causal reasoning out of the summary and required competing hypotheses. During Commit 11, I avoided anchoring on the first proposed implementation by asking whether the easiest launcher fix was deletion of blocking behavior rather than addition of new checks.

### Automation bias

Professional formatting and specific technical language made AI suggestions feel verified. I experienced this directly when generated code and progress descriptions created a sense of completion. The token-limit interruption exposed that feeling: the conversation stopping did not prove which changes existed or worked. I mitigated automation bias by reading the actual files, comparing commits, checking configuration boundaries, and treating every assistant recommendation as a candidate decision.

### Post hoc fallacy

In incident analysis, "the deployment happened before the failure" can be mistaken for a causal mechanism. The checkout example deliberately contradicts that shortcut. I required a mechanism and evidence, not chronology alone. The same discipline applied to the API problem: the failure occurred after the provider redesign, but timing alone did not prove the redesign caused it. A rejected or restricted key, endpoint permissions, and model access remained competing explanations.

### Availability bias

Familiar causes such as deployment regressions, load, or connection-pool exhaustion are easy to recall, so they can crowd out less familiar explanations. I addressed this by requiring ordinary operational alternatives and evidence-specific tests rather than generic guesses. In implementation, I resisted assuming that the key problem matched the most familiar 401 case; the observed rejection could instead be a 403 permission or project-access issue.

### Overconfidence bias

The green "API key loaded" badge was a concrete example of overstatement. It presented presence as if it were readiness. I noticed the mismatch only when a populated value still failed against the provider. The red/orange/green model reduces overconfidence by reserving green for a verified connection and using orange for an unresolved state.

### Hindsight bias

After finding the cache issue, it was tempting to say that cache invalidation was obvious. It was not obvious before browser-based editing was introduced; the old design expected a restart after manual editing. I record the sequence honestly: the new requirement changed the lifetime of configuration, which made the old cache behavior a problem.

### Base-rate neglect

An unusual AI or infrastructure explanation can sound more sophisticated than a common setup error. I mitigated this by checking simple causes first: missing values, wrong model, endpoint mismatch, permissions, and stale configuration. The tool's prompts similarly require at least one ordinary operational hypothesis so rare explanations do not dominate merely because they are interesting.

## 10. Problems encountered and solutions

The largest technical problem was maintaining strict reasoning while supporting multiple providers. Providers differ in structured-output support and error behavior. I handled that variance at one client boundary, retained local Pydantic validation, and exposed provider messages instead of guessing their meaning.

The largest usability problem was the setup loop. The application could explain that a key was missing, yet the launcher stopped before the user could see that explanation. I solved this by making startup independent of API configuration and moving configuration into the running interface.

The largest reasoning problem was confusing configuration presence with successful authentication. The solution was a four-state concept - missing, unverified, checking/failed, and verified - simplified visually into red, orange, and green with descriptive text. The cache issue was solved by invalidating settings immediately after an environment update.

The largest process problem was continuity after Claude reached its token or usage limit. I solved it by returning to evidence: the brief, the latest complete snapshot, the file tree, and the exact unfinished requirements. This prevented me from blindly continuing an assumed implementation.

## 11. Ethical and professional considerations

The main ethical risk is over-trust. IncidentIQ can generate a plausible explanation or a risky action, but responsibility remains with the engineer. The interface therefore shows uncertainty, competing hypotheses, counter-evidence, and verification status. It should never claim authority it has not earned.

Production evidence may contain personal data, tokens, internal addresses, or confidential system details. The prototype does not yet redact input before sending it to an external provider, so real organizational logs should not be submitted without review. Provider independence partly helps because a local compatible model can keep evidence on the machine, but redaction and policy controls remain necessary future work.

Browser-based writing to `.env` has a modest security aspect. For this local coursework prototype, the server binds to `127.0.0.1`, `.env` is ignored by Git and excluded from the distributable archive, and the stored key is never read back into the page. I deliberately did not claim that Commit 11 implements Origin or CSRF hardening. Adding Origin validation, CSRF protection, stricter permissions, and possibly an operating-system credential store would be appropriate future hardening. I kept that out of this commit because the immediate risk in a local demonstration is limited and rushed security middleware could introduce startup or browser-compatibility bugs.

## 12. Evaluation and future improvements

IncidentIQ meets the intended strong-prototype scope: it has structured inputs, six analysis outputs, multiple example incidents, evidence checking, confidence and counter-evidence, reasoning-risk detection, graceful stage failure, Markdown export, tests that do not require a real key, and a one-click local interface. Commits 10 and 11 improve two weaknesses that only became clear through critical use: provider dependence and misleading setup state.

I do not treat this as proof that the analysis is accurate. A proper evaluation needs incidents with known causes, repeated runs, comparison across models, and measures such as whether the true cause appears among the top hypotheses and whether cited claims are actually entailed by the evidence. Citation matching detects invented quotations but not every misleading interpretation.

Future improvements should include automatic redaction, retrieval over larger log sets, saved investigations, side-by-side model comparison, accessibility testing of status indicators, stronger local configuration security, and a broader evaluation dataset with ground truth. The most valuable next experiment would run the same incident through two providers and display agreements and disagreements. That would turn provider independence into an explicit uncertainty tool rather than only a configuration feature.

## 13. Conclusion

The strongest lesson from this project is that critical AI use is an active engineering practice. I worked iteratively, questioned results between commits, changed designs that looked finished, and documented where the assistant helped and where it created false confidence. Commit 9 to 10 showed that a clean-looking abstraction could still hide vendor dependence. Commit 10 to 11 showed that a present key is not necessarily a valid key and that technically correct setup can still be poor user experience.

AI accelerated drafting, implementation ideas, failure-mode discovery, and prompt refinement. It did not remove my responsibility to inspect, test, narrow scope, and communicate uncertainty. In both the product and my own workflow, the same rule held: separate facts from assumptions, treat explanations as hypotheses, and take verifiable actions before claiming success.

## Appendix - supporting material

- Full system prompt and prompt-iteration rationale: [`PROMPTS.md`](PROMPTS.md)
- Installation, configuration, examples, and project structure: [`../README.md`](../README.md)
- Windows launch: `run.bat`; macOS/Linux launch: `run.sh`
- Local interface: `http://127.0.0.1:8000`
