# DevStandard, delivered natively for DeepSeek Harness

Status: accepted

## Problem & context

This repository is the DevStandard method delivered natively for **DeepSeek Harness (dsh)** as the
main session. It begins as a full copy (content + git history) of `LeonJoeeee/devstandard` — the
Claude Code project — and is adapted here; the two are separate siblings and never synchronize back
([issue #1](https://github.com/LeonJoeeee/devstandard-dsh/issues/1)).

Everything in the copy that names a host binds the method to a harness this repository does not run
on: `agents/*.md`, `hooks/hooks.json`, `.claude-plugin/`, `reference/harness-claude.md`,
`reference/harness-codex.md`, the executor halves of `scripts/dispatch`, and the two model-tier
tables. Two owner constraints bound the port: **remove all Codex-dispatch machinery** (dispatch uses
the harness's own subagent mechanism only), and **one model everywhere** — DeepSeek V4.1 Flash at max
effort.

The method itself — the collaboration protocol, the three roles, the review contract, the worktree
lifecycle, the issue/PR discipline, the ADR log — is host-agnostic and survives. ADR 0061's shape
(one worker contract, one mechanics page per harness) is the template the port mirrors, reduced to
one harness.

A read-only probe of the installed dsh 0.2.0-rc.2 (conclusions below; full record published on
issue #1) established what the port may build on. Its single most consequential finding is negative:
**a subagent row's `toolName` is not carried onto the child**, so the role guard cannot select its
word list by the child's role — see Decision (d).

### Probe conclusions (dsh 0.2.0-rc.2, installed tree)

- **Role delivery.** `ctx.systemPrompt.section({name, order, text, complete?})` is scope-derived: a
  section registered through `agent.ctx` reaches that agent, one registered globally reaches every
  agent. A plugin may listen on `agent/created` — awaited before the first turn — and register on the
  root agent alone, reading root-vs-child from `agent.session.header` (`origin: 'subagent'`,
  `delegationDepth`). `text` may be a function, so the page can be read from the package at load.
- **Subagents.** `@deepseek-ai/dsh-tool-subagent` rows take `toolName` (distinct per instance, so
  `worker` and `reviewer` are two callable tools), `provider: spawn`, `backgroundMode: continuable`
  (gives `send_message`/`interrupt_agent`/`list_agents`), `agentOptions {model, reasoningEffort}`,
  `toolFilter {allow?, deny?}` (removes tools from the prompt *and* from execution), and `persona` —
  **inline text only, not a file reference**. `spawn` and `fork` support all five capabilities;
  `fork` seeds the child with the parent's conversation, so it is wrong for a worker. Only `spawn`
  and `fork` are registered in this install.
- **Interception.** `tools/pre-execute` is `(exec, next) => PreToolDecision` with
  `{kind:'allow'|'deny'|'cancel'|'ask'}`; `exec` carries `name` (the concrete tool), `arguments`, and
  `agent`. The shell tool is `bash`, so a command is `exec.arguments.command`. Built-in tool names
  are lowercase: `bash`, `read`, `write`, `edit`, `str_replace_editor`, `glob`, `grep`.
- **Packaging.** A bundle is an npm package whose `package.json` declares
  `dsh.bundle.patch → ./cordis.patch.yml`; rows reference the plugin **by package name**; `index.js`
  exports `apply(ctx, config)`. `personaPrefix`/`personaSuffix` and the hook bridge exist but are not
  used here (Options 1–2).
- **Correction to the prior survey.** The Claude Code hooks bridge **does** consume `SessionStart`'s
  JSON `additionalContext` (the community claim that it is ignored is refuted by its source). It
  remains the weaker carrier: its handler runs detached and can miss the first request.

## Options considered

1. **Reuse the Claude Code hooks bridge** (`dsh-hooks-claude-code`) — the existing `hooks.json` and
   its part-split delivery would run nearly unchanged. Rejected: the role text can miss the first
   request, and the issue asks for the method delivered natively, not through a compatibility shim.
2. **Deliver the role through the `AGENTS.md` chain** (`dsh-agent-instructions`) — no code at all.
   Rejected: that chain is injected **per agent and per session**, so it also lands in every
   dispatched child, and it is capped by `maxBytes`; it cannot be scoped to the root alone.
3. **A native bundle: plugin rows for role delivery, the two role subagents, and the guard** — chosen.
   It is the only option that gives the root alone its role, fixes the workers' model and effort and
   their tool surface, and keeps the guard's own word lists where ADR 0052 put them.

## Decision

Ship **one dsh bundle** whose rows supply the three surfaces the method needs, and keep the method
prose as the bundle's own `reference/` files.

**(a) Package.** A `package.json` declaring `dsh.bundle.patch → ./cordis.patch.yml` and an `npm files`
list; one plugin module (`index.js`, exporting `apply`) referenced by package name; the shipped
`reference/` pages; the ported skills under `skills/`; the git+gh machinery under `scripts/`.
Installed locally into a profile for now (a future publish is `dsh plugin add`, no rework). Nothing
publishes to a registry in this change.

**(b) Role delivery.** The plugin registers one system-prompt section carrying
`reference/orchestrator.md`, **on the root agent's scope only**: it listens on `agent/created` and
registers through `agent.ctx` when the created agent is top-level, reading the page from the bundle
at load. The section is named `devstandard:orchestrator` and ordered after the deployment persona
prefix, so the harness identity and the deployment persona still open the prompt. The 16-part split
disappears: there is no per-output persistence cap to fit, and the page is delivered whole.

**(c) The two role subagents.** Two `@deepseek-ai/dsh-tool-subagent` rows — `toolName: worker` and
`toolName: reviewer`, both `provider: spawn`, `backgroundMode: continuable` — each with:

- `agentOptions: {model: <the anchor>, reasoningEffort: max}` — the port's single model site (e);
- `persona`: the role page's text, **generated into the row** from `reference/worker.md` and
  `reference/code-review-prompt.md`, because the field is inline-only. A CI gate asserts the embedded
  text is byte-identical to its source page — the successor to `check-agents.py`'s byte-identity
  check, keeping one operative source per role;
- `toolFilter: {deny: ['write','edit','str_replace_editor']}` on the reviewer, mirroring the sibling
  project's reviewer denial (`agents/reviewer.md`'s `disallowedTools`) with dsh's tool names. This is
  a **hard** mechanism — the tool leaves the prompt and rejects execution — not a word scan.

A worker is continued with `send_message {agent_id}` — the native replacement for the recorded
subagent handle. `maxDepth` stays at the host default, so a worker cannot itself delegate; that
matches "one accountable author per lane" (ADR 0055).

**(d) The guard.** The plugin listens on `tools/pre-execute` and reuses `scripts/hard_edges.py`'s word
engine unchanged in its policy: the same three words ADR 0062 cleared (a worker's `merge`, the
orchestrator's `gh pr merge`, a reviewer's `gh api` write flags) plus the worker default-branch push
that branch protection takes over. Only two things change: the tool names become dsh's (`bash`), and
the command text comes from `exec.arguments.command`.

**Named risk.** `exec.agent.session.header` yields root-vs-child but **not** the spawner row, so the
guard cannot at first distinguish a worker's legitimate work from a reviewer's. The design therefore
splits the rules into a root tier and a child tier, and the child tier is the worker-and-reviewer
union until probe 2 (below) restores the exact split. The union costs a worker nothing the method
relies on — the reviewer's write refusal is carried hard by `toolFilter` — and if probe 2 cannot
restore it, that widening is recorded in ADR 0062's amendment rather than hidden.

**(e) The model anchor.** One site: the two rows' `agentOptions` in `cordis.patch.yml`. The
orchestrator's own model is the session default the human picks, as the method already says. The two
tier tables, the Codex column, the helper table's Codex column and the per-kind routing all collapse
to this one anchor; `scripts/hard_edges.py`'s model readers shrink to reading it.

**(f) Scripts.** `scripts/dispatch` keeps its git and gh machinery — issue fetch, lane creation and
records, brief assembly, continuation, cleanup — and loses both executor branches. It emits one
native instruction: call the `worker` tool with the assembled brief, and record the returned child
id. Continuation becomes `send_message`; `--reconcile-lost` simplifies, because an in-process child's
end is observable at the tool boundary rather than by a detached supervisor's marker.
`scripts/review-packet` keeps assembly, publication and round accounting and loses
`--implementation codex`. `scripts/guard` keeps `compare`, `protection` and `merge` and loses
`codex-config`. `scripts/review_packet.py`'s manifest lockstep moves from the two `.claude-plugin`
files to the bundle's `package.json`.

**(g) Reference prose.** `reference/harness-codex.md` is deleted; `reference/harness-claude.md`
becomes `reference/harness-dsh.md` (ADR 0061's shape, one harness). `reference/orchestrator.md`,
`reference/worker.md` and `reference/code-review-prompt.md` keep their protocol text and have their
host surface replaced: dispatch and continuation, the model anchor, the delivery mechanism, the
guard's carrier, and the reviewer's identity examples. `reference/repo-claude-md.md`'s rule becomes
the host's repo-root instructions file — dsh reads `AGENTS.md` and `CLAUDE.md` in one chain, and
because that chain is per agent a dispatched worker receives the project's file too, which the method
wants.

**(h) CI.** The Codex job and `test-codex-runtime.py` are deleted. `check-agents.py` becomes the
bundle gate: `package.json`'s `dsh` block, every row's required fields, the `agentOptions` anchor,
the skill frontmatter, and the byte-identity of each embedded persona against its source page. The
Claude runtime job becomes a dsh job driving `dsh --profile headless` against a local deterministic
OpenAI-compatible endpoint, asserting that the root prompt carries the orchestrator page, that a
child carries its own role and not the orchestrator's, and that the guard refuses each role's word.

**(i) Decisions recorded.** Four new ADRs, claimed at 0064 and carried in this PR with the spec, as
issue #1 requires before any implementation: **0064** this repository delivers DevStandard natively
for DeepSeek Harness (supersedes 0063; amends 0018, 0049, 0060, 0061, 0062); **0065** dispatched work
is the host's own subagent, with the lost per-worker OS sandbox named (amends 0036); **0066** every
dispatched role runs one model at one effort (supersedes 0050); **0067** the bound superpowers craft
is ported into the package (supersedes 0016). Dated amendment blocks, not new files, wherever the
decision stands and only its carrier moved.

### Probe 2 (before implementation, small and deterministic)

1. Does a section registered on the **root** `agent.ctx` reach a spawned child? The scope service's
   documentation says child scopes inherit ancestors; the system-prompt service's says a
   contribution "affects that agent alone". If it inherits, the child's scope gets a same-named
   shadow so the worker never receives the orchestrator page.
2. Does `subagent/start` carry the child's id together with the row's `persona` or `label`, so the
   guard can map child→role? If it does, the child tier splits back into worker and reviewer rules.

Both answers change (b) and (d) only in mechanism; neither changes the shipped shape.

## Out of scope

- Publishing the bundle to a registry, and installing it anywhere but a local profile.
- Any per-child OS sandbox. The Codex path gave a worker one; the native path inherits the session's
  permissions. This is a real loss, named in the dispatch ADR, not a gap to close by reintroducing a
  CLI executor.
- dsh Workflows and Scheduled Dispatch; the former is unused by this method, the latter cannot mount
  headless. MCP has nothing to port.
- The Claude Code sibling repository, its ADRs, and any push back to it.

## Verification

Machine-judgeable, and the issue's done-check derives from it:

1. **Role delivery:** a fresh `dsh --profile headless` run against the deterministic endpoint, with
   the bundle composed, shows `reference/orchestrator.md`'s bytes in the root request and **absent**
   from a spawned worker's request, which instead carries `reference/worker.md`.
2. **Guard:** the same run, or a `tools/pre-execute` probe, refuses `gh pr merge` at the root,
   refuses `merge` and a default-branch `push` in a worker, and leaves an ordinary command allowed.
3. **End to end (the demo):** one real task under dsh on this machine — issue → lane → a built-in
   `worker` subagent (V4.1 Flash at max) → PR → an independent `reviewer` → guarded merge → cleanup —
   with the evidence recorded on the issues. Run in an interactive profile under `workspace-write`
   with approvals answered by the human; the worker is in-process and inherits the session's
   permissions.
4. **No Codex residue:** a grep over the shipped pages and scripts, **the ADR log excluded**,
   finds no Codex-dispatch reference. The exclusion is the point, not a convenience: the log
   ships inside the bundle and recording Codex's removal is what this port asks it to do, so a
   grep that counts its own record proves nothing. Issue #1's Done-check wording is read the
   same way.
5. **CI green** on the port PRs, including the bundle gate and the dsh runtime job.

## Failure detection & rollback

This repository ships no runtime state and nothing else depends on it, so detection is the CI gates
above plus probe 2, and rollback is reverting the offending PR or simply not composing the bundle
into a profile. The one change that is costly to undo is the ADR set: the port ADRs supersede
established decisions, so they land with the design PR and, if the direction changes, are superseded
by a later ADR rather than edited — the log's own rule.
