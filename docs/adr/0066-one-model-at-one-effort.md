# 0066 — Every dispatched role runs one model at one effort

Status: Accepted (2026-10-05). Supersedes 0050.

## Context

ADR 0050 routed model and effort by kind of work: it retired the tier cap of 0024, named a per-harness
tier vocabulary, and — as amended on 2026-09-19 — anchored the worker and the reviewer to fixed rows
while leaving a helper table for one-off subagents. `scripts/hard_edges.py` read those rows out of
`reference/orchestrator.md`, so the two harnesses' model names lived in the page and the machinery
parsed them from there.

The owner's constraint for this repository is one model everywhere: **DeepSeek V4.1 Flash at max
effort**, through the local gateway dsh is already wired to. dsh has no tier vocabulary at all — a
model identity is `(provider, exact model id, reasoningEffort)`, with effort from `off | low | high |
max` and no opus/sonnet analogue to name.

## Decision

One anchor. The two subagent rows carry
`agentOptions: {model: <the anchored model>, reasoningEffort: max}` in the bundle's `cordis.patch.yml`,
and that is the only site. There are no tiers, no per-kind routing, and no helper table: every
dispatched role, the reviewer included, takes the same route.

The orchestrator's own model is not anchored — it stays the session default the human picks, as the
method already says.

## Consequences

`hard_edges.py`'s model readers shrink from two tables to one anchor, and the per-harness column
disappears with the second harness. The routing rule's remaining content — that a role never runs
below the tier that produced the work — is vacuous when there is one tier, so it leaves the page
rather than staying as a rule with nothing to decide.

Raising or lowering the anchor later is a one-line change in one file, which is the point: the
scattered routing this supersedes existed to express choices this repository does not make.
