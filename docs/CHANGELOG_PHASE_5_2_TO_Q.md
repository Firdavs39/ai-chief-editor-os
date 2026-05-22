# Changelog: Phase 5.2 → Phase Q (this PR)

> What changed between commit `c6c75c2` (main, pre-PR) and the head of
> branch `phase-5.2-through-13`. Written for the operator, not the
> developer — focuses on "what does this give me?" rather than commits.

---

## TL;DR — what you can do now that you couldn't before

| Capability | Before this PR | After this PR |
|---|---|---|
| **Run Quality Editorial Workflow on real Kimi** | Worked once (Phase 5), failed reproducibly (Phase 5.1: 50% failure rate) | Reproducible — Phase 5.2 schema fix validated end-to-end, Phase 7 succeeded on real RSS data in 39 min |
| **See real trends from real sources** | Demo seed only | 11 RSS sources active, 142 items + 50 clusters from vc.ru / Habr / TechCrunch / MIT Tech Review etc. |
| **Read deterministic AI-tells in critic_report** | Not measured | Em-dash density, sentence-length variance, banned-phrase hits, front-loaded anchor, screenshottable phrase, vague time markers, anti-CTA position — all surfaced automatically |
| **Track cost per generation** | Not measured | `/analytics/cost` endpoint + per-step `tokens_in / tokens_out` persisted in DB; ~$0.10-0.15 per real run on Kimi |
| **Trust the output more** | Generic "OK but not viral" drafts | Phase Q-grade output: side-quest paragraphs with locatable specificity, decimal anchors, self-correction, imperative CTAs |
| **Know what to do next** | Vague "approval gate exists" | `OPERATOR_RUNBOOK.md` 4-step ritual + `phase8_safety_walker.py` interactive walker |
| **Run a reproducibility test** | Manual one-at-a-time | `scripts/phase6_batch.py --n 8` runs 8 clusters back-to-back, writes CSV |

---

## Daily workflow now

1. Open `http://localhost:3000/trends` — see ~50 real trend clusters.
2. Pick one, click **Generate Quality Brief**.
3. Wait ~30-45 minutes (Kimi-bound; nothing to do).
4. Read draft in `/editor/{candidate_id}`. The Phase Q prompts produce:
   - **Hook**: one of 8 named patterns (`number_as_reframe`, `second_person_scene`,
     `contrarian_inversion`, `social_threat_diagnostic`, `mini_cliffhanger`,
     `insider_artifact`, `confession_opener`, `anti_universal`).
   - **TG version**: 800-1500 chars typical; engagement-optimal.
   - **Threads version**: 180-380 chars; open-question CTA.
   - **Reddit version**: 60-90 char title + 800-2000 char body.
   - **Critic report**: deterministic AI-tells flags + LLM editorial judgment merged.
   - **Quality Judge**: calibrated scores (style_match / viral / slop / controversy)
     with explicit approve/revise/reject logic.
5. Approve / Reject / Rewrite.
6. (If Approve) Run the 4-step publish ritual in `OPERATOR_RUNBOOK.md`.

---

## Phases shipped in this PR, in order

1. **Phase 5.2 — Schema hotfix** for Kimi length-overflow failure
2. **Phase 6 — Token telemetry** (no fallback wired, Kimi-only stack)
3. **Phase 7 — RSS source wiring** (11 real sources active)
4. **Phase 8 — Safety walker** (interactive script, operator-flag flips only)
5. **Phase 10 — Cost dashboard** (`/analytics/cost`)
6. **Phase 11 — Style DNA proposal scaffold** (no silent mutation)
7. **Phase 12 — Performance feedback scaffold** (capped engagement boost)
8. **Phase 13 — Hosting decision** (`HOSTING_DECISION.md`)
9. **Phase Q — Quality Hardening** (51 banned phrases catalogued in detector,
   8 hook patterns, 15-emotion taxonomy, 10 evasion rules, dead-lever
   deny-list, R2-derived rules: front-loaded anchor / screenshottable
   phrase / vague time markers / anti-CTA position, R3-derived: prompt
   trimming to Kimi sweet spot, Sierra-style supervisor post-merge,
   Bad/Good anti-example pair)

---

## Files an operator might actually open

- [docs/PHASE_PLAN.md](PHASE_PLAN.md) — master roadmap
- [docs/OPERATOR_RUNBOOK.md](OPERATOR_RUNBOOK.md) — 4-step publish ritual
- [docs/HANDOFF.md](HANDOFF.md) — what's left for the operator
- [docs/PHASE_5_2_REPORT.md](PHASE_5_2_REPORT.md) — Kimi stability validation
- [docs/PHASE_Q_REPORT.md](PHASE_Q_REPORT.md) — final quality validation
- [docs/HOSTING_DECISION.md](HOSTING_DECISION.md) — when to deploy off localhost

## Numbers

- **+~5300 lines** of code & docs across **~30 files**
- **+105 tests** (initial 258 → 362; +40%)
- **0** safety regressions (all `test_approval_gate*`, `test_publishing_safety*`
  tests still pass)
- **9 commits** in this PR (`be26b55` → `cd4db09`)
- **Ruff clean** across the entire repo

## What is still operator-action only (not automatable)

- Provide Reddit credentials → 5 subreddits unlock as sources
- Provide Telethon `api_id` + `api_hash` → 5 TG channels unlock
- Create Telethon session file via interactive SMS code (local machine only)
- Create test channel + Telegram bot + provide bot token
- Flip `PUBLISHING_ENABLED=true` and `DRY_RUN_PUBLISH=false` (only the
  operator — never Claude)
- Approve / reject / rewrite candidates
- 7 days of daily-publish observation (Phase 9 milestone)

Each step is described in `OPERATOR_RUNBOOK.md` and `HANDOFF.md`.

## What does NOT change

- Three-layer approval gate stays — no auto-publish.
- Vault stays encrypted at rest with MultiFernet.
- Schema validation strict.
- `PUBLISHING_ENABLED=false` and `DRY_RUN_PUBLISH=true` defaults preserved.
- Claude never flips safety flags.
