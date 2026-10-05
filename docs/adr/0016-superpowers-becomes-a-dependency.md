# 0016 — superpowers becomes a dependency: point at its skills, don't copy them

Status: Superseded by 0067 (2026-10-05). Originally Accepted (2026-07-16). Amended by 0045 (2026-09-05). Supersedes 0002. Amended (2026-07-16). Amended by 0039 (2026-08-26). Amended by 0049 (2026-09-07). Amended (2026-09-07). Amended by 0056 (2026-09-11). Amended by 0063 (2026-09-29).

## Context

0002 made superpowers a quarry: port the best pieces with attribution, never install it in the final environment — set when the plan was to eventually replace it. A month of lived reality says otherwise. The human runs Claude Code + superpowers + DevStandard together in every session and has declared that arrangement permanent ("the three are siblings — they always appear together"). superpowers is actively maintained upstream (installed: v5.1.0), while our two copied technique files (`aids/testing-anti-patterns.md`, `aids/debugging-techniques.md`) froze at their port date and silently drift. And the layering has clarified: Claude Code provides the mechanics (sessions, tools, agents), superpowers provides the per-step craft (how one agent does one job well), DevStandard provides the method (how a team of agents runs a project) — a layer wrapped around the other two.

## Decision

**Declare the dependency.** DevStandard assumes Claude Code and superpowers are installed alongside it, and its documents point at superpowers skills by name. A pointer is plain text naming the skill to use at a step; the agent invokes the skill itself — DevStandard executes nothing on its behalf.

- Four pointers (names verified against installed v5.1.0): pinning down requirements with the human → `superpowers:brainstorming`; a bug task → `superpowers:systematic-debugging`; implementation guarded by tests → `superpowers:test-driven-development`; an issue/spec written for a context-free worker → `superpowers:writing-plans`.
- The two copied technique aids are deleted — the live skills replace them. `aids/code-review-prompt.md` and `aids/worktree-lifecycle.md` stay: they are DevStandard's own protocol (adapted with attribution), not duplicated craft.
- Two guards carry over from 0002's reasoning:
  1. **Sovereignty and chain-cutting.** A skill serves inside one step of this flow, and every pointer says "then return to this flow" — superpowers skills chain to each other ("next, use skill X") and would otherwise pull the agent into superpowers' own pipeline. On any conflict, DevStandard's page wins; the 12-entry conflict register in `_source/superpowers-porting-plan.md` still maps where the conflicts live. This sovereignty rule — not the never-point list — is also what neutralizes the hazards the pointed-at skills themselves carry (announce boilerplate, their own artifact paths, universal tests-green framing).
  2. **A never-point list.** Skills whose territory DevStandard owns are not pointed at: worktree setup/teardown and branch finishing (superpowers keeps worktrees after PRs; our merger deletes them), the code-review pair (merge check 1 has its own protocol), and its dispatch/router skills (announce boilerplate, a universal tests-green gate, ask-anytime).

Rejected: conditional "if superpowers is installed…" pointers with the copies kept as fallback — that preserves a standalone mode nobody uses, at the price of permanent duplication and drift.

## Consequences

Leaner (two copies deleted; upstream improvements now flow in live) and honest about the real environment. Costs: DevStandard no longer works standalone — the README declares the requirement, and the plugin system cannot enforce it; an upstream rename or content change can dangle a pointer or sharpen a conflict — daily dogfooding catches it, and the conflict register is the guard. 0002's porting plan keeps earning its place as the map of what to point at and what to keep away from.

**Amendment (2026-07-16, see `_source/superpowers-coupling-map.md`):** a full coupling survey of all 14 skills plus the non-skill layer refined the pointer placement — the four pointed-at skills are unchanged, but `writing-plans` moved from core.md to `howto/design-spec.md` (its craft matches the design-spec step; issue-writing stays low-on-how), `brainstorming` gained a step-local redirect in `howto/architecture.md`, and prd.md's inline restatement of the interview craft was deleted (the pointer carries the how). The survey confirmed the never-point list and added a hazards register for upstream drift.

**Amendment (2026-08-26, see 0039):** "assumes Claude Code installed alongside" widens to "a
supported harness — Claude Code or Codex". The superpowers dependency decision itself is unchanged;
on a harness without those skills, the mappings page routes each pointed-at step to its substance.

**Amendment (2026-09-05, see 0045):** The 0039 amendment's Codex host assumption and mappings-page fallback are retired. DevStandard is installed alongside superpowers in Claude Code; dispatched workers use the execution-skill triggers in `reference/worker-brief.md`. The superpowers dependency and step-local sovereignty remain.

**Amendment (2026-09-07, see 0049):** the pointer placement this ADR and its 2026-07-16 amendment
fixed moves with the role split. Each role's skill bindings are stated once, on that role's own
operative source; `core.md` carries only the trigger and the rule that the agent returns to this
workflow afterwards. The dependency itself, step-local sovereignty, and the never-point list are
unchanged.

**Amendment (2026-09-07, issue #279):** the 2026-09-05 block's *"dispatched workers use the
execution-skill triggers in `reference/worker-brief.md`"* names a page #235 reduced to a
compatibility pointer and #270 deleted. The triggers live on `reference/worker.md`, in the fenced
worker-skills block that `.github/check-agents.py` checks the Claude agent definition against, and a
Codex executor receives them in its dispatch brief. Per 0049 each role's bindings are stated once on
that role's own source: `reference/orchestrator.md` for the orchestrator's, and the reviewer's set is
empty by design. The dependency, step-local sovereignty and the never-point list are unchanged.

**Amendment (2026-09-11, see 0056):** The 0045 block's Claude-only host assumption is retired by
0056. Install superpowers on either executing host and resolve its skills from the existing role
bindings. The Codex adapter maps access to those installed skills; it does not copy craft or revive
a substance-only replacement. Dependency, step-local sovereignty and the never-point list remain.

**Amendment (2026-09-29, see 0063):** 0063 removes the Codex host and its adapter, not the
dependency on either executing host. Superpowers is installed alongside DevStandard in Claude Code,
and into Codex wherever Codex workers are dispatched: a Codex CLI worker receives its role's skill
bindings in the dispatch brief and resolves those skills from Codex's own roots. `README.md`'s
Install section carries the Codex commands. Dependency, step-local sovereignty and the never-point
list remain.
