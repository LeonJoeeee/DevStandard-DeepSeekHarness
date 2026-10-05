# 0063 — Claude Code is the only main session; Codex executes when dispatched

Status: Superseded by 0064 (2026-10-05). Originally Accepted (2026-09-29). Supersedes 0056. Amends 0006, 0007, 0008, 0011, 0015, 0016, 0018,
0019, 0022, 0024, 0035, 0036, 0038, 0039, 0040, 0045, 0046, 0047, 0049, 0051, 0052, 0059, 0060 and
0061 (their live Codex-host, delivery, routing and version-exemption clauses).

**Scope: this ADR decides what the method ships.** It removes a supported host.

## Context

ADR 0045 removed Codex host packaging during the collaboration rebuild; ADR 0056 restored it on the
human's request ([issue #342](https://github.com/LeonJoeeee/devstandard/issues/342)), with a Codex
plugin manifest and repository marketplace, a Codex branch of the SessionStart hook delivering the
orchestrator page and a bounded adapter, an explicit `devstandard` skill for hookless recovery,
native Codex worker receipts (`--implementation codex-native`), and real-CLI host qualification. A
real Codex-host lane later ran end to end.

On 2026-09-29 the human ruled the host out again
([issue #459](https://github.com/LeonJoeeee/devstandard/issues/459)): as a main session Codex does
not align with the method — given the full instruction set, it follows its own harness and logic
instead — so hosting it is not worth carrying. That is the human's direction, not a regression to
litigate. What the ruling keeps is Codex as a dispatched executor: a Claude Code orchestrator
launching `codex exec` for a worker or a read-only gating review, which never depended on the host
packaging.

## Decision

Claude Code is DevStandard's only main session. Everything that existed only so Codex could host the
method goes; everything a Claude Code orchestrator needs to dispatch Codex stays.

**Removed:** `.codex-plugin/`; the repository marketplace under `.agents/plugins/`; the Codex branch
of `hooks/session-start` with its cap, its handler set in `hooks/hooks.json`, the per-handler host
argument that chose between the two sets and the `additionalContextLimit` key #389 added for the
Codex host; the `devstandard` skill, which existed for hookless recovery on that host — Claude Code
also discovered it, but there it only pointed at the role pages SessionStart already delivers; the
host-facing content of `reference/harness-codex.md` — its context delivery, native workers, hook
trust and resume trigger; the `--implementation codex-native` dispatcher path and its
`native-spawn.json` receipt; the Codex-host tests `test-codex-plugin.py`, `test-codex-native.py` and
`test-codex-install.py`, and the host cases of `test-codex-runtime.py`. A Codex environment running
the hook — `PLUGIN_DATA` alone or with an equal-valued Claude alias — is an unsupported environment
again, with the visible warning 0045 gave it, stated once; a dispatched role's `DEVSTANDARD_ROLE`
silences the hook in any environment.

**Kept:** `--implementation codex` for workers and read-only gating review; its OS sandbox, the
fixed role hook it runs under `--dangerously-bypass-hook-trust` and the orchestrator's duty to vet
the invocation-wide hook sources that bypass reaches; MCP admission; `--wait` and the supervisor's
lock and completion marker; `guard codex-config`; superpowers installed into Codex, where a Codex
worker's craft bindings resolve; the Codex worker-mechanics section
`scripts/dispatch` appends to a Codex CLI brief; and the Codex executor cases of
`test-codex-runtime.py`, which still gate the aggregate `test` check. `reference/harness-codex.md`
stays as the page a Claude orchestrator reads for Codex CLI mechanics, plus that marked worker
section. The Model and effort section's table and values are unchanged; routing is re-decided
separately.

**Two judgment calls stay as they are.** The role hook's fallback that gives a child event carrying
`agent_id` but no agent type the worker list was added for native Codex children; it stays, because
removing it could only loosen the guard for an untyped child event. And the dispatcher still reads a
recorded `codex-native` run as a native record, so a lane recorded before this change never blocks
its own continuation or cleanup.

The release manifests are the two Claude ones. The CI lockstep gate, the guard's bare-bump waiver
and its rebase exemption cover exactly those two version fields, with the same equal-version,
mode and ordering checks.

Rejected: keeping the host packaging unmaintained beside the executor path. A host the method no
longer supports would still be discovered, hooked and read, and its qualification would still cost
CI on every change.

## Consequences

Target projects run the orchestrator in Claude Code only; the version is 2.0.0, a major release,
because a supported host is removed. A Codex installation of an earlier release keeps working until
it is uninstalled; nothing here edits a user's Codex configuration. Codex lanes launched from Claude
Code are unaffected.

The Codex CI job, on Ubuntu and macOS, keeps the Linux sandbox prerequisites, the pinned CLI and the
executor cases — the role hook, the dispatched brief reaching the model byte for byte, MCP admission
per sandbox mode — plus the hook-delivery, dispatch and review-packet suites on each runner's own
shell. Its install, native-spawn and package steps go.

ADR bodies stay as written. Dated amendment blocks reconcile the live statements 0056 and its
amendments left routing a reader to a Codex host, to `codex-native`, to the adapter or to a third
manifest. 0045's removal is history; this ADR decides the removal again rather than reviving 0045.
Rollback is a reviewed revert of the implementing PR.
