# Quality Editorial Workflow v1 — Implementation Plan

Status: **Architecture pass only — no product code modified in this commit.**
Date: 2026-05-18
Authors (team roles): Chief AI Product Architect, AI Workflow Architect, Prompt Engineering Lead, Editorial Director, Backend Lead, Frontend Lead, Security Lead, QA Lead, Observability Lead, Research Lead.

---

## 1. Executive summary

Replace the monolithic `generate_for_cluster()` call (one 13-field JSON schema in a single LLM round-trip) with a step-by-step **Quality Editorial Workflow**: Research Analyst → Trend Strategist → Audience Psychology Analyst → Style DNA Editor → Platform Writers → Critic/Red Team → Editor-in-Chief Finalizer → Quality Judge.

Each step is small (≤ 6 schema fields, ≤ 500-token output), persistable as a `GenerationArtifact`, and inspectable in the UI. A new `GenerationRun` row is the unit of work; the worker pulls queued runs and advances them step-by-step. The current `/brief/generate` endpoint keeps its mock-mode contract and becomes a **queue submission** (HTTP 202) in real-provider mode — no more 30-minute API blocks.

Editorial quality is the goal. Speed is secondary. The pipeline is designed for high-quality real LLMs (Kimi K2.6, Claude Opus, GPT-4o) and remains deterministic under the existing `MockLLMProvider` for tests.

All existing safety guarantees stay locked: `PUBLISHING_ENABLED=false`, `DRY_RUN_PUBLISH=true`, three-layer approval gate untouched, Vault untouched, no auto-`ApprovalDecision`, no auto-`PublishJob`.

---

## 2. Current repo diagnosis (grounded)

Files inspected this pass (all confirmed in the working tree):

| File | What it does | Why it's relevant |
|---|---|---|
| [services/candidate.py:75-126](packages/shared/chief_editor/services/candidate.py) | One `provider.complete_json` call with `_CANDIDATE_SCHEMA` (13 fields) + critic pass + DB write | This is the monolith. Times out on Kimi:cloud. |
| [services/candidate.py:16-39](packages/shared/chief_editor/services/candidate.py) | `_CANDIDATE_SCHEMA` — 13 required fields, 3 nested via `enum` | Far above the "≤ 8 fields, ≤ 2 nesting" 2026 best practice. |
| [llm/base.py:11-19](packages/shared/chief_editor/llm/base.py) | `LLMProvider.complete_json(system, user, schema, temperature)` | Single primitive available today. No streaming, no tool-use, no batched. |
| [llm/ollama_provider.py:82-127](packages/shared/chief_editor/llm/ollama_provider.py) | OpenAI-compat chat completions, prompt-only JSON request, one repair-retry | No constrained decoding. Returns prose+JSON; recoverable via existing `_safe_parse`. |
| [llm/registry.py:16-66](packages/shared/chief_editor/llm/registry.py) | Provider resolution (env → vault → mock) | Already in place from Vault work. Reuse as-is. |
| [llm/mock.py:82-185](packages/shared/chief_editor/llm/mock.py) | Deterministic Russian copy from seeded text hash | Will be extended to support per-step deterministic responses. |
| [services/critic.py:51-147](packages/shared/chief_editor/services/critic.py) | Deterministic regex critic — slop, hook, hedge, CTA, length | Becomes the heuristic critic *next to* the LLM Critic step (defense-in-depth). |
| [worker/main.py:92-136](apps/worker/worker/main.py) | `generation_loop` polls top 5 clusters every 600s, calls `generate_for_cluster` | New `generation_runs_loop` slots in alongside; the existing loop can later delegate to it. |
| [worker/main.py:43-58](apps/worker/worker/main.py) | `_heartbeat` + `session_scope` pattern | Reuse verbatim. |
| [routers/briefs.py:21-40](apps/api/app/routers/briefs.py) | `POST /brief/generate` — synchronous, returns `list[CandidateOut]` | Backward-compat: mock mode unchanged, real mode → 202 + run_id. |
| [models/candidate.py:8-30](packages/shared/chief_editor/models/candidate.py) | `PostCandidate` schema (15 fields, `status` default `"draft"`) | Untouched. The finalizer step writes a `PostCandidate` only on success. |
| [models/_base.py:27-30](packages/shared/chief_editor/models/_base.py) | `TimestampedBase` + `json_column` + `json_list_column` | Reuse for `GenerationRun`/`Step`/`Artifact`. |
| [tests/test_brief_generate_safety.py:1-89](tests/test_brief_generate_safety.py) | Pins: draft-only candidates, no `ApprovalDecision`, no `PublishJob`, mock provider yields Russian | Becomes the regression contract for the new path. |
| [apps/web/app/(app)/editor/page.tsx:1-78](apps/web/app/(app)/editor/page.tsx) | Editor index — lists candidates by status | Add a "Generate Quality Brief" entry point here. |
| [apps/web/app/(app)/trends/page.tsx:1-80](apps/web/app/(app)/trends/page.tsx) | Trend Radar with focus card | Add the same button on the focused cluster. |

---

## 3. Research findings (with sources)

Live web searches were run on 2026-05-18. All URLs verified via WebSearch.

