# 0061 — One worker contract, one mechanics page per harness

Status: Accepted (2026-09-19). Amends 0056 (shared role sources) and 0060 (the definition body). Amended by 0063 (2026-09-29). Amended by 0064 (2026-10-05).

**Scope: this ADR decides what the method ships.** It splits the worker role into a shared contract
and one mechanics page per executor family (#409); `reference/worker.md`,
`reference/harness-claude.md` and `reference/harness-codex.md` carry the operative wordings, and
this record carries the reason.

## Context

One worker role is dispatched four ways: a Claude built-in subagent, a Claude CLI process, a Codex
native child and a Codex CLI process. ADR 0056 made them share one role source and ADR 0060 made
that source arrive without a read. Neither decided what to do with the parts of the role that are
not shared, so they accumulated on the one page every executor is delivered.

The #409 audit measured what that cost. `reference/worker.md` carried the Claude nonce-and-grep
lookup over `~/.claude/projects`, the Codex-native impossibility clause, the `codex exec` sandbox
sentence and the session-persistence precondition — mechanics a worker can act on only if it is
running on the harness they describe. Every other worker pays their tokens once per dispatch and
must first work out which of them is about its own host. A Codex worker reading the Claude lookup
has no records to grep; a Claude worker reading the `codex exec` clause has no sandbox.

The audit also found the one thing that must not be sunk behind a pointer: a worker recovering a
lost binding has lost the packet field that resolves `reference/` paths, so the lookup it needs has
to be resident in what it is already holding.

## Decision

**`reference/worker.md` is the shared contract and carries no executor-specific mechanics.** A
sentence a worker must obey lives there; a sentence describing how a harness behaves lives on that
harness's page. One resident trigger replaces the mechanics it lost: *"Your harness page, delivered
with this one, says how you recover your binding, what you may spawn, and what your sandbox is."*

**Each executor family gets one mechanics page, and a worker is delivered its own and never the
other's.** `reference/harness-claude.md` is new and holds the built-in subagent's mechanics with a
subsection for the Claude CLI worker. `reference/harness-codex.md` keeps its host-facing content and
gains a marked worker-facing section for the Codex mechanics moved off the shared page.

**Each mechanics page rides a carrier that survives its executor's context loss.** On Claude that is
the agent definition body, so `.github/check-agents.py` now generates `agents/worker.md`'s body as
`reference/worker.md` followed by `reference/harness-claude.md`, concatenated byte for byte, and
checks it. Codex has no such carrier — a native child gets SubagentStart and a CLI child runs with
`DEVSTANDARD_ROLE` set, so the session-start hook delivers it nothing — so `scripts/dispatch`
appends the marked Codex section to the brief for `codex` and `codex-native`. The Codex host's
session-start delivery of the whole adapter is unchanged.

**The hard rule that keeps this from becoming four drifting files again: a harness page carries
mechanics only, never rules.** The pre-fold state ADR 0059 ended — several pages restating each
other — returned as drift every time a rule lived in more than one place. Only the dispatcher's
process-run receipt lookup is stated on both mechanics pages, because both families have a CLI
process worker and neither can be handed the other's page to find it.

Rejected: a third file for the Codex worker section, which would have made two Codex pages against
this decision's one-per-family shape; and leaving the mechanics on the shared page behind per-harness
conditionals, which is what the audit measured the cost of.

## Consequences

A worker's system prompt no longer describes a host it is not running on, and the pages that do
describe its host are the ones it is holding. The measurable part of that is per dispatch, not per
session: `reference/worker.md` is not a session-start artifact.

The Claude worker now pays for two pages at spawn instead of one, and the Codex worker for the
contract plus one section. That is the same total text as before, minus the other family's share.

Two carriers now have to stay in step rather than one, and both are gated: `.github/check-agents.py`
fails on a body that is not the exact concatenation, and `scripts/dispatch` refuses a
`reference/harness-codex.md` whose worker-facing markers are missing, duplicated or empty. The
runtime tests assert what reaches each model: `.github/test-claude-runtime.py` that both pages and
their concatenation arrive byte-identical in the host's own request and that neither harness's
mechanics reach the brief, `.github/test-codex-native.py` and `.github/test-codex-runtime.py` that
the contract and the Codex section reach the child and the Claude page does not, and
`.github/test-dispatch.py` that the three implementations differ in exactly that way.

The within-page repetition the same audit found is deliberately untouched here, so a reviewer can
tell a deliberate cut from a lost sentence. This change moves sentences; it removes none.

Rollback concatenates the two pages back into `reference/worker.md` and restores the single-source
generator, through a reviewed revert.

**Amendment (2026-09-29, see 0063):** 0063 strips the host-facing content from
`reference/harness-codex.md`: it now maps the Codex CLI executor for the dispatching Claude Code
session and keeps the marked worker section, which dispatch appends for `--implementation codex`
alone. There is no `codex-native` path and no Codex session-start delivery of the page;
`.github/test-codex-native.py` is deleted, and `.github/test-codex-runtime.py` still proves the
contract and the Codex section reach the child. The one-contract, one-mechanics-page split stands.

**Amendment (2026-10-05, see 0064):** the shape stands, with one harness instead of two. The single
mechanics page is `reference/harness-dsh.md`; `reference/harness-codex.md` is deleted and
`reference/harness-claude.md` becomes that page, because this repository's host is dsh alone.
