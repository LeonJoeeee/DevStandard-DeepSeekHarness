# 0049 — Each role's static context is its own delivered artifact, injected by default

Status: Accepted (2026-09-07). Amends 0007 (one always-loaded page becomes several role artifacts,
and its every-session budget becomes a per-artifact byte gate), 0015 (its delivery contrast),
0016 (where the skill bindings are stated) and 0019 (the delivery mechanism only — its diagnosis,
its hook matcher and its unsupported-environment behavior stand). Amended by 0056 (2026-09-11). Amended by 0063 (2026-09-29). Amended by 0064 (2026-10-05).

*This ADR changes what DevStandard ships — what the SessionStart hook emits, and which page each
role reads — so a reader in a seeded project should take it as method.*

## Context

0007 decided one always-loaded page, injected by the hook. 0019 flipped the delivery to a
hook-forced first-action read, because Claude Code inline-caps hook `additionalContext` and had been
silently delivering a truncated preview for months. 0019's own Consequences named the price it paid
for that fix: the scheme relies on model compliance, and the guaranteed inline paste is gone.

Since then `core.md` was the *only* artifact, so it had to carry the shared contract and every
role's operative rules at once — which is what kept pushing it against the cap in the first place.
The approved architecture (chapter 3) splits static context by role: one shared contract plus one
operative source per role. The human's delivery ruling on issue #179 makes **direct injection the
default for every static context set**, with each artifact's concrete carrier — inline injection or
an instructed read — chosen at implementation from that artifact's measured size against the cap.
Rebuild 5 (#205/#235) implemented the split and took the measurement; #258/#264 then settled what
happens to an artifact that does not fit.

## Decision

**1. Static context is per role.** `core.md` carries the shared workflow contract, the role
interlock and the triggers. `reference/orchestrator.md` and `reference/worker.md` are the operative
role sources, and `reference/code-review-prompt.md` remains the reviewer's. Agent definitions and
dispatch briefs are carriers of those sources, never independently edited copies.

**2. Delivery is per artifact, and injection is the default.** The SessionStart hook emits one
output per delivered artifact and inlines that artifact whole when its complete `additionalContext`
fits under the cap the hook measures; only an artifact that does not fit falls back to 0019's forced
IN FULL read. 0019's matcher — `startup|clear|compact`, resume excluded — is unchanged, and so is
its visible warning on an environment the hook cannot identify.

**3. The fallback is not a resting place.** The core-budget gate **fails** when a delivered
artifact's complete context crosses the measured cap, so an over-cap artifact is a red check rather
than a quietly degraded delivery. 0007's every-session budget and 0019's context-cost governor
therefore become a hard per-artifact byte budget enforced in CI. The measurement's method, date and
figure are recorded once, in `docs/specs/2026-09-06-core-md-rule-ledger.md`; this ADR states no
figure, because the current one is the gate's to report.

**4. Workers and reviewers are not hook-delivered.** Each receives its role through dispatch — the
Claude agent definition or the Codex brief — naming the same role source the hook would have used.
0015's delivery contrast (a separate session gets the injection; a subagent gets the brief pasted)
is retired: neither role depends on a session hook, and one file is the source for both
implementations.

What survives: 0007's no-router, no-skill shape, its `@path` ban, and the on-demand `reference/`
split (0031); and 0019's diagnosis, which is the whole reason for point 3 — the failure worth
preventing is a delivery that degrades without saying so, and it is now a red gate instead of a
preview nobody saw.

Rejected: **one always-injected page** — it must then carry both roles' operative rules, which is
the condition that produced 0019's truncation. Rejected: **keeping the forced read as the default**
— it trades a measurable guarantee for model compliance, and the measurement shows the delivered
artifacts fit. Rejected: **letting an over-cap artifact fall back silently** — that is 0019's
original failure with a better message on it.

## Consequences

Each delivered artifact now carries a budget it cannot exceed. Growing one means moving a rule to a
page read at its trigger, and the rule ledger records where each rule went. Session start pays one
hook output per delivered artifact rather than one for the whole method, and every future delivered
artifact must be measured and gated — adding one is a deliberate act with a CI cost, which is the
point.

The cost is that the split has to be maintained: a rule stated on both a role source and `core.md`
is a duplicate that no compiler will find, and the sweep discipline is the only thing that catches
it.

**Amendment (2026-09-11, see 0056):** 0056 extends per-artifact delivery to Codex with the same core
and orchestrator sources plus a bounded adapter. Shared startup/clear/compact matchers remain; the
adapter also runs on resume and requires reads of missing shared sources. An explicit recovery skill
is the no-skill clause's narrow exception, never the automatic-delivery mechanism. Native Codex
workers receive their full role in the dispatch receipt; they receive SubagentStart, not the main
SessionStart context. CLI child role markers suppress orchestrator startup context. Every delivered
artifact remains budget-gated.

**Amendment (2026-09-29, see 0063):** 0063 removes the Codex per-artifact delivery, its adapter, the
recovery-skill exception and native Codex workers. Delivery is the Claude hook's alone; a Codex CLI
worker receives its role in the dispatch brief, and a CLI child's `DEVSTANDARD_ROLE` marker still
suppresses orchestrator startup context wherever the hook runs.

**Amendment (2026-10-05, see 0064):** the carriers change; the decision does not. The orchestrator's
role arrives as a system-prompt section registered on the root agent's scope, and a worker's and a
reviewer's as the `persona` of their subagent row. Each role still receives one delivered artifact
rather than a pointer, and the host part-cap that shaped the old carrier no longer exists, so the
delivery is whole by construction instead of by arithmetic.