### 3.1 Prompt chaining vs monolithic prompts
- **Evidence:** Decomposing into chained prompts achieves up to ~15.6% better accuracy than monolithic; the 2026 canonical pattern is "Router-Solver-Critic" + Self-Refine. — Sources: [Orkes — The Secret to Stronger Agentic Workflows](https://orkes.io/blog/prompt-engineering-in-agentic-workflows/), [Sathish Raju — AI Agentic Workflow Patterns That Actually Matter in 2026](https://medium.com/@sathishkraju/the-ai-agentic-workflow-patterns-that-actually-matter-in-2026-08955ac6f398), [LangChain — Average steps per trace doubled 2.8 → 7.7](https://www.langchain.com/articles/agent-observability).
- **Assumption:** "15.6%" figure is an industry survey, not a vendor-published benchmark for our exact pipeline. Treat as directional.

### 3.2 Structured outputs and JSON reliability
- **Evidence:** Native structured output / constrained decoding hits ~100% schema compliance; prompt-only JSON fails ~5–15% per request. Keep schema nesting ≤ 2-3, ≤ ~6 fields. Place `editorial_rationale` field **before** answer fields so the model generates left-to-right reasoning. — Sources: [Pockit — LLM Structured Output in 2026](https://pockit.tools/blog/llm-structured-output-complete-guide/), [Cohere docs](https://docs.cohere.com/docs/structured-outputs).
- **Implication for us:** Ollama Cloud (Kimi K2.6) speaks OpenAI-compatible Chat Completions; we cannot rely on Anthropic's tool-use input_schema. We MUST keep schemas small and use the existing repair-retry as a fallback.

### 3.3 Async long-running LLM jobs
- **Evidence:** Canonical 2026 pattern — submit → 202 Accepted with `job_id`, persist as `PENDING`, worker consumes queue, client polls status. Durable execution (Temporal, Inngest, Arq) is the production trend. — Sources: [Mitesh Jat — Non-Blocking Async LLM API](https://medium.com/@mitesh.singh.jat/building-a-non-blocking-asynchronous-llm-api-with-spring-boot-kafka-and-ollama-81adaabe94df), [Arq Background Jobs 2026](https://johal.in/arq-background-jobs-async-queue-management-2026/).
- **Implication for us:** Our existing worker + SQLModel-backed queue is enough for v1; no Celery/Arq dep required.

### 3.4 MCP risks
- **Evidence:** OWASP MCP Top 10 exists; March 2025 study found 43% of public MCP servers had command-injection flaws; 30% allowed unrestricted URL fetching. MCP is a transport, not a governance layer. — Sources: [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/), [Practical DevSecOps — MCP Security Vulnerabilities](https://www.practical-devsecops.com/mcp-security-vulnerabilities/), [InfoQ — Cloudflare on MCP architecture, April 2026](https://www.infoq.com/news/2026/04/cloudflare-mcp/).
- **Implication for us:** We do NOT introduce MCP into the generation pipeline in v1. The pipeline is closed-world.

### 3.5 Observability for multi-step agent workflows
- **Evidence:** Multi-agent tracing where each step = span is the 2026 norm. OpenTelemetry semantic conventions (Microsoft + Anthropic contributing) are the cross-vendor schema. Common SaaS: Braintrust, Langfuse, Laminar. — Sources: [Braintrust — Agent Observability Complete Guide 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026), [Microsoft Foundry agent tracing](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/trace-agents-sdk).
- **Implication for us:** v1 ships with structured logs only (structlog already wired). The field names mirror OTel agent semantic conventions so a tracer can be dropped in later without rename churn.

### 3.6 Chain-of-thought storage & safety
- **Evidence:** OpenAI's published research warns that CoT is *fragile*: training pressure can make it look helpful regardless of internal state. Storing private reasoning long-term is risky. — Sources: [OpenAI — Reasoning models struggle to control their CoT](https://openai.com/index/reasoning-models-chain-of-thought-controllability/), [OpenAI — Evaluating CoT monitorability](https://openai.com/index/evaluating-chain-of-thought-monitorability/).
- **Implication for us:** `GenerationArtifact` rows store only canonical step outputs. A bounded `editorial_rationale` (≤ 240 chars) is allowed as a deliverable field. We do NOT store raw model "thinking".

### 3.7 Claude Code subagents (project agents) format
- **Evidence:** Project agents live in `.claude/agents/<name>.md` with YAML frontmatter (`name`, `description` required; `tools`, `model`, `permissionMode`, `disallowedTools`, `maxTurns` optional). Tool names are short ("Read, Edit, Bash"). The Markdown body is the system prompt. — Source: [code.claude.com/docs/en/sub-agents.md](https://code.claude.com/docs/en/sub-agents.md) (verified May 2026).
- **Implication for us:** 9 agents in `.claude/agents/` follow this format exactly. See companion files committed alongside this plan.

### 3.8 Human-in-the-loop / approval governance
- **Evidence:** EU AI Act Article 14 (Human Oversight) takes effect Aug 2, 2026; content agents must keep approvals in the human path. — Source: [Strata — Human-in-the-Loop 2026 guide](https://www.strata.io/blog/agentic-identity/practicing-the-human-in-the-loop/), [Anna Jey — Human-in-the-Loop AI Agents 2026](https://medium.com/@arvisionlab/human-in-the-loop-ai-agents-how-to-add-approvals-escalation-and-safe-autonomy-in-production-0a21e359781c).
- **Implication for us:** Existing three-layer approval gate (API route → worker dispatch → publisher boundary) is exactly the recommended pattern and stays untouched. The Quality Judge step recommends — never auto-approves.

### Sources unavailable
- We could not retrieve a vendor benchmark for Kimi K2.6:cloud structured-output reliability. Treat the `_safe_parse` repair-retry as the safety net; no claim is made about its hit rate without direct measurement.

---

## 4. Why monolithic candidate generation fails

Two failure surfaces, each by itself sufficient:

1. **Model/provider:** Kimi K2.6:cloud answers the small `/readiness/test-llm` probe (~50 tokens out) in ~10 seconds. The current monolith asks for ~600 tokens of output across 13 fields, with `temperature=0.7` and prompt-only JSON instructions. Across two retries × 10-minute SDK timeout, the request never returns bytes (HTTP 000 observed twice in prior sessions). Likely upstream queueing on Kimi:cloud + token-by-token serialization of a long structured response.

2. **Product architecture:** Even when the model eventually returns, a 30-minute synchronous `POST /brief/generate` blocks the API thread, blocks the worker (which calls the same function on its 600s tick), and the user has no progress signal. The 13-field schema is also impossible to debug — a single bad field rolls back the whole transaction with no partial artifact preserved.

Backend orchestration limitation: the worker's `generation_loop` competes with the API endpoint for the same provider and the same transaction scope. No queue, no progress, no cancel.

UI/UX limitation: the Editor index / Trend Radar pages have a "Generate brief" button that links to `/editor`. There is no per-cluster progress, no artifact view, no per-step retry — the operator gets a spinner and a silent 500 if the model times out.

---

## 5. Why external OpenClaw / Hermes / off-the-shelf agent frameworks are NOT the right core right now

- **MCP-based orchestration**: high-risk per OWASP MCP Top 10 (43% command-injection in March 2025 servers). Wrong attack surface for an alpha. (§3.4)
- **LangGraph / CrewAI / AutoGen**: heavy runtime deps, opinionated state schemas; rewriting our domain model (Source, RawItem, TrendCluster, PostCandidate, ApprovalDecision, PublishJob) into theirs is too much risk for too little win at this stage. We get the same evaluator-optimizer benefits from a thin local engine.
- **External LLM gateways (Braintrust/Langfuse/Laminar)**: we should adopt one for observability later; v1 emits structured logs that align with OTel agent semantic conventions so the migration is rename-free. (§3.5)
- **Inngest / Temporal**: durable-execution frameworks are nice-to-have. SQLModel rows + the existing worker loop give us the same "resume from last successful step" property at v1 scale.

In short: do the minimum local engine that captures the patterns (chained steps + evaluator-optimizer + safe artifacts), and keep the door open for the SaaS layer later.

---

## 6. Why an internal Quality Editorial Workflow IS the right architecture

- Maps 1:1 to the existing editorial brief shape (we are not abandoning the brand voice / critic / dry-run model — we are decomposing the single call into the steps the team would do anyway).
- Reuses everything already in the repo: `LLMProvider.complete_json` primitive, `StyleProfile`, the deterministic `critique()` heuristic, `session_scope()`, `_heartbeat()`, structlog with redaction, `_safe_parse` repair-retry.
- Preserves all existing safety invariants by design — no new code path can bypass the three-layer approval gate.
- Small surface: one new module package (`services/generation/`), three new models, one new router, one worker loop, two new UI components. Roughly 6–8 PRs cleanly sliceable (see §18 rollout).

---

## 7. New data models

All inherit `TimestampedBase` (UUID PK, `created_at`, `updated_at`) and live in `packages/shared/chief_editor/models/generation.py`. Registered in `models/__init__.py`.

### 7.1 `GenerationRun`
```python
class GenerationRun(TimestampedBase, table=True):
    __tablename__ = "generation_runs"
    cluster_id: str | None = Field(default=None, foreign_key="trend_clusters.id", index=True)
    requested_by: str = Field(default="api", max_length=32)   # "api" | "worker" | "manual"
    status: str = Field(default="queued", index=True, max_length=24)
    # queued | running | succeeded | failed | cancelled
    current_step: str = Field(default="", max_length=48)      # name of latest step
    step_index: int = 0                                       # 0..N
    total_steps: int = 8
    candidate_id: str | None = Field(default=None, foreign_key="post_candidates.id", index=True)
    # Filled ONLY by finalizer after Quality Judge passes.
    error_class: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=240)    # truncated, no secrets
    started_at: datetime | None = None
    finished_at: datetime | None = None
    provider: str = Field(default="", max_length=24)          # snapshot at start
    model: str = Field(default="", max_length=64)
```

### 7.2 `GenerationStep`
```python
class GenerationStep(TimestampedBase, table=True):
    __tablename__ = "generation_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_index", name="uq_run_step_index"),)
    run_id: str = Field(foreign_key="generation_runs.id", index=True)
    step_index: int                                            # 0..N
    name: str = Field(index=True, max_length=48)
    # research | strategy | psychology | style_dna | platform_writers | critic | finalizer | quality_judge
    status: str = Field(default="pending", max_length=24)
    # pending | running | succeeded | failed | skipped | cancelled
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    error_class: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=240)
```

### 7.3 `GenerationArtifact`
```python
class GenerationArtifact(TimestampedBase, table=True):
    __tablename__ = "generation_artifacts"
    run_id: str = Field(foreign_key="generation_runs.id", index=True)
    step_id: str = Field(foreign_key="generation_steps.id", index=True)
    name: str = Field(max_length=48)                           # human-readable
    schema_version: str = Field(default="v1", max_length=12)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
    # JSON-only canonical step output. NO raw model text, NO private CoT.
```

### 7.4 (optional) `QualityReport`
A single row per run produced by the Quality Judge step, summarizing the rubric scores. Could live as a `GenerationArtifact` with `name="quality_report"` — choose whichever the Backend Lead prefers during implementation.

State machine:
```
GenerationRun:
  queued ──worker pick──▶ running ──last step ok──▶ succeeded
                              │
                              ├─any step fails──────▶ failed
                              │
                              └─cancel request──────▶ cancelled
GenerationStep:
  pending ──worker──▶ running ──complete──▶ succeeded
                          │
                          ├─error──▶ failed (run transitions to failed)
                          └─cancel──▶ cancelled (run transitions to cancelled)
```

---

## 8. New service architecture

New package: `packages/shared/chief_editor/services/generation/`.

| File | Purpose | Notes |
|---|---|---|
| `__init__.py` | Public re-exports | `from .workflow import run_workflow; from .steps import STEP_SEQUENCE` |
| `workflow.py` | Orchestrator. Takes `(session, GenerationRun)`, advances one step per tick. Owns transactions. | Each step runs in its own committed transaction so failures preserve prior artifacts. |
| `steps.py` | `STEP_SEQUENCE: list[Step]`. Each `Step` carries name, prompt builder ref, schema, parser, downstream artifact name, retry policy. | Pure data; no DB writes. |
| `prompts.py` | Per-step system + user prompt templates and JSON schemas (≤ 6 fields each). | Russian-first system prompts. Owned by Prompt Engineering Lead. |
| `artifacts.py` | Pydantic validators for each step's artifact shape. Writes `GenerationArtifact` rows. | Validators catch malformed payloads before they hit DB. |
| `finalizer.py` | Translates the collected artifacts into a `PostCandidate` row + runs the deterministic `critique()` from `services/critic.py`. | The ONLY place a `PostCandidate` is created. |
| `provider_capabilities.py` | Maps `LLMProvider.name → ProviderCapability`. Decides per-step parameters (temperature, max_tokens, schema variant). | Anthropic uses tool-use input_schema; OpenAI uses response_format; Ollama/Mock use prompt-only JSON. |

Engine pseudocode (one tick per run):
```python
def advance_one_step(session: Session, run: GenerationRun) -> None:
    if run.status not in {"queued", "running"}:
        return  # cancelled / terminal
    next_index = run.step_index if run.status == "queued" else run.step_index + 1
    if next_index >= len(STEP_SEQUENCE):
        finalize(session, run)        # creates PostCandidate, run.status = "succeeded"
        return
    step_def = STEP_SEQUENCE[next_index]
    step_row = create_step_row(session, run, step_def, next_index)
    try:
        artifact = step_def.execute(session, run)   # calls provider.complete_json
        save_artifact(session, run, step_row, artifact)
        step_row.status = "succeeded"
        run.step_index = next_index
        run.status = "running"
        run.current_step = step_def.name
    except Exception as exc:
        step_row.status = "failed"
        step_row.error_class = type(exc).__name__
        step_row.error_message = str(exc)[:240]
        run.status = "failed"
        run.error_class = step_row.error_class
        run.error_message = step_row.error_message
    session.commit()
```

Transactional invariant (hard): **No `PostCandidate` row exists until `finalize()` commits successfully.** Mid-run failure leaves a `GenerationRun(status="failed")` and N partial `GenerationArtifact` rows for debugging, but zero candidates and zero approvals/jobs.

---

## 9. Editorial pipeline (8 steps)

Each step is one `provider.complete_json` call. Each schema has an `editorial_rationale` field FIRST when a short user-safe explanation is needed (≤ 240 chars). **`editorial_rationale` is a user-safe deliverable, not private chain-of-thought** — it must be safe to render in the UI; it never quotes hidden model reasoning or any content outside the step's canonical output. Soft length limits are non-binding hints; the Critic step enforces real limits.

| # | Step name | Reads | Produces (artifact) | Schema shape (≤6 fields) | Russian-first? |
|---|---|---|---|---|---|
| 1 | `research_analyst` | TrendCluster keywords + up to 5 RawItem titles+bodies | `research_brief`: `{editorial_rationale, fact_bullets[3-7], source_handles[≤5], gaps[≤3]}` | 4 fields | yes (RU output) |
| 2 | `trend_strategist` | research_brief + cluster score_breakdown | `angle`: `{editorial_rationale, primary_angle, contrarian_take, why_now}` | 4 fields | yes |
| 3 | `audience_psychology_analyst` | angle + StyleProfile.audience | `psych`: `{editorial_rationale, target_emotion, hook_pattern, cognitive_bias_lever}` | 4 fields | yes |
| 4 | `style_dna_editor` | psych + StyleProfile (tone, banned_phrases, example_posts) | `voice_brief`: `{editorial_rationale, sentence_length_target, vocab_lane, must_avoid[≤5]}` | 4 fields | yes |
| 5a | `platform_writer_telegram` | voice_brief + angle | `tg_post`: `{editorial_rationale, body (≤1024), hook (≤80), cta}` | 4 fields | yes |
| 5b | `platform_writer_threads` | voice_brief + angle | `threads_post`: `{editorial_rationale, body (≤500), cta}` | 3 fields | yes |
| 5c | `platform_writer_reddit` | voice_brief + angle | `reddit_post`: `{editorial_rationale, title (≤300), body (≤1500), cta}` | 4 fields | EN allowed |
| 6 | `critic_red_team` | all platform_posts | `critic_report`: `{editorial_rationale, slop_count, factual_concerns[≤3], length_issues[≤3], hook_grade}` | 5 fields | yes |
| 7 | `editor_in_chief_finalizer` | all of the above | `final_brief` artifact ONLY: `{editorial_rationale, topic, source_summary (≤400), why_it_matters (≤300), psychology_hook (≤200), final_tg, final_threads, final_reddit, cta}` (9 fields — the only step allowed to exceed the cap because it ASSEMBLES, doing no new generation, just selection + minor copy). **Does NOT create `PostCandidate`.** | yes |
| 8 | `quality_judge` | final_brief + heuristic `critique()` from `services/critic.py` | `quality_report` artifact: `{editorial_rationale, style_match_score, viral_score, slop_risk, controversy_risk, recommendation}` | 6 fields, mirrors today's `_CANDIDATE_SCHEMA` scores | yes |

Steps 5a/5b/5c run in **sequence** in v1 (not parallel) — keeps SQLite transaction logic simple. Parallel batching is a v2 optimization once we measure step latencies.

**Candidate creation order (hard rule):** Step 7 produces only the `final_brief` artifact. Step 8 produces only the `quality_report` artifact. The **`finalizer.py` service creates the `PostCandidate(status="draft")` only after Step 8 succeeds** — it reads both artifacts, runs the heuristic `critique()`, and assembles the row in a single transaction. If Step 8 fails or `quality_judge` returns `recommendation: "reject"`, the `GenerationRun` flips to `failed` and no `PostCandidate` is written. This invariant is enforced by code structure: `grep -r "PostCandidate(" packages/shared/chief_editor/services/generation/` must return exactly one hit, inside `finalizer.py`.

---

## 10. Provider strategy

`provider_capabilities.py` returns a `ProviderCapability` per `LLMProvider.name`:

| Provider | Schema style | Temperature | Max tokens out | Notes |
|---|---|---|---|---|
| `mock` | prompt-only JSON (existing) | n/a | n/a | Deterministic per-step; extend `MockLLMProvider._step_response(step_name, seed)`. |
| `ollama` (Kimi K2.6:cloud) | prompt-only JSON + `_safe_parse` repair-retry (existing) | 0.7 (creative), 0.2 (judge) | ~500 | Single-step budget keeps response small; expect each step to return in ≤ 60 seconds. |
| `ollama` (local) | same | same | same | Lower latency, no per-step cost concern. |
| `anthropic` | **Implementation spike — not guaranteed.** Docs indicate Anthropic's GA `output_config.format` with `type: "json_schema"` provides constrained decoding, but Phase 1 does NOT change `AnthropicProvider`. Wiring decision is deferred until we (a) confirm the pinned `anthropic>=0.39` SDK exposes `output_config.format`, and (b) confirm whether Ollama Cloud's OpenAI-compat passthrough forwards `response_format` to Kimi:cloud. Until then, `anthropic` uses the same prompt-only JSON path as `ollama`. | same | same | Spike (see [docs](https://platform.claude.com/docs/en/docs/build-with-claude/structured-outputs)). |
| `openai` | `response_format={"type": "json_schema", "schema": …}` — also an implementation spike until verified. | same | same | OpenAI's native Structured Outputs path; pinned SDK version to be validated. |

Each capability instance will carry: `supports_native_structured_output: bool`, `recommended_temperature(step_name)`, `recommended_max_tokens(step_name)`, `step_retry_budget`, `step_timeout_seconds`. **Phase 1 does NOT add the `LLMCallOptions` parameter to `LLMProvider.complete_json` yet** — it is documented in §1b as a backward-compatible Phase 2+ extension.

A failed step is retried at most once with a repair prompt (mirrors the existing `ollama_provider.py:117-127` pattern). After that, the run fails.

### 10b. `LLMCallOptions` (Phase 2+ design)

Backward-compatible extension over the current `LLMProvider.complete_json(system, user, schema, *, temperature=0.7)` signature. Lives in `packages/shared/chief_editor/llm/base.py` alongside `LLMProvider`. Pure data; Phase 1 call sites in `services/candidate.py` and `readiness/checks.py` continue to ignore it.

```python
@dataclass(frozen=True)
class LLMCallOptions:
    step_name: str = ""                          # for logging only — never in payload
    temperature: float | None = None             # None → provider default
    timeout_seconds: int | None = None           # None → provider default (SDK retry policy)
    max_tokens: int | None = None
    response_mode: Literal["json", "json_strict"] = "json"
    # "json"        = prompt-only JSON + _safe_parse repair-retry (existing path)
    # "json_strict" = constrained-decoding when provider supports it (FUTURE; Phase 2+)
    provider_mode: Literal["auto", "force_real", "force_mock"] = "auto"
    # "auto"        = registry decides (existing get_llm_provider behavior)
    # other values  = reserved for tests
```

**Phase 1 does NOT add this parameter** to `complete_json`. Phase 2 will introduce it as an optional kwarg so existing call sites are unaffected; `provider_capabilities.py` will produce the per-step instance.

---

## 11. API endpoints

New router: `apps/api/app/routers/generation_runs.py`. **ALL endpoints require `X-Admin-Token`** via the existing `require_admin_token` dependency from `apps/api/app/deps.py`. No new auth system. Rationale: generation runs trigger real LLM cost and the artifacts are private editorial work; in the current alpha/live/public tunnel context every endpoint is gated identically to `/secrets/*`.

| Method | Path | Body / Query | Auth | Returns | Notes |
|---|---|---|---|---|---|
| POST | `/generation-runs` | `{cluster_id?: str, top_n?: int}` | admin | `GenerationRunOut` (status `queued`) — HTTP **202** | Enqueues 1..N runs. |
| GET | `/generation-runs` | `?status=queued|running|...` `&limit=` | admin | `list[GenerationRunOut]` | Paginated by `created_at desc`. |
| GET | `/generation-runs/{id}` | — | admin | `GenerationRunOut` + summary counts | Used for UI polling. |
| GET | `/generation-runs/{id}/steps` | — | admin | `list[GenerationStepOut]` | Ordered by `step_index`. |
| GET | `/generation-runs/{id}/artifacts` | — | admin | `list[GenerationArtifactOut]` | Payloads as JSON. |
| POST | `/generation-runs/{id}/cancel` | — | admin | `GenerationRunOut` | Sets `status="cancelled"`; worker honors on next tick. |

`GenerationRunOut` keys: `id, cluster_id, status, current_step, step_index, total_steps, candidate_id, error_class, error_message, started_at, finished_at, provider, model, created_at, updated_at`.

Error semantics: 401 on missing/invalid `X-Admin-Token`; 404 on unknown id; 409 on cancel-after-terminal; 422 on unknown `cluster_id`.

---

## 12. Backward compatibility for `/brief/generate`

```python
@router.post("/generate", response_model=BriefGenerateResponse)
def generate(...):
    settings = get_settings()
    if settings.mock_mode or settings.llm_provider == "mock":
        # Existing synchronous path — fast, deterministic, tested.
        return BriefGenerateResponse(candidates=[generate_for_cluster(...) for ...])
    # Real-provider path: enqueue one run per cluster, return run ids.
    run_ids = [enqueue_run(session, cluster_id) for cluster_id in ...]
    return BriefGenerateResponse(run_ids=run_ids, status="queued")  # HTTP 202
```

`BriefGenerateResponse` is a discriminated union:
```python
class BriefGenerateResponse(BaseModel):
    candidates: list[CandidateOut] | None = None   # mock-mode legacy shape
    run_ids: list[str] | None = None               # real-mode async shape
    status: str | None = None                      # "queued" when run_ids set
```

`tests/test_brief_generate_safety.py` already runs in mock mode (`MOCK_MODE=true` in conftest) — its assertions on `c["status"] == "draft"` and zero `ApprovalDecision`/`PublishJob` rows stay green unchanged. A new test pins the real-provider 202 + `run_ids` shape via `monkeypatch`.

---

## 13. Worker orchestration

New loop: `async def generation_runs_loop(stop: asyncio.Event)` in `apps/worker/worker/main.py`. Interval: max(15, `settings.generate_interval_seconds // 8`). Runs alongside the existing `generation_loop` (which can later delegate by calling `enqueue_run` instead of `generate_for_cluster`).

Per tick:
1. `SELECT * FROM generation_runs WHERE status IN ('queued','running') ORDER BY created_at LIMIT 3`. Concurrency cap = 3 (SQLite + small server; tune later).
2. For each run:
   - If `status == "cancelled"`: short-circuit, do nothing.
   - Else: call `workflow.advance_one_step(session, run)`. Commits at end of step.
3. `_heartbeat(session, "generation_runs", "tick")`.

Failure behavior:
- A step raising any exception → step row `failed` + run row `failed`, with `error_class` / `error_message` (truncated 240 chars). Worker moves on.
- A run stuck in `running` for > 30 minutes (configurable later) is NOT auto-recovered in v1; a stale-run reaper is v2.
- Cancellation: any tick checks `status == "cancelled"` before each LLM call. Mid-step requests are NOT interrupted — they finish, but no further step runs.

No partial `PostCandidate` until `finalize()` succeeds. This is enforced by:
- `workflow.advance_one_step` commits per step.
- `finalize()` is its own transaction at step 8+1 (after `quality_judge`).
- The Backend Lead's hard-verification step `grep -r "PostCandidate(" packages/shared/chief_editor/services/generation/` returns ONLY a hit inside `finalizer.py`.

---

## 14. UI plan

No redesign. Two new entry points + two new components.

**Entry points (insertions only):**
- `apps/web/app/(app)/editor/page.tsx` — add a `<Button>` next to "New from trend" in the `Topbar.actions` slot: "Generate Quality Brief" → opens a small modal with a cluster picker (defaults to top trending) → POSTs to `/generation-runs` → navigates to `/editor/runs/{id}`.
- `apps/web/app/(app)/trends/page.tsx` — on the focused cluster card, add a second button "Generate Quality Brief" that POSTs `{cluster_id}` and navigates to `/editor/runs/{id}`.

**New route:** `apps/web/app/(app)/editor/runs/[id]/page.tsx` — full-page run viewer.

**New components:**
- `components/feature/generation/run-timeline.tsx` (client) — polls `GET /generation-runs/{id}` every 1500 ms until terminal. Renders one row per step with the visual language of `readiness-section.tsx::ReadinessRow` (icon + label + status badge + duration + "View artifact" link).
- `components/feature/generation/artifact-card.tsx` (client) — modal/slide-over that renders the artifact payload as a labeled list (Russian content shown as-is; no JSON tree — too dev-y). Read-only.

**States:**
- `queued`: ghost timeline, "Waiting in queue" banner.
- `running`: live timeline; current step pulses cyan; previous steps green.
- `succeeded`: link to `/editor/{candidate_id}` ("Open final draft"); all artifact cards expanded.
- `failed`: red banner with `error_class`; "Retry" enqueues a fresh run.
- `cancelled`: muted timeline; "Cancelled by user"; "Run again" enqueues fresh.

Polling stops automatically on terminal status (§Frontend Lead agent).

---

## 15. Observability plan

- **Per-step structured log** via `structlog.get_logger("chief_editor.generation").info(event, run_id=..., step_name=..., status=..., duration_ms=..., provider=..., model=..., tokens_in=..., tokens_out=...)`. NEVER include prompt/completion text.
- **SystemLog rows** for run-level transitions only (`generation.run.queued`, `.started`, `.succeeded`, `.failed`, `.cancelled`). Data payload whitelisted to `{run_id, status, step_count, duration_ms, error_class}`. Mirrors `apps/api/app/routers/secrets.py::_audit` discipline.
- **OpenTelemetry semantic conventions** (Microsoft + Anthropic contribution): field names chosen to match the agent-span attributes draft so a future tracer can be wired without renaming columns. See [Microsoft Foundry agent tracing](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/trace-agents-sdk).
- **Artifact safety**: `GenerationArtifact.payload` is the canonical JSON output of each step (≤ 6 fields). No raw model text. No private CoT beyond `editorial_rationale ≤ 240 chars`.
- **No external tracer in v1.** Local structured logs + DB rows are the surface. SaaS observability (Braintrust/Langfuse/Laminar) is a v2 plug-in.

---

## 16. Safety invariants

These MUST be preserved end-to-end. The Security Lead agent enforces them on every PR.

1. `PUBLISHING_ENABLED=false` and `DRY_RUN_PUBLISH=true` are unchanged by every code path in `services/generation/`.
2. Zero auto `ApprovalDecision`. Zero auto `PublishJob`. Asserted by grep + tests.
3. `PostCandidate.status` is always `"draft"` when created by the finalizer. Approval is a human action via `apps/api/app/routers/approvals.py`.
4. Vault untouched: `services/secrets/`, `services/integration_config.py`, `apps/api/app/routers/secrets.py`, `apps/api/app/deps.py::require_admin_token`. Generation pipeline reads credentials only via the existing `llm_registry.get_llm_provider()` indirection.
5. No secret leaks: no `decrypt(` call in `services/generation/`. No env var name / Vault key name in API responses.
6. No private CoT storage: `GenerationArtifact.payload` contains only canonical step output JSON.
7. `SystemLog.data` whitelist for generation events. Vault secret-substring sweep tests stay green.
8. No streaming endpoints in v1; no SSE; no WebSocket. Poll-based UI only — simpler attack surface.

---

## 17. Tests to add

(See `qa-lead.md` for full budget. Summary here.)

- `tests/test_generation_models.py` — 6 tests covering creation, unique constraints, default statuses, JSON columns.
- `tests/test_generation_runs_api.py` — 10 tests covering all 5 endpoints (200, 404, 409, 422), shape of `GenerationRunOut`, cancellation, mock-mode end-to-end run.
- `tests/test_generation_worker.py` — 6 tests covering step advancement, transaction rollback on failure, cancellation honored on next tick, no `PostCandidate` until finalizer, heartbeat written.
- `tests/test_generation_provider_capabilities.py` — 4 tests covering the routing matrix for `mock`/`ollama`/`anthropic`/`openai`.
- `tests/test_generation_safety.py` — 6 tests covering: no auto `ApprovalDecision`, no auto `PublishJob`, candidate stays `draft`, dry-run preview still returns `would_send=false`, `SystemLog` whitelist holds, `/brief/generate` mock-mode contract still green.
- Extend `tests/test_brief_generate_safety.py` with a real-provider 202-path test (monkeypatched, no live network).
- `pnpm -C apps/web run typecheck` and `pnpm -C apps/web run build` clean on every UI PR.

Target: **209 tests** (179 current + ~32 new). 100% pass before declaring v1 done.

---

## 18. Rollout strategy

Sliced for clean PRs and Security Lead audits between each.

| Phase | Scope | Deliverable | Tests | Owner |
|---|---|---|---|---|
| **1** | Backend models + skeleton router | `GenerationRun`, `GenerationStep`, `GenerationArtifact` models; `apps/api/app/routers/generation_runs.py` with 5 endpoints; mock-mode end-to-end pipe returning an empty run. | Model tests + endpoint contract tests (~16). | Backend Lead |
| **2** | Workflow service + per-step prompts | `services/generation/*` package; 8 steps wired; `provider_capabilities.py`; MockLLM extended for per-step responses. | Worker step-execution tests (~10). | Backend + Prompt Engineering Leads |
| **3** | Worker orchestration | `generation_runs_loop` in `worker/main.py`; cancellation; concurrency cap. | Worker tests + safety tests (~12). | Backend Lead |
| **4** | UI surface | Buttons, `/editor/runs/[id]` page, timeline, artifact viewer. | `pnpm typecheck` + `pnpm build` clean. | Frontend Lead |
| **5** | Quality + safety regression | Full safety sweep, Security Lead audit, Editorial Director rubric on sample run, Observability log review. | All 4 gates green; 209 tests. | QA + Security + Editorial + Observability Leads |

Each phase ends with a Security Lead audit run + Editorial Director sample review before merge.

---

## 19. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Kimi K2.6:cloud still slow per-step (~60s × 9 steps = 9 min total run) | Medium | This is the speed-vs-quality trade-off the product accepts. UI shows progress; user knows it's working. Optional v2 parallelism on platform writers. |
| One step returns invalid JSON twice; run fails | Medium | Repair-retry already exists; if it fails, run fails cleanly with `error_class`. User retries; no half-state in DB. |
| Concurrency conflicts on SQLite WAL with 3 parallel runs | Low | SQLite WAL handles this (already in `db.py`); cap is conservative. |
| Prompt regression — a step's prompt loses voice quality | Medium | Editorial Director scores every prompt before merge; Quality Judge step + heuristic `critique()` catch low scores at runtime. |
| Step that consumes prior artifact diverges silently | Medium | Pydantic validator per step (`services/generation/artifacts.py`) catches malformed input before the LLM call. |
| Observability bloat → SystemLog leaks something | Low | Whitelist enforced in code, swept by existing vault tests. New safety test scans SystemLog after a full run. |
| Worker hangs on a Kimi:cloud connection without timing out | Medium | Step-level timeout in `provider_capabilities.py`; default 5 minutes per step. Worker reaper of stale `running` runs is v2. |
| Adding parallel platform-writer steps later breaks transaction boundaries | Low | v1 is serial; v2 design will add a small fan-out helper. |
| Provider switches (Anthropic/OpenAI) need different schema mode | Medium | `provider_capabilities.py` encapsulates the difference; `LLMProvider.complete_json` signature stays stable. |
| EU AI Act Article 14 compliance | Low (we already comply) | Approval gate is human-only; this plan does not change that. Documented in §16. |

---

## 20. Recommended next-phase implementation prompt

Hand this to the team when ready to start Phase 1. It is self-contained:

```
We are implementing Phase 1 of the Quality Editorial Workflow (see
QUALITY_EDITORIAL_WORKFLOW_PLAN.md sections 7, 11, 18).

Constraints:
- Do not change Vault (services/secrets/, integration_config.py, deps.py::require_admin_token).
- Do not change safety flags or any code under publishing/.
- Do not change UI in this phase.
- Do not introduce auto ApprovalDecision or PublishJob.

Scope:
1. Add models GenerationRun, GenerationStep, GenerationArtifact in
   packages/shared/chief_editor/models/generation.py per plan §7. Register
   in models/__init__.py.
2. Add router apps/api/app/routers/generation_runs.py with all 5 endpoints
   per plan §11. No admin_token requirement. Use Depends(get_session).
3. Add a stub `services/generation/__init__.py` exporting enqueue_run() that
   creates a GenerationRun row in status="queued" — no LLM calls yet.
4. Wire the backward-compat shim in apps/api/app/routers/briefs.py per plan
   §12: mock mode keeps the existing list[CandidateOut] response; real-mode
   creates one GenerationRun per cluster and returns
   {run_ids, status: "queued"} with HTTP 202. Use a discriminated-union
   response model.
5. Tests:
   - tests/test_generation_models.py — 6 tests per plan §17.
   - tests/test_generation_runs_api.py — at least the GET-list, GET-by-id,
     POST-create, POST-cancel, 404, 409 cases.
   - Extend tests/test_brief_generate_safety.py with a real-provider 202-path
     test using monkeypatch to flip LLM_PROVIDER without making any network
     call.
6. Quality gates that MUST pass before declaring done:
     python -m pytest -q
     python -m ruff check .
     pnpm -C apps/web run typecheck
     pnpm -C apps/web run build
7. Security Lead audit: invoke @agent-security-lead with the diff scope.
   Report must be SHIP before merge.

Use the project subagents:
- ai-workflow-architect for any design clarifications
- backend-lead for implementation
- qa-lead for test authoring
- security-lead for the final audit
- observability-lead for SystemLog wiring

Output:
- Files changed
- Test counts
- Security Lead audit verdict
```

---

## Appendix — Source list

Cited above; consolidated here:

- [Claude Code sub-agents docs (May 2026)](https://code.claude.com/docs/en/sub-agents.md)
- [Orkes — Stronger Agentic Workflows](https://orkes.io/blog/prompt-engineering-in-agentic-workflows/)
- [Sathish Raju — Agentic Workflow Patterns 2026](https://medium.com/@sathishkraju/the-ai-agentic-workflow-patterns-that-actually-matter-in-2026-08955ac6f398)
- [LangChain — Agent Observability](https://www.langchain.com/articles/agent-observability)
- [Pockit — LLM Structured Output 2026](https://pockit.tools/blog/llm-structured-output-complete-guide/)
- [Cohere — Structured Outputs](https://docs.cohere.com/docs/structured-outputs)
- [Mitesh Jat — Async LLM API](https://medium.com/@mitesh.singh.jat/building-a-non-blocking-asynchronous-llm-api-with-spring-boot-kafka-and-ollama-81adaabe94df)
- [Arq Background Jobs 2026](https://johal.in/arq-background-jobs-async-queue-management-2026/)
- [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/)
- [Practical DevSecOps — MCP Security Vulnerabilities](https://www.practical-devsecops.com/mcp-security-vulnerabilities/)
- [InfoQ — Cloudflare on MCP](https://www.infoq.com/news/2026/04/cloudflare-mcp/)
- [Braintrust — Agent Observability Complete Guide 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026)
- [Microsoft Foundry — Agent Tracing](https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/trace-agents-sdk)
- [OpenAI — CoT Controllability](https://openai.com/index/reasoning-models-chain-of-thought-controllability/)
- [OpenAI — Evaluating CoT Monitorability](https://openai.com/index/evaluating-chain-of-thought-monitorability/)
- [Strata — HITL 2026 Guide](https://www.strata.io/blog/agentic-identity/practicing-the-human-in-the-loop/)
- [Anna Jey — HITL AI Agents 2026](https://medium.com/@arvisionlab/human-in-the-loop-ai-agents-how-to-add-approvals-escalation-and-safe-autonomy-in-production-0a21e359781c)

End of plan.
