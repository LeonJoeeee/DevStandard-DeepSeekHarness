# DevStandard

[![CI](https://github.com/LeonJoeeee/DevStandard-DeepSeekHarness/actions/workflows/ci.yml/badge.svg)](https://github.com/LeonJoeeee/DevStandard-DeepSeekHarness/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/LeonJoeeee/DevStandard-DeepSeekHarness)](https://github.com/LeonJoeeee/DevStandard-DeepSeekHarness/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**The GitHub flow, extended to agent teams.**

DevStandard is a development-method bundle for [DeepSeek Harness](https://deepseekdocs.com) (dsh) — it delivers the orchestrator's role as a system-prompt section and dispatches work to dsh's own subagents. It adds the three things an agent harness doesn't do by itself:

1. **Discipline** — rules an agent won't impose on itself: settle what "done" means before starting, get designs torn apart before writing code, prove completion with evidence, know when to stop and ask you;
2. **Project memory** — a PRD, an architecture doc, a decision log, design specs for substantial changes, and a repo instructions file only when it has commands, gotchas, a worktree copy-list, or record-language declaration to hold, so parallel sessions (and human teammates) stay aligned on *what*, *how*, and *why*;
3. **Reliable delivery of both** — the bundle registers the orchestrator's self-contained role reference as one root-agent system-prompt section, delivered whole. Dispatched workers receive their own complete role context.

The bet behind it: directing agents is the same collaboration problem humans already solved with the GitHub flow — so agents follow the **same** branches / PRs / CI / review process your team already uses, instead of some new agent-coordination scheme ([why](docs/adr/0009-github-flow-extended-to-agent-teams.md)).

## Requirements

- **DeepSeek Harness (dsh)**, as the main session ([ADR 0064](docs/adr/0064-this-repository-delivers-devstandard-for-deepseek-harness.md)). Dispatch goes to dsh's own built-in subagents, and to nothing external ([ADR 0065](docs/adr/0065-dispatched-work-is-the-hosts-own-subagent.md)).
- **[superpowers](https://github.com/obra/superpowers)** — the craft layer. Its requirements, debugging, TDD and planning skills are the role pages' craft bindings ([ADR 0067](docs/adr/0067-superpowers-craft-is-ported-into-the-package.md)).
- **git**, and a **GitHub repo** for the full flow — the generated CI and release pipelines target GitHub Actions. The discipline itself works with any git hosting.
- **Python 3.9+ and an authenticated [`gh`](https://cli.github.com/) CLI** for the shipped commands — the dispatcher, review packets and guarded merge use GitHub through `gh` ([dispatch guide](reference/orchestrator.md)).

## Install

Create a profile and install this bundle into it:

```sh
dsh myprofile --from-default-profile tui --dump-config   # create the profile from the shipped template
dsh plugin --profile myprofile add <path-or-package>     # install this bundle
dsh myprofile                                            # boot it
```

To check it took: start a session and ask *"what does DevStandard tell you to do?"* — the agent should recite the trigger rule and the discipline.

**Updating.** Re-run `dsh plugin --profile myprofile add <path-or-package>` at the new version, then start a new session. Confirm the same way as the install check above.

## What you get

- **Set the result and why** — the orchestrator turns them into issues with bounds and observable done-checks. Document and review weight belongs to each task; a demo earns no automatic setup ceremony.
- **Keep one responsive orchestrator** — the main session discusses, dispatches, accepts and integrates. Direct work stays small enough not to block that conversation; other concrete work goes to a worker.
- **Run workers in parallel lanes** — one task, branch and worktree each, on the `worker` delegation tool by default. A worker implements, rebases, proves the final state and delivers a green PR; isolation is the worktree, the role hook, and independent review, because an in-process child inherits the session's permissions.
- **Accept against the goal** — a clean reviewer judges a green PR under the Goal/Floor/Notes contract. Both review and CI guard integration; architecture direction and major releases remain human-owned.
- **Load the relevant context** — the orchestrator's role reference arrives as a root-only system-prompt section, and the worker's arrives as its delegation row's `persona`. Other references load at their triggers.

## How you use it

**Day to day** — nothing visible changes. Ask for a bug fix or a small feature in an existing repo and the agent just does it, under standing discipline: it settles what "done" looks like first, and closes with evidence instead of "should work now".

**Starting something new** — say what you want to build and why. The orchestrator clarifies the outcome and chooses task bounds with you. A durable project definition, shared architecture, substantial design, or pipeline task triggers its corresponding document or template; a demo does not inherit a full lifecycle merely because it is new.

**Working a big project in parallel** — discuss direction with one orchestrator. It creates issues, cuts independent scopes and dispatches N lanes through the [fixed dispatcher](reference/orchestrator.md). Workers return evidence-bearing PRs, drive CI green, and leave their worktrees for the orchestrator. A clean reviewer judges acceptance, the guarded integration path verifies the result, and the orchestrator closes the issue, cleans up and performs any authorized release. You own direction, irreversible authorization, architecture direction, and major releases.

Execution scales through isolated lanes: the orchestrator keeps direct work short and delegates
anything that would block the coordinating conversation; workers own concrete task lanes.

## What's actually installed

The orchestrator's static context is one self-contained page,
[`reference/orchestrator.md`](reference/orchestrator.md): the shared workflow contract, its event
loop and its operations. `index.js` reads it from the bundle at load and registers it as a
system-prompt section **on the root agent's scope alone**, so a fresh session holds it before its
first turn and a dispatched child never does. The method's own size discipline survives as prose;
the mechanical part-cap does not, because the host it measured is gone.
Runtime evidence and its limits are recorded in
[the architecture](docs/architecture.md).
The worker receives [`reference/worker.md`](reference/worker.md) — the whole page, as the `worker`
delegation row's inline `persona` — plus one task packet from the
[fixed dispatcher](reference/orchestrator.md). That page is the shared contract; the mechanics of
the host it is running on come with it, from [`reference/harness-dsh.md`](reference/harness-dsh.md), and a
worker is never handed the other role's page. Those pages are self-contained together: the role is
complete without the orchestrator page. The reviewer judges under the sole
[judging contract](reference/code-review-prompt.md), which the review-packet script fills from
current sources, dispatches through the `reviewer` tool, and publishes whole on the PR.
Superpowers bindings live once per role, checked against the bundle's generated personas.
Other templates and procedures in [`reference/`](reference/) load at their triggers. The supported
configuration and guard limitations are in [the architecture](docs/architecture.md) and
[the guard guide](reference/orchestrator.md).

**A guard runs before your tools, and it denies with a reason.** The bundle listens on dsh's
`tools/pre-execute`: it sees every tool
call, reads the command itself — not a here-document body or a quoted string it carries — and
refuses three things, each as a whole word: a worker's `merge`, an orchestrator's `gh pr merge`,
which routes to `scripts/guard merge` instead, and a reviewer's `gh api` write flags. A worker's
push naming the default branch is refused too, until branch protection takes that over. Everything
else is admitted — a tag, a release build, a force-push, an `rm -rf node_modules` — because a word
that refuses reversible work costs more in false refusals than it buys. Shell syntax is never a
reason to refuse, and no network failure can produce one.
**There is nothing to configure** — no settings file, no allowlist, no per-project word list — so
adopting it is installing the bundle. Every refusal is a
reminder rather than a wall: it names the word you wrote, what your role does instead, and the page
to read. This guards the ordinary
case and says so: an interpreter script or an obfuscated spelling is outside it, and `guard merge`,
branch protection and the reviewer row's write-tool denial supply separate enforcement layers. The rule and its limits are in
[the guard guide](reference/orchestrator.md).

## FAQ

**Will it slow down small edits?**
Weight follows the task. A small edit needs no invented PRD, architecture document or ADR;
the ordinary branch/PR gates still apply, with the
[two-checks paragraph](reference/orchestrator.md) naming the narrow exceptions. The agents run the commands.

**What exactly enters my context?**
The orchestrator page is delivered as one root-only system-prompt section before the first turn;
the worker and reviewer pages travel as their delegation rows' `persona`. A dispatched worker also
holds the repository-root instructions file, because the host injects the `AGENTS.md`/`CLAUDE.md`
chain into every agent.
The [rule ledger](docs/specs/2026-09-06-core-md-rule-ledger.md) records the original measurement and carrier choices.

**Does it depend on other plugins?**
One: [superpowers](https://github.com/obra/superpowers). The host supplies mechanics and superpowers supplies craft — at the step where a craft skill helps, the flow names it and the agent invokes it; the skill serves inside that one step, and on any conflict DevStandard's flow wins ([ADR 0016](docs/adr/0016-superpowers-becomes-a-dependency.md)). Two `reference/` files remain adapted from superpowers (MIT, attribution kept).

**Is it for teams or solo?**
The supported configuration is one dsh orchestrator per project and N isolated workers.
GitHub holds the durable collaboration record; the [architecture](docs/architecture.md) defines
the supported executor boundary.

**Can I adopt it on an existing project?**
Yes. Changes are tasks from day one. Add each method document only when its own trigger fires; the paths in the templates are defaults that yield to an established convention, declared by the architecture doc, and a repo-root instructions file exists only when it has an admitted line to hold (`reference/in-repo-writes.md`).

## Layout

```
cordis.patch.yml  the bundle patch: role delivery, the `worker` and `reviewer` delegation rows,
                  and the one model anchor both rows alias
index.js          the plugin: root-only role delivery and the `tools/pre-execute` role hook
guard.js          the guard's word engine, ported from `scripts/hard_edges.py` and pinned to it
scripts/          the shipped machinery — fixed dispatcher, review packets, guarded merge
reference/        the self-contained orchestrator and worker role pages, each carrying
                  the shared workflow, role interlock, resident triggers, clean handback
                  and PR-green — and, on the orchestrator page, executor dispatch,
                  guarded operations and the worktree checklist — plus one file per
                  thing they still point at: PRD / architecture / ADR /
                  design-spec templates, CI + release pipelines, red-check
                  and CI-fallback rules, reviewer
                  prompt, where files go (where-it-goes.md — not a
                  router or classifier), out-of-repo writes, in-repo document
                  admission, the repo instructions-file admission, and the dsh
                  mechanics page
docs/             DevStandard's own PRD, architecture doc, and decision log
_source/          the research this design stands on
```

DevStandard was built with its own rules. Its `docs/` holds a real PRD, architecture doc, and an ADR log recording why every major call went the way it did — including the ones that got overturned (0001 → 0007, 0002 → 0016, 0003 → 0008, 0004 → 0014, 0005 → 0015, and the rebuild's own supersessions: 0038/0039 → 0045 → 0056 → 0063 → 0064, 0006/0008 → 0047, 0014 → 0048). That log is the best demo of what the method produces.

## License

MIT.
