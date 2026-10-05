# 0064 — This repository delivers DevStandard natively for DeepSeek Harness

Status: Accepted (2026-10-05). Supersedes 0063. Amends 0018 (the repo-root instructions file is the
host's), 0049 and 0060 (the carrier of every role), 0061 (one mechanics page, now for one harness)
and 0062 (the guard's carrier and its child tier).

## Context

The method was built for Claude Code and its shipped surface says so everywhere: an `agents/*.md`
definition format, a SessionStart hook that slices the orchestrator page into ordered parts against a
host persistence cap, a `.claude-plugin` package, a Codex mechanics page, and two model-tier tables
read out of the orchestrator page.

This repository is a full copy of that project adapted to run under **DeepSeek Harness (dsh)** as the
main session ([issue #1](https://github.com/LeonJoeeee/devstandard-dsh/issues/1)). The Claude Code
project continues unchanged; the two are siblings and never synchronize back. The protocol — the
roles, the review contract, the worktree lifecycle, the issue/PR discipline, the ADR log — is
host-agnostic and is what the port preserves. What it replaces is the host shell, in exactly the
shape ADR 0061 established: one worker contract, one mechanics page per harness. A read-only probe of
dsh 0.2.0-rc.2, recorded on issue #1, established the replaceable surfaces.

## Decision

Deliver the method as **one dsh bundle**: a package whose `package.json` declares `dsh.bundle.patch`,
a `cordis.patch.yml` of plugin rows, the shipped `reference/` pages as the bundle's own files, and a
plugin module that reads them.

The **orchestrator's role** is delivered as a system-prompt section registered from the
`agent/created` event **on the root agent's scope only**, reading `reference/orchestrator.md` from the
package at load. The part-slicing hook delivery, `hooks/` and `.claude-plugin/` are removed: the host
has no per-output persistence cap to fit, and its section mechanism carries the page whole.

The **repo-root instructions file** is the host's rather than Claude Code's. dsh reads `AGENTS.md` and
`CLAUDE.md` in one chain, per agent, so the rule names the file the host reads; `CLAUDE.md` stays a
name that host reads, not one the method requires.

Rejected: **the Claude Code hooks bridge** (`dsh-hooks-claude-code`), which would have reused
`hooks.json` almost unchanged — its handler runs detached and can miss the first request, and the
issue asks for the method delivered natively, not through a compatibility shim. Rejected: **the
`AGENTS.md` chain as the role carrier** — it is injected per agent and per session, so it also lands
in every dispatched child and cannot be scoped to the root alone.

## Consequences

A fresh dsh session receives the orchestrator page without a hook, a cap measurement or a part
reassembly, and a dispatched worker receives neither it nor the Claude page that no longer exists.

The `agents/` directory, the hook pair, the two plugin manifests and the part-budget gate all leave
the shipped set, and with them the CI checks that existed to police them. The method's own size
discipline survives as prose; the mechanical cap does not, because the host it measured is gone.

The bundle ships the method's prose as data the plugin reads, so a page edit is a package edit — the
rule that a role page is its own single source still holds, and the gate that proved it moves from
the agent-definition body to the embedded persona text.
