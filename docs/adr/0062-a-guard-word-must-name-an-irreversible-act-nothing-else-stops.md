# 0062 — A guard word must name an irreversible act nothing else stops

Status: Accepted (2026-09-20). Amends 0051 (the role lists, the re-spelling detour) and 0052
(release is not the hook's business). Amended (2026-09-20). Amended by 0064 (2026-10-05).

## Context

ADR 0051 cut the role hook to one word list per role and named the rule that made the cut: a guard
that cannot be complete guards the ordinary case, and the residual is accepted rather than chased.
It did not turn that rule on the lists themselves. Ten days later #379 did — an audit of every
enforced constraint in the method against one question, *would one sentence do?* — and its surface-1
inventory read each word against a keep-bar: **does this word name an act that is irreversible, and
that no other layer stops?**

Three words cleared it. Every other word failed in both directions at once: it refused work the role
does daily, and admitted the spelling that would actually have done the damage. Measured, not
argued:

- **`tag`** refused the local, reversible `git tag` while admitting `git push --tags`, which is the
  half that reaches a remote. #351 had already narrowed the word away from `--tags` and recorded the
  gap as behaviour.
- **`release`** refused `cargo build --release`, `pytest -k release` and `make release` — in every
  target project, not only this one.
- **`--force`** stranded a worker on the lease-protected force-push its own dispatch brief required
  (#236), and `reference/worker.md` still spells that command out.
- **`branch -D`, `branch --delete`, `push --delete`, `worktree remove`** name reversible acts on a
  disposable lane whose branch is already pushed, and no record has any of them firing on a
  defection.
- **The reviewer's whole list** — `push`, `merge`, `tag`, `release`, `delete`, `rm` — admits
  `gh pr comment`, `gh pr review --approve` and `gh pr edit`, probed. It never carried the
  independence its name claimed; `agents/reviewer.md`'s writer denial and the Codex `-s read-only`
  sandbox did.
- **The orchestrator's `git merge`** names a local, reversible merge, and it refused the audit's own
  probe and the `gh issue create --body` of #351.
- **The recursive-`rm` rule** refused `rm -rf node_modules`, `rm -r .tox` and every relative target,
  and carried a `/tmp/` carve-out — the only rule in the hook that read a command's targets rather
  than its words — to soften that.
- **The re-spelling detour** in every refusal existed to route around refusals the list should not
  have made.

The human ruled on 2026-09-20 (「同意」) on that inventory: the lists shrink to the three that clear
the bar, and the patches that existed only to soften their false refusals go with them.

## Decision

**The hook refuses three things and nothing else.**

| role | refuses | why it stays |
|---|---|---|
| worker | `merge` (`git merge`, `gh pr merge`) | an unreviewed squash to the default branch is irreversible, and `guard protection` configures no required review, so nothing else on the path stops it |
| orchestrator | `gh pr merge` | merging outside `scripts/guard merge` skips the reviewed-head check, the rebase proof and the green-checks read |
| reviewer | a `gh` command's `-X`, `--method`, `-f`, `-F`, `--input` | the one reviewer rule with a real target; read-only otherwise rests on `agents/reviewer.md`'s `disallowedTools` and the Codex `-s read-only` sandbox |

**One rule survives beside them, on borrowed time.** A worker `push` that also names `main` or
`master` is still refused. It covers the window before `guard protection --apply`, after which
GitHub refuses the push server-side; the human did not rule on it on 2026-09-20, and it is written
here so that the next reader knows it is a stopgap rather than a fourth principle.

**What is deleted** is every other entry in the three lists, the recursive-`rm` rule with its
`/tmp/` carve-out, and the re-spelling paragraph the refusal text carried. A refusal now has three
parts — the word the caller wrote, what the role does instead, the one page that states it.

**What is kept on purpose**, because it is what stops the surviving words from refusing prose: the
here-document and quoted-string removal, the whole-word boundary, and the absence of any tool
allowlist. `merge` still appears in commit messages, issue bodies and search patterns every day, and
removing the data a command carries is cheaper than a detour telling the caller how to re-spell it.

**The keep-bar is the rule this ADR ships**, and it is what a future round is answered with: before
a word is added to any role's list, it must name an act that is irreversible *and* that no other
layer — the merge guard, branch protection, an agent definition's writer denial, an OS sandbox, the
disposability of a lane — already stops. A word that fails either half buys its refusals with false
ones, and a false refusal costs a lane.

## The residual, named

ADR 0051's *"a review finding of that class is a Note"* governs what this widens, and it widens in
two directions worth writing down rather than leaving for a round to discover:

- A **reviewer's shell** now reaches GitHub writes outside `gh api` — `gh pr merge` among them. The
  gate's read-only property is the agent definition's writer denial and, on the Codex path, the OS
  sandbox; the word list never supplied it.
- A **worker's recursive `rm`** now reaches any target, `/` included. The lane is a disposable
  worktree whose branch is already pushed, and the rule that guarded it also refused
  `rm -rf node_modules`.

Neither is answered with a new word. The layers that carry the guarantee are unchanged: `guard
merge`'s reviewed-head verification and rebase proof, GitHub's branch protection, the per-role OS
sandbox where the executor has one.

## Consequences

The hook is now small enough to state in one sentence on each role page, which is what
`reference/orchestrator.md`'s **The role hook** paragraph and `reference/worker.md` §1 do.
`.github/test-hard-edges.py` keeps its sweep unchanged in mechanism — every surviving rule across
the bare, quoted, here-doc, substitution and `cd … &&` positions and both tool-input formats — and
gains a table pairing each struck-out word with the benign command it used to refuse, so a word that
comes back brings its false refusal back with it. The real-CLI qualification suites
(`.github/test-codex-runtime.py`, `.github/test-claude-runtime.py`) probe each role's own surviving
rule, because since this change no single command is refused for more than one role.

Minor version: the hook admits more than it did and refuses nothing new.

**This ADR decides what the method ships**, not only how this repository operates: every seeded
project's role hook refuses these three things and nothing else.

**Amendment (2026-09-20, issue #437):** *"refuses these three things and nothing else"* now holds on
the error path too. The hook's top-level handler denied on any exception, so a malformed host event
or a bug below the decision was a fourth refusal — one naming no act at all, let alone an
irreversible one nothing else stops, and which this ADR's own keep-bar therefore rejects. It fails
open instead: the call is admitted and one line on stderr names the error. The three rules and the
worker's default-branch `push` are untouched, and `.github/test-hard-edges.py` gains a case that
injects an exception into the decision and asserts admission with that warning. See 0051's block of
the same date for the reasoning.

**Amendment (2026-10-05, see 0064):** the three words and the worker's default-branch `push` stand;
the carrier changes. The guard rides the host's `tools/pre-execute`, reading the same command text,
with dsh's tool names in place of the old ones. One widening is named rather than chased: the subagent
row that spawned a child is not carried onto it, so the guard's child tier applies the
worker-and-reviewer union until a child can be mapped to its row. A reviewer's write refusal is
unaffected — the row's `toolFilter` carries it hard, not a word.
