# 0060 — The agent definition body carries the worker role

Status: Accepted (2026-09-15). Amends 0059 (its Decision's carrier sentence for the default
Claude Agent path). Amended by 0061 (2026-09-19). Amended (2026-09-20). Amended by 0063 (2026-09-29). Amended by 0064 (2026-10-05).

**Scope: this ADR decides what the method ships.** It decides what carries a worker its role on
each host (#402); `reference/worker.md` carries the operative wording, and this record carries the
reason.

## Context

`reference/worker.md` holds the whole worker role. Four executors have to receive it, and until now
only three did. `scripts/dispatch` reads the page into the brief for `--implementation claude-cli`,
`codex` and `codex-native`, and `.github/test-claude-runtime.py` and `.github/test-codex-runtime.py`
prove those bytes reach the model byte-identical. The default `--implementation claude` — the host's
own subagent, which ADR 0040 as amended by 0056 makes the default on a Claude host — sent the task
packet alone. Its only carrier was `agents/worker.md`, which held a pointer: the resolved absolute
path of the role source and an instruction to read it IN FULL.

That pointer cost a turn and the tokens of a `Read` for content the harness could have carried, on
the path most dispatches take. It also could not be proven: `role_page_carrier` in
`.github/test-claude-runtime.py` recorded the carrier as *unproven*, because a deterministic fixture
can witness an instruction but never a model performing a read.

The page also carried four template slots — `{ISSUE_LINK_OR_SPEC}`, `{DONE_CHECK}`, `{BRANCH}`,
`{WORKTREE_PATH}` — which `scripts/dispatch` filled per lane. They duplicated values the task packet
already carries under `Issue`, `Branch` and `Worktree`, and inside its verbatim issue body under
`## Done-check`; the same section already required those values *from the packet*. They existed only
because the dispatcher filled them.

## Decision

**The Claude harness loads an agent definition's body as the subagent's system prompt, so the body
is the carrier.** `agents/worker.md` becomes hand-authored frontmatter plus a generated body that is
`reference/worker.md` verbatim. The role arrives with no read, and it survives compaction — the
dynamic packet does not, which is why the page keeps its recovery procedure.

**`reference/worker.md` stays the single hand-written source.** It is what `scripts/dispatch` reads,
what CI's invariant greps assert against, and what every prose citation names. The generated body is
checked, and regenerated, by an existing gate rather than a new script: `.github/check-agents.py`
asserts the body is byte-identical to the source and writes it in place under `--write`.

**The four template slots are removed.** A static system prompt cannot fill a slot, so keeping them
would put literal `{BRANCH}` placeholders in a Claude subagent's system prompt and fork the role text
per executor. Without them the page is identical for all four executors, which is the property this
decision is for.

## Consequences

Two carriers, one text. On the default Claude path the definition body is the page; on the three
dispatched paths `scripts/dispatch` writes the same page into the brief. `role_page_carrier` now
asserts what it used to disclaim — the page arrives byte-identical, exactly once, in the request the
host actually sent — for the CLI worker, the native Agent child, and the CLI worker that spawns a
native reviewer.

`agents/worker.md` no longer opens with a hand-written *"You are the DevStandard worker"* line,
because nothing hand-written survives in a generated body. Two things read that line and were
repaired in the same change: the runtime test's identity assertion, which for the worker is replaced
by the stronger byte-identical delivery assertion, and the local fixture's child-request detection,
which now matches the worker page's own opening declaration — the sentence `.github/workflows/ci.yml`
already pins. The reviewer is untouched throughout: its judging contract is assembled per PR with
filled slots and already rides the prompt whole, so its definition body stays hand-written and its
assertions stay as they were.

The compaction-recovery procedure that lived only in `agents/worker.md` — the nonce emitted through
a tool call and `grep -rl` over the host's conversation records — moves into
`reference/worker.md`'s Recover the binding section, where the pointer to `agents/worker.md` would
otherwise have become self-referential. Every executor now reads that procedure, and the one that can
use it is the one it names.

The cost is that `reference/worker.md` is now delivered to a Claude subagent in full at spawn rather
than on demand. That is the point: it is the same text the other three executors already received in
their brief, and it is what the CLI paths have always paid.

**Amendment (2026-09-19, see 0061):** This ADR's carrier holds; what it carries is now two pages.
`reference/worker.md` kept only the shared contract, and the Claude harness mechanics it used to
hold moved to the new `reference/harness-claude.md`, which has no other carrier to a Claude worker.
So the generated body is `reference/worker.md` followed by `reference/harness-claude.md`,
concatenated byte for byte with nothing between them, and `.github/check-agents.py` owns that rule
and fails on any other body. Both pages stay hand-written; the Decision's *"the body is
`reference/worker.md` verbatim"* reads as *"the body is its role sources concatenated verbatim"*.
The Consequences paragraph recording that the nonce-and-`grep` compaction lookup moved into
`reference/worker.md`'s Recover the binding is overtaken for its destination only: that procedure now
lives on `reference/harness-claude.md`, and Recover the binding keeps the trigger that sends a worker
to its own harness page. Nothing about delivery without a read, the removed template slots or the
reviewer changes.

**Amendment (2026-09-20, issue #411):** the Consequences carrier map — *"on the three dispatched
paths `scripts/dispatch` writes the same page into the brief"* — now covers two of them.
`--implementation claude-cli` launches `--agent devstandard:worker`, so the definition body was
already delivering the page as that process's system prompt while the brief prepended it as well,
and the worker received the role twice; the brief carries the task packet alone there now. Both
Claude paths therefore take the role from the definition body, and only `codex` and `codex-native`
take it from the brief. `role_page_carrier`'s assertion is unchanged in kind and now counts over the
whole host request rather than its `messages`, which is what lets it see the system prompt and prove
the single copy. The decision — the definition body is the carrier, delivered without a read — is
unchanged, and so is the Codex half of the map.

**Amendment (2026-09-29, see 0063):** 0063 removes `codex-native`. Only `--implementation codex`
takes the role from the brief — `reference/worker.md` plus the marked worker section of
`reference/harness-codex.md`; both Claude paths take it from the definition body.

**Amendment (2026-10-05, see 0064):** under dsh there is no agent-definition format to carry a body.
A worker's role is carried by the `worker` subagent row's `persona` text, generated from
`reference/worker.md` with a CI gate asserting byte identity — the same one-operative-source rule, by
a different carrier.
