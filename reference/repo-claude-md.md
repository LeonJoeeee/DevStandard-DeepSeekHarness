# The repo-root instructions file

CI settles the project's commands — capture them while they're fresh: generate a repo-root instructions file — when there is something to put in it (below), as admitted by `reference/in-repo-writes.md` — one page hard max. The host reads `AGENTS.md` and `CLAUDE.md` in one chain and injects it per agent, so it is the one place operational facts reach every agent automatically, a dispatched worker included. Write it as `AGENTS.md`; a project that already keeps its instructions in `CLAUDE.md` is read through the same chain and needs no rename. Three kinds of content — plus one conditional fourth, and nothing else:

**The repo-root instructions file stays the operational-memory file on every harness.** The main session and every dispatched worker read it, because the host injects the chain into each agent (`reference/orchestrator.md` and `reference/worker.md`). Write discoveries back here through the PR, keeping each operational fact at its established source. Do not duplicate this memory or install a managed method block in the chain.

- **Commands** — install, test, run (the same ones CI just encoded);
- **Environment gotchas** — ports in use, services that must be up, local-vs-CI differences;
- **Untracked files a new worktree must copy** — the allowlist `reference/orchestrator.md`'s Worktree lifecycle section copies from (`.env`, keys, local config).

A cache or deploy root outside the tree is an environment gotcha of exactly this kind only when the
root itself already existed as an authority for this project's files or the human chose it. Recording
that place relays the authority so a clean-context worker does not invent another
(`reference/where-it-goes.md`); an instructions-file line added in the same change never authorises a
root the change invented. It belongs under Gotchas, not as a new kind of content.

One conditional fourth item — the fence's only exception: a `## Record language` line, when the repo's durable record is not English. It sits here because a clean-context worker must see it natively; the reasoning behind the choice goes in that repo's ADR log, not here. Its absence means English.

A repo-wide language declaration in the root instructions file overrides English for the whole record,
never per file or per agent. An established non-English record earns that declaration: write it
and follow the existing record, never start a mixed record. A human-facing translation is a marked
mirror naming its canonical file and changes in the same diff as that file.

Generate it only when the project actually has some of that to say. A file that merely transcribes what CI already encodes, or that would stand empty under every heading with no record language to declare, is noise every later session pays to read — skip it, and let the first real command, gotcha, copy-list line or record-language declaration create it through the same write-back lane.

It grows one line at a time: whoever merges a task that exposed a command, environment gotcha, worktree copy-list entry, or record-language declaration writes it back (the worktree checklist's Death step) through a short-branch PR like any other change. The writer enforces the 30-line cap (roughly twice the template below) at write time: a write-back that would cross it also drops the line it most clearly supersedes, or otherwise the stalest gotcha — never a separate cleanup pass. Architecture, decisions, rules, and task state never go here — the template's last line is the fence.

```markdown
# <Project> — repo notes for agents

## Commands
- install: <command>
- test: <command>
- run: <command>

## Gotchas
- <port / service / local-vs-CI difference worth one line>
- <cache or deploy root already assigned to this project or chosen by the human, e.g. ~/.cache/foo or /srv/app — this line relays that place; it does not authorise a root this change invented>

## New worktree: copy these untracked files
- <path>   (or: none — everything load-bearing is tracked)

Architecture: see docs/architecture.md — never duplicated here. Decisions: docs/adr/ unless the architecture doc points elsewhere. Tasks: GitHub issues.
```
