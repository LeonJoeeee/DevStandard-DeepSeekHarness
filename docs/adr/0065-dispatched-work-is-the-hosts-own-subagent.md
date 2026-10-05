# 0065 — Dispatched work is the host's own subagent, and its isolation is the worktree

Status: Accepted (2026-10-05). Amends 0036 (the executor set narrows to the host's own subagent; its
never-lower-the-gate fallback stands).

## Context

The method dispatched to three implementations: Claude-native subagents, Codex CLI processes, and
Claude CLI worker processes (ADR 0040 as amended by 0063). The two process implementations existed
for what a native subagent could not give: a detached run that outlives its invoking session, and —
for the reviewer — an OS read-only sandbox. A Codex worker also carried a filesystem sandbox scoped to
its lane.

The owner's constraint for this repository removes the Codex machinery entirely and directs dispatch
to the harness's own subagent mechanism, with nothing external. dsh's native subagent is a composition
row: `dsh-tool-subagent` with `provider: spawn`, a fixed `agentOptions` route, a `persona` and a
`toolFilter`, and — for a continuable child — the `send_message` control tool against its id.

## Decision

One implementation. Two rows, `toolName: worker` and `toolName: reviewer`, both `provider: spawn`,
`backgroundMode: continuable`. A continuation is `send_message` against the child id the tool returned
— the native replacement for the recorded Agent handle. The CLI executor, its detached supervisor,
its sandbox arguments, the `--implementation` selector, and the `--reconcile-lost` machinery that
existed to resolve a detached process whose exit could not be observed, are all removed.

**The cost is named, not hidden.** An in-process child inherits the session's permissions and cwd, so
there is no per-worker OS sandbox. Lane isolation is now three things: the worktree, the role guard,
and independent review. A reviewer's read-only posture survives at the same tier it has on the Claude
Code sibling — the row's `toolFilter` removes the write tools from its prompt and rejects their
execution — but it is a tool-level denial, not an OS sandbox.

Rejected: **a `dsh --profile headless` process as a second executor.** It would restore an OS boundary
and a detached run, at the price of reinstating exactly the permission surface and supervisor lifecycle
the native mechanism removes, and against the owner's direction to use the built-in mechanism only.
Rejected: **`provider: fork`**, which seeds the child with the parent's completed conversation — a
worker must start from its brief, not from the orchestrator's history.

## Consequences

A lane's lifecycle simplifies: a child's end is observable at the tool boundary, so lost-run
reconciliation loses its reason to exist. What the superseded CLI path proved — detached survival, a
scoped sandbox — is not replaced and is not claimed.

If a future dsh exposes a per-child sandbox, restoring the boundary is a change to two rows, not to
the dispatch protocol; the ADR to write then is a new one, not an edit of this.
