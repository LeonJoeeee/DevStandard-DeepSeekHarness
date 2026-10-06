# DevStandard — Collaboration-model architecture

> Shared baseline for all parallel work. Read before any task. Changing anything here = touching
> the core: public merge + human approval + an ADR.

This document defines the supplementary harness required by the three target workflows in PRD §4. It
does not repeat those workflows or the working rules held by their role pages. It defines the
roles, context boundaries, delivery paths, enforcement points, and concurrency behavior from which
the rebuild is implemented. Every structure named here is traced to a PRD §1 pain point or a PRD §2
reuse decision in the closing table.

Delivery and enforcement statements use two labels. **Verified** means the behavior was measured or
the artifact was inspected, and names its source. **Unverified** means the architecture requires the
behavior but the rebuild has not demonstrated it. A design requirement is not treated as a fact
about a native harness. Unless a paragraph or evidence cell says **Verified**, mechanisms described
here are **Unverified** target requirements.

## 1. Scope and configuration

The supported configuration is one dsh orchestrator with N dispatched executors. A
dispatched executor has one of two purposes, worker or reviewer. Implementations are dsh's own
subagents — the `worker` and `reviewer` delegation rows, and nothing external. A conflict resolver is a
worker assigned a conflict task, not a third role. This is the smallest configuration that removes scheduling from the human while
retaining the GitHub flow and native isolation mechanisms (PRD §1.1, §2.1, §2.2).

DevStandard is a supplementary harness. The host owns its sessions, native subagents,
tools, models and permissions; a dispatched in-process child inherits the session's permissions and
cwd, so the port gives up the per-worker OS sandbox the retired CLI path had. DevStandard supplies the
missing collaboration protocol: role context, dispatch, acceptance, and the transitions between
GitHub artifacts. It replaces neither the native harness nor its own role hook (PRD §1.1, §1.5).

**It governs one layer: the collaboration with GitHub — issue, lane, PR, review, merge — and
nothing below a role.** What a dispatched role spawns beneath itself to finish its own task touches
none of those artifacts, so this design neither defines nor requires any such subagent, and sets only
the model it takes (`reference/orchestrator.md`'s Model and effort section); what it
requires of a lane is that one accountable author hands back one PR (ADR 0055). The gating reviews
above a role — merge check 1 and the pre-code design challenge, both commissioned by the
orchestrator and published on the PR — are inside this layer and unaffected.

ADR 0064 makes this repository deliver DevStandard natively for DeepSeek Harness (dsh) as the main
session ([issue #1](https://github.com/LeonJoeeee/DevStandard-DeepSeekHarness/issues/1)); the Claude
Code project is a sibling that continues unchanged and is never synchronized back. ADR 0065 removes
the CLI executors, so dispatch goes to dsh's own subagent and nothing external, and ADR 0066 fixes
one model at one effort for every dispatched role. Workers retain their internal
delegation under ADR 0055. Separate live-session lanes, custom agent configuration and
workflow panels are not required (PRD §1.6).

**Verified — repository source:** the bundle declares `dsh.bundle.patch -> cordis.patch.yml`; its
`index.js` registers a root-scoped system-prompt section carrying `reference/orchestrator.md` and the
`tools/pre-execute` role hook, whose word engine is `guard.js`; its two delegation rows carry
`reference/worker.md` and `reference/code-review-prompt.md` as inline `persona` text and alias one
model anchor. `.github/check-dsh-bundle.py`, `.github/check-dsh-guard.py` and
`.github/test-dsh-bundle.py` assert the row shape, the anchor, the persona byte-identity, and the
live delivery — the qualification the retired host's evidence section used to carry, recorded in the
ADR log rather than here.

The durable coordination state is GitHub: issues declare work, branches and worktrees isolate it,
PRs deliver it, review records acceptance, and CI plus branch protection gate integration. Native
task handles, process identifiers, and output files are transient observations, not a second state
machine (PRD §2.1, §2.2).

## 2. Roles and context sets

### Orchestrator

The orchestrator converses with the human, completes an issue with the settled result and reason
after the human confirms the handover,
partitions concurrent work, dispatches executors, observes delivery, assembles acceptance reviews,
merges accepted work, and performs cleanup and delegated release. Its context set contains:

- the workflow contract and the three events that wait on the human;
- open-issue, open-PR, CI, branch, and worktree state needed to run the main loop;
- the dispatch, acceptance, merge, cleanup, and reporting triggers with pointers to their operative
  procedures;
- requirements-clarification skill bindings used while discussing direction with the human; and
- the rule that implementation craft and a worker's task-local procedure are not loaded into the
  orchestrator set.

This set keeps the main conversation responsive and stops the human from becoming the scheduler
(PRD §1.1). It delivers assumed working conventions to every new orchestrator session (PRD §1.5)
without mixing in the worker set described below.

### Dispatched executor: purpose × host row

There is one dispatched-executor construct. Purpose determines its context and authority;
the delegation row determines how that context is delivered.

| Purpose | dsh delegation row | Result |
|---|---|---|
| Worker | The `worker` row's `persona` is `reference/worker.md`, the whole shared contract with its own mechanics page delivered beside it (ADR 0061); the row's `agentOptions` fixes the model and effort, and the dispatcher supplies the task packet. | A green PR linked to the issue, rebased on current `main`, with final-state evidence. |
| Reviewer | The `reviewer` row's `persona` is `reference/code-review-prompt.md`; the row's `toolFilter` denies the write tools, and the packet supplies the review instance. | A verdict naming the reviewer and reviewed head, published whole on the PR. |

The carriers are the two rows' inline `persona` text, generated from `reference/worker.md` and
`reference/code-review-prompt.md`, each page the one operative source for its role;
`.github/check-dsh-bundle.py` asserts each `persona` is byte-identical to its source and regenerates
it under `--write`. The worker's contract sits beside its own mechanics page,
`reference/harness-dsh.md`, and a worker is delivered its own and never the reviewer's (ADR 0061). A
role's own subagents are not a third one: they sit below the governed layer (§1), and on dsh a child
cannot itself delegate, so v0.45.0's `devstandard:helper` definition and the pre-handback review it
was required for are removed (ADR 0055).

The routing rule is ADR 0065: dispatch goes to the host's own subagent, and nothing external. The
dispatcher prepares a delegation instruction — the `worker` or `reviewer` tool to call, with a
description and the brief pointer — and the orchestrator calls it and records the returned child id;
a prepared instruction is not a running worker. The choice
changes delivery, not purpose or obligations. Explicit binding prevents invented working conventions
(PRD §1.5); role-based skill bindings reuse the superpowers library at the step where its craft is needed (PRD §2.3).

### Worker context set

The worker set consists of the static role plus one dynamic task packet.

The static role binds the worker to PRD §4 Workflow 3: one issue, branch, and worktree; write
authority only in that lane; evidence and attribution duties; the NEVER and escalation boundaries;
and the execution-skill triggers, including test-driven development and systematic debugging. The
task packet supplies the freshly fetched whole issue — body and ordered non-record comments
verbatim — with named base, branch, worktree, required inputs, and expected output. It carries no
merge, release, or orchestration procedure. This separates execution from integration and makes a
worker's claim inspectable rather than trusted (PRD §1.2, §1.5, §2.3).

### Reviewer context set

Reviewer is the read-only purpose of the dispatched-executor family. Its static set is the judging
contract from issue #183 and PR #188: Goal verdict first, the two-check Floor second, and Notes last.
Only the Goal verdict and Floor decide readiness; Notes neither block nor trigger another review
round. The reviewer has no craft skills because it reads and rules rather than builds (PRD §1.4).

An ordinary review packet contains the issue's goal, bounds, and done-check; the PR description as
the fulfillment claim; explicit review-base and head SHAs; the convention base; the accepted-spec
blob or `NONE`; the architecture-level flag; the CI-configuration paths the diff touches, so a green
run the diff configured cannot vouch for it; the in-repo-write predicate; an assembly report naming
what it pinned and what it could not; and the published CI-fallback comment only when the fallback
has been declared. Beside those slots it carries the complete issue body as
quoted evidence, the three contract sections still deciding the verdict
(`reference/code-review-prompt.md`). The reviewer sees no orchestrator history and treats
supplied claims as unverified (PRD §1.2, §1.4).

### Resolver

A resolver is a worker whose issue-sized assignment is to rebase a delivered branch that conflicts
with current `main`. It receives the ordinary worker set plus the delivered PR, old and new bases,
the conflicting paths, and the original issue contract. It may change only that lane, reruns the
original done-check on the resolved final state, republishes evidence, and returns the new head for
fresh review. It never receives merge authority (PRD §1.2, §2.2).

## 3. Context delivery

Static role content has one operative source per role: `reference/orchestrator.md`, `reference/worker.md`,
and `reference/code-review-prompt.md` for the reviewer. The worker's is a contract
only; the mechanics of its host come from the one mechanics page, `reference/harness-dsh.md`, and a
worker is delivered it beside its contract (ADR 0061). The rows' `persona` text and the dispatch
brief are delivery carriers, not independently edited copies — a `persona` is generated from its
page and CI asserts byte identity. Each role page is
self-contained: it carries the shared workflow contract, triggers and pointers together with that
role's own operations, so a role reads one page and never the other role's (ADR 0059) — plus, for a
worker, its own mechanics page, delivered with the contract rather than read from a pointer. This
arrangement addresses convention loss without rebuilding another incident-driven rules layer
(PRD §1.5, §1.6).

**Delivery is the harness's own mechanism, not a hook and not a read.** The bundle reads
`reference/orchestrator.md` at load and registers it, through the root agent's own context, as a
system-prompt section on the **root agent's scope alone**: a spawned child's scope is a sibling of
its parent's, never a descendant, so the orchestrator page reaches the root and nobody else (probe 2
item 1, issue #4). A dispatched child instead carries its own row's `persona` — `reference/worker.md`
or `reference/code-review-prompt.md` — read from the bundle when the child is created. Both survive
compaction, because a system prompt is not a conversation; the dynamic task packet does not, which
is why the worker page keeps its recovery procedure. There is no per-output cap to fit and no part
reassembly: the section mechanism carries a page whole, so the mechanical part-cap the retired host
measured does not survive — the method's own size discipline does (ADR 0064).
**Verified — repository source:** `index.js` registers the section and `cordis.patch.yml` carries the
two rows; `.github/test-dsh-bundle.py` proves the root's request carries `reference/orchestrator.md`'s
exact bytes and no child's does, and that each child's request carries its own page and not the
other's.

| Context and role | Delivery path | Evidence state |
|---|---|---|
| Orchestrator static set | The bundle's `index.js` registers `reference/orchestrator.md` as a root-scoped system-prompt section at load, before the agent's first turn. | **Verified — repository source and live run:** `.github/test-dsh-bundle.py` takes the page's exact bytes out of the root request and requires their absence from a worker's (issue #4). Persistent UI lifecycle behavior remains **Unverified**. |
| Worker static set | The `worker` row's `persona` is `reference/worker.md`, read from the bundle at spawn; the page is complete with its own mechanics page, `reference/harness-dsh.md`. | **Verified — repository source and live run:** `.github/check-dsh-bundle.py` asserts the persona byte-identity and `.github/test-dsh-bundle.py` requires the page's bytes in the worker child's request and the reviewer's absence from it. |
| Worker task | The dispatcher validates the lane, then prepares a delegation instruction carrying the brief pointer; the orchestrator calls the `worker` tool and records the returned child id. | **Verified — repository source:** `scripts/dispatch` validates fields and publishes the instruction; `.github/test-dispatch.py` covers refusal and lane records. |
| Reviewer static set | The `reviewer` row's `persona` is `reference/code-review-prompt.md`, and its `toolFilter` removes the write tools from the child's prompt and rejects their execution. | **Verified — repository source and live run:** `.github/check-dsh-bundle.py` asserts the persona and the tool denial; `.github/test-dsh-bundle.py` proves a scripted write call is rejected. A model acting on the contract it receives remains **Unverified**. |
| Review instance | The review-packet assembler reads current GitHub state, resolves exact SHAs, takes the current reviewer contract, and fills every ordinary-packet slot before dispatch. It refuses a partial packet or a review before the PR is green. | **Verified — [issue #183](https://github.com/LeonJoeeee/devstandard/issues/183) and [PR #188](https://github.com/LeonJoeeee/devstandard/pull/188):** the judging protocol changed while this architecture work was being dispatched, demonstrating that a copied earlier packet can stale under the dispatcher. **Verified — repository source:** `scripts/review-packet` implements current-source assembly, green-head admission and refusal of incomplete slots; `.github/test-review-packet.py` covers these transitions. |

The dispatcher records purpose, issue, branch, worktree and the prepared delegation status on the
issue; the orchestrator adds the child id the tool returns, and the shell dispatcher cannot invent or
observe it. That lane record is the observable marker for the dispatched wait, and a child's end is
observable at the tool boundary rather than through a detached supervisor
(`reference/orchestrator.md`'s Dispatching to an executor section).
Completion is never inferred from those signals: it is established only by the durable PR,
evidence, verdict, and CI state. A restarted orchestrator reconstructs work from open issues and
PRs; absence of a PR remains "running or lost," not "done" (PRD §1.1, §1.2, §2.1).

**Unverified:** how much of the live dispatch-to-handback loop holds end to end, and issue-record
creation as one recovery path, have not been tested as one sequence.

## 4. Workflow edges and enforcement tiers

The tiers describe how a rule binds:

- **Hard:** a native mechanism refuses an invalid action. Use it for catastrophic and mechanically
  decidable boundaries.
- **Structural:** the harness puts required context or a fixed transition at the act site. The agent
  can still disobey, but omission is not left to memory.
- **Soft:** the role instructions require judgment. Use it only where the decision cannot be made
  mechanically.

The workflow comes first; tiers are assigned to its edges, not used to invent additional workflow.
The worker-side rows below point to PRD §4 Workflow 3 and assign mechanisms to its boundary; they do
not restate the worker's execution.

### Workflow 1: one task

| Step or edge from PRD §4 | Tier and native mechanism | Evidence state |
|---|---|---|
| Discussion → confirmed, complete ① issue | **Structural:** the orchestrator set provides the issue fields and the requirements-skill trigger. **Soft:** the human confirms the settled result and reason; the orchestrator completes its scope and done-check afterward. | **Verified — repository source:** `reference/orchestrator.md` supplies the ready-at-dispatch definition, fields and triggers; native startup delivery is qualified below. The use of a skill here is reuse under PRD §2.3, not a claim that a skill can judge completeness. |
| ① issue → ② dispatch / Workflow 3 receipt | **Hard:** the fixed dispatch script refuses a missing issue, named base, branch, or worktree, and a reviewer dispatch whose goal, bounds or done-check is unfilled. **Structural:** the injected worker set points to Workflow 3's specification check. **Soft:** the orchestrator writes the issue contract and cuts scope, and the worker returns a missing or vague field before starting (#427). | **Verified — repository source:** `scripts/dispatch` validates fields and selects the requested implementation; `.github/test-dispatch.py` covers its refusals. This edge exists to prevent evidence-free work and missing conventions (PRD §1.2, §1.5). |
| ② dispatch → Workflow 3 isolated lane | **Hard:** the reviewer row's `toolFilter` denies the write tools, and branch protection rejects a direct push to a protected default branch. **Structural:** a dedicated worktree separates working trees, while the selected role row and the task packet bind the worker to Workflow 3. **Soft:** a worker with required shared-git-metadata access still obeys its named-branch boundary. | **Verified — repository source:** `cordis.patch.yml` declares the worker and reviewer rows and the reviewer's tool denial; dispatch records lane identity; `.github/test-dsh-bundle.py` proves a scripted write call is rejected. Reuses PRD §2.2. |
| ③ Workflow 3 execution → green delivered PR | **Hard:** review assembly refuses acceptance until the current PR checks report green. **Structural:** the worker set binds Workflow 3's act-site obligations to the lane. **Soft:** implementation choices and the truth of non-mechanical evidence remain worker judgment subject to review. | **Verified — repository source:** the worker carrier delivers the role itself — the row's `persona` — and review-packet enforces green-head admission. **Unverified:** the complete live execution-to-handback path. GitHub, CI, and worktrees are reused under PRD §2.1 and §2.2; acceptance addresses PRD §1.2. |
| Delivered green PR → ④ acceptance | **Hard:** the assembler refuses an ordinary review while the current PR head is red or unreported; the reviewer row denies the write tools. **Structural:** the assembler supplies a complete, current, clean-context packet and the Goal/Floor/Notes output shape. **Soft:** the reviewer judges goal fulfillment and the Floor evidence. | **Verified — [issue #183](https://github.com/LeonJoeeee/devstandard/issues/183) and [PR #188](https://github.com/LeonJoeeee/devstandard/pull/188):** the goal-centric contract and empty-by-design skill set are recorded, and PR #188's CI is green. **Verified — repository source:** `scripts/review-packet` implements green-head admission and packet assembly; the reviewer row's `toolFilter` carries its read-only posture. Live role enforcement is qualified separately below. This edge addresses PRD §1.2 and §1.4. |
| ④ accepted head → ⑤ merge and cleanup | **Hard:** branch protection rejects direct main writes; the merge guard requires a Goal Yes/Floor Pass verdict or the permitted orchestrator merge-as-is ruling after both Floor checks pass. If `main` moves after acceptance, the only path without a fresh verdict is a conflict-free rebase for which the comparison script proves every PR-changed path byte-identical — chapter 5's manifest version-line exemption apart — and CI passes on the merged result; both hard layers pass → merge, while either failure falls back to full review and a resolver where needed. **Structural:** the guard records the acceptance anchor and comparison proof; architecture-level status travels in the issue, PR, and review packet. **Soft:** the orchestrator classifies architecture-level work and waits for the human's decision. | **Verified — [issue #179's option-A ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5550436875):** the human fixed the two-layer path. **Verified — repository source:** `scripts/guard`, `scripts/hard_edges.py` and `.github/test-hard-edges.py` implement and constructively probe these checks. Target-repository protection still requires actual evidence. The hard mechanisms are reused under PRD §2.1 and §2.2. |
| ⑤ merged result → ⑥ delegated release | **Structural:** the orchestrator set requires the human's authorization or the project's standing delegation before releasing, and the one-line report after. **Soft:** the human decides a new delegation or major-release sign-off. | **Unverified:** delivery of the release rule to a fresh orchestrator. Since ADR 0052 this edge has **no hard tier**: the hook does not recognize `tag` or `release`, and no record is looked up. Releasing is judged against PRD §1.3 by the role's page, and that is the ruling, not a gap to close. |

### Workflow 2: orchestrator events

The event-handler paragraph under [PRD §4 Workflow 2](./PRD.md#4-the-solution-the-target-workflows),
tracked in [issue #194](https://github.com/LeonJoeeee/devstandard/issues/194), is the authority for
the loop's semantics rather than this table. The architectural consequence is that every event
handler must be short, and any long wait is a dispatched lane plus an observable marker
([human ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5550436875)).

| Event from PRD §4 | Tier and native mechanism | Evidence state |
|---|---|---|
| The human speaks | **Soft:** the orchestrator discusses or adjusts direction. **Structural:** its role set presents the issue-creation and requirements-skill triggers. | **Verified — repository source:** `reference/orchestrator.md` supplies these triggers; host delivery is qualified below. Addresses PRD §1.1 and reuses §2.3. |
| An irreversible action is needed | **Hard:** the role hook rejects its listed command words at the host's `tools/pre-execute`, and refuses the orchestrator's `gh pr merge`, routing merges through `guard merge`; GitHub's branch protection rejects a direct push to a protected default branch. **Soft:** the orchestrator identifies every irreversible action the guard's word list does not reach — which since ADR 0051 is deliberately most of them, teardown of a merged lane included, since ADR 0052 the founding push and the release as well, and since ADR 0062 everything outside the three rules. | **Verified — repository source:** `guard.js` implements the word lists at `tools/pre-execute`; `.github/check-dsh-guard.py` pins it to `scripts/hard_edges.py`. Addresses PRD §1.3. |
| Architecture direction or a major release is ready | **Structural:** the orchestrator set keeps direction and major-release authority with the human, and an architecture-level acceptance is commissioned at the arbitration setting; architecture integration has no separate sign-off after that direction is settled. **Soft:** the orchestrator classifies the change and the human decides direction or publication. | **Verified — repository source:** `reference/orchestrator.md` supplies the authority boundary and its Dispatching to an executor section supplies review routing. Addresses the irreversible-control concern in PRD §1.3. |
| Ready-at-dispatch issues await | **Hard:** the dispatcher enforces one branch/worktree per task. **Structural:** it creates and records N lanes. **Soft:** the orchestrator applies its ready definition and cuts scopes to reduce overlap. | **Verified — repository source:** `reference/orchestrator.md` defines the dispatch moment; `scripts/dispatch` publishes lane records and `.github/test-dispatch.py` covers its admission and refusal transitions. GitHub and worktrees are reused under PRD §2.1 and §2.2 to address PRD §1.1. |
| A worker delivers | **Structural:** the orchestrator observes the PR and external state, validates the fulfillment packet, and starts acceptance only when required checks for the current head are green. A red or unreported PR remains on the worker side of the handback edge. **Soft:** a worker report remains a claim until review establishes it. | **Verified — repository source:** `scripts/review-packet` enforces green-head admission. **Unverified:** autonomous observer behavior as a complete live loop. The durable source is GitHub under PRD §2.1; the distrust boundary addresses PRD §1.2. |
| A verdict returns | **Structural:** Goal Yes/Floor Pass advances the reviewed head toward merge; if its base later moves, it enters the two-layer light-review path. Goal No returns only the stated goal grounds to the orchestrator for its per-PR continuation decision. A Floor check 1 failure—an evidence-free completion claim—returns to the worker for real evidence, and the failed review counts as a round. A Floor check 2 failure—an unauthorized irreversible action or out-of-scope work—stops the lane and escalates to the human at the irreversibles touchpoint, with no fix round. A conflict dispatches a resolver. **Hard:** merge waits on exact-head acceptance or a prior acceptance anchor plus both content-unchanged-rebase layers; any failed layer falls back to full review and a resolver where needed. **Soft:** the verdict, the permitted orchestrator ruling, and whether another goal-fix round is useful are judgments. | **Verified — [issue #183](https://github.com/LeonJoeeee/devstandard/issues/183) and [PR #188](https://github.com/LeonJoeeee/devstandard/pull/188):** Goal/Floor/Notes semantics. **Verified — [issue #179's round ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5525395030) and [option-A ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5550436875):** the human fixed the continuation, cap, and base-move paths. **Verified — repository source:** review-packet round accounting, guard rebase proof and dispatch continuation implement the mechanical transitions. **Unverified:** the complete autonomous verdict-to-resolution loop. Addresses PRD §1.2, §1.3, and §1.4. |
| Main goes red | **Structural:** the orchestrator set stops new dispatch and presents revert-first recovery and the relevant procedure. **Soft:** it decides whether an obvious minutes-long fix-forward is safer than revert. | **Verified — repository source:** `reference/orchestrator.md` supplies the event rule. CI is reused under PRD §2.1; preventing concurrent work on a bad base supports PRD §1.1. |
| Idle | **Structural:** the main-loop trigger queries open issues, PRs, checks, and worktree records and reports progress. **Soft:** the orchestrator decides whether a leftover needs cleanup or escalation. | **Verified — repository source:** `reference/orchestrator.md` supplies the idle trigger. **Unverified:** sustained autonomous idle handling. Reuses GitHub state under PRD §2.1 to address PRD §1.1. |

### Workflow 3: worker execution

[PRD §4 Workflow 3](./PRD.md#4-the-solution-the-target-workflows) is the authority for the steps; this table assigns their enforcement mechanisms.

| Step or edge from PRD §4 Workflow 3 | Tier and native mechanism | Evidence state |
|---|---|---|
| Receipt → specification check | **Hard:** the fixed dispatch script refuses an unfilled named base, branch, or worktree. **Soft:** the worker judges a missing, placeholder or vague goal, bounds or done-check and returns an underspecified task rather than starting; since #427 that judgment is the only check on the worker path. | **Verified — repository source:** dispatch validates the lane and the worker role begins with the specification check. Host delivery qualification is separate below. |
| Taking position → baseline snapshot | **Structural:** the dedicated worktree separates the lane. The role set requires the baseline snapshot, and the dispatcher records the lane on the issue. | **Unverified:** worktree enforcement, baseline delivery, and issue recording as a complete lane path. |
| Implementation | **Structural:** the row's `persona` binds execution skills, including TDD and systematic debugging. **Soft:** implementation choices and the named-branch boundary remain judgment where shared git metadata access is required. | **Verified — repository source:** the worker page binds skills and its row delivers it as the child's system prompt. **Unverified:** uncoached skill use and named-branch adherence. |
| The four stop events | **Hard:** the worker role hook refuses command text carrying its short word list, decided from source alone. It does not remove every way to perform an irreversible operation. **Soft:** recognizing core-architecture work, a wrong or unreachable done-check, or a direction call requires worker judgment. **Structural:** the role set fixes the escalation channel (the issue/PR comment) and requires the lane to stop and wait. | **Verified — repository source:** the worker role defines the stop triggers and `scripts/hard_edges.py` implements the word list. **Unverified:** uncoached escalation behavior. The open enforcement boundary below still applies. |
| Rebase onto current main → own conflicts | **Structural:** the role set assigns rebasing and conflict resolution to the worker. **Hard:** the merge guard rejects a head not based on current main; a moved base after acceptance uses the content-unchanged-rebase path in chapter 5 or full review. | **Verified — [issue #179's option-A ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5550436875):** the two-layer rebase path is settled. **Verified — repository source:** the worker role assigns rebase ownership; guard and comparison machinery implement the current-base and unchanged-content checks. Live recovery as one sequence remains unverified. |
| Final-state done-check → evidence | **Structural:** the role set requires the done-check on the final state with commands, exit codes, and output. **Hard:** CI reruns the mechanical assertions. **Soft:** the truth of non-mechanical evidence is judged by Floor check 1. | **Verified — repository source:** `reference/worker.md` requires final-state evidence and `.github/workflows/ci.yml` carries mechanical assertions. **Verified — [PR #188](https://github.com/LeonJoeeee/devstandard/pull/188):** the Floor evidence contract. **Unverified:** the complete live evidence-to-acceptance path. |
| Opening the PR → fulfillment claim | **Structural:** the PR template restates the goal and carries the evidence. **Hard:** branch protection forbids direct main writes. | **Unverified:** rebuilt template delivery and branch-protection configuration. |
| Driving CI green | **Hard:** the observer and assembler refuse a red or unreported current head at acceptance. **Soft:** the worker classifies own-red versus not-own-red and escalates the latter. | **Verified — repository source:** review assembly enforces green-head admission and the worker role supplies red-check classification and escalation. Uncoached compliance remains unverified. |
| Handback → worktree left in place | **Hard:** the worker role hook refuses its listed merge command words. **Structural:** the lane record and handback message return the PR and evidence to the orchestrator, retaining the worktree for removal at merge. | **Verified — repository source:** the role hook, dispatch lane record and cleanup preconditions exist. **Unverified:** the complete live handback/cleanup transition. |
| Returned for a goal fix | **Structural:** a continuation brief carries the named goal gap into the same branch, worktree, and PR; the lane persists and the executor is disposable. **Hard:** per-PR round accounting records and reports every returned round. | **Verified — [issue #179's round ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5525395030):** same-lane continuation is settled; issue #434 replaced the cap with a reported warning. **Verified — repository source:** `scripts/dispatch` preserves the lane on continuation and `scripts/review-packet` enforces round accounting. Each returned native handle is recorded on the issue, which is the evidence a prior handle finished. |

**open:** the architecture never claimed zero unauthorized irreversible actions, and since ADR 0051
it does not attempt to. A hook that reads command text is not complete enforcement — obfuscation, an
interpreter script and an operation built from runtime data all pass it — so the role hook guards the
ordinary case and the layers that carry the guarantee are `guard merge`'s reviewed-head verification,
branch protection, and the reviewer row's write-tool denial. A dispatched child inherits the session's
permissions and cwd: its assigned-worktree and named-branch boundaries are structural role obligations,
and its shared git metadata access also does not enforce its named-branch boundary.

These assignments answer the five engineering sub-problems from PRD §5. Delivery is role-specific
and has one source per context set; a child's end is observed at the tool boundary;
asymmetry is explicit in the rows; enforcement is selected per workflow edge; and
observability uses external state while treating self-report as a claim.

## 5. Concurrency and review convergence

N-way dispatch is N issue/branch/worktree lanes under one orchestrator. The orchestrator cuts scope
to reduce overlap between concurrently writable path sets; it never reduces concurrency, and every
issue meeting `reference/orchestrator.md`'s ready-at-dispatch definition is dispatched at once. Worktrees separate lanes, and
every worker obeys its assigned-worktree contract; the role hook and independent review are the
remaining layers. GitHub provides the queue and durable return path (PRD §1.1, §2.1, §2.2).

**open:** the human has not set the observation target for N in PRD §6. The architecture therefore
defines N-way behavior without claiming a supported lane count.

Before handback, the worker owns rebasing and conflict resolution under PRD §4 Workflow 3. After a
green PR is handed back, the orchestrator never repairs a new conflict in its own worktree; it
dispatches a resolver worker into the affected lane. The resolver preserves the issue goal, reruns
final evidence, drives the new head green, and returns it for review. The
[live case recorded on issue #179](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5488090376)
verifies the cost: with two concurrent PRs, merging #177 caused #171 to conflict in
`reference/external-agent.md`; detection consumed review round 5, resolution used an
orchestrator-dispatched worker, and the changed head required round 6. That observation supports
scope cutting and resolver dispatch; it does not prove that every conflict has the same cost.

The review dose is one goal-centric round by default. Notes do not trigger another review round.
Whether to dispatch each next goal-fix round is the orchestrator's per-PR decision, judged only from
the verdict's stated goal gaps. Each returned verdict consumes a review round,
including a verdict that fails Floor check 1. The count is reported, and warned about past **7
rounds** per PR, but nothing refuses on it: the stop signal is findings of the same shape round
after round, which the reviewer reports as non-convergence. The
[human ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5525395030) set 7
as a provisional cap tuned from observed effect; issue #434 (2026-09-20) turned it into the warning,
no record of it ever firing having appeared.

The lane persists and the worker is disposable. A goal-fix round sends a continuation brief into
the same branch, worktree, and PR, carrying only the blocking goal gaps, the PR, and the issue. A
A continuation reaches the same child through `send_message`, or a fresh one. The child id is the caller's own and the dispatcher
observes none, so the id recorded on the issue is the evidence its child finished; only a live
or unknown child blocks reuse.

A Floor check 1 failure for an evidence-free completion claim returns to that lane for real evidence;
the failed review has already consumed a round. A Floor check 2 failure for an unauthorized
irreversible action or out-of-scope work stops the lane and escalates to the human at the
irreversibles touchpoint; it receives no fix round. A conflict after review invalidates the reviewed
head and dispatches a resolver; the resolver's changed head enters full review.

When another round would be pointless — most clearly when the findings keep their shape round
after round — the orchestrator rules first:
merge as-is when the goal is met within bounds and dispose of remaining Notes under
`reference/code-review-prompt.md`'s three options and leave-on-PR default; return the issue for
rewriting; abandon it; or change route. The ruling reaches the human only when it is
directional (abandon or change route) or meets `reference/orchestrator.md`'s handover-interrupt
grounds; that page's ready-at-dispatch and interrupt rules govern rather than a counted set of
touchpoints. Otherwise the orchestrator decides and reports the ruling in one line. A
merge-as-is ruling may settle an unresolved Goal No; it cannot waive either Floor check (PRD §1.4).

Before the option-A implementation, the rule re-reviewed every rebased head because its SHA changed. Applied to N ready PRs, each
merge can invalidate the other N−1 reviews even when the changed paths are disjoint. The issue #179
case demonstrates the conflict branch of this cascade at N=2; the general quadratic cost is an
inference, not a measurement.

Under the
[human's option-A ruling](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5550436875),
a reviewed PR whose base moves is neither merged blind nor sent immediately through another full
review. It receives a light review in two ordered, hard layers. The
[industry survey on issue #179](https://github.com/LeonJoeeee/devstandard/issues/179#issuecomment-5525494302)
found no mature system that adds a human or model interaction gate keyed on textual identity; CI on
the merged result is treated as the empirical answer, and the PRD's no-preventive-construction
boundary applies.

1. **Mechanical, hard:** a script proves that the rebase was conflict-free and every path changed by
   the PR is byte-identical before and after it. **One exemption, added 2026-09-07 (#242, #256)**
   because the human's ruling puts the version bump on the change PR: both release manifest
   version lines read as no difference when their old and new versions each agree, and where that
   exemption is what admits the comparison the new head must declare a bump against the reviewed
   head whose value, read as a dotted numeric release, sorts above both the reviewed head's and the
   replay's — so a lane cannot rebase past a merged bump and set the manifests back. The same
   exemption governs the replay that feeds the comparison: a conflict confined to those version lines
   resolves to the new base's value and the replay continues (#274). Every other byte or mode
   difference, and every conflict reaching any other path or line, still refuses.
   The same synchronized version-only predicate covers the bare-bump review waiver; a stale or
   mismatched version and non-version changes require ordinary review.
2. **Integration, hard:** CI is green on the merged result.

Both layers pass → merge. Any failure falls back to full review and dispatches a resolver where
needed (PRD §1.2, §1.4, §2.1, §2.2).

## 6. Rebuild outputs

The original rebuild opened the following implementation work after architecture approval. The
shipped source and remaining runtime qualification are recorded below; this is not a new task list:

1. Ship the two delegation rows — `worker` and `reviewer` — each carrying its role page as an inline
   `persona`, fixing one model at one effort, denying the reviewer's write tools, and binding the
   worker-only skill page (PRD §1.5, §2.3).
2. Build the fixed dispatcher: issue-field validation, worktree
   creation, delegation-instruction preparation, attribution,
   issue-side lane record, same-lane continuation through `send_message`, and cleanup
   (PRD §1.1, §1.4, §1.5, §2.2).
3. Build current-source acceptance assembly and publication: exact SHAs; green-head admission;
   complete ordinary packets from the current reviewer contract, reporting an unfilled slot to the
   reviewer rather than withholding the packet; whole-verdict return; and per-PR round accounting
   with the orchestrator-first ruling path (PRD §1.2, §1.4).
4. Split the orchestrator and worker context into the self-contained role pages, and bind
   superpowers once per role. Each page is delivered by the harness's own mechanism — the
   orchestrator's as a root-scoped system-prompt section, a worker's as its row's `persona` beside
   its own mechanics page — so the shared `core.md` ADR 0059 deleted never returns
   (PRD §1.5, §1.6, §2.3).
5. Implement and probe the hard edges: the role hook's per-role word lists at `tools/pre-execute`,
   the reviewed-head
   merge guard, the two-layer content-unchanged-rebase path (comparison script and CI on the
   merged result), branch-protection settings, and recovery
   behavior (PRD §1.2, §1.3, §2.1, §2.2).
6. Audit every current `reference/` page as keep, merge, move-to-role, or drop. Build a rule ledger
   that gives every retained clause its role, act site, enforcement tier, and PRD trace; a drop needs
   the human's approval. This ledger is implementation evidence, not a new shipped rules page (PRD
   §1.6).
7. Write the superseding and amending ADRs indicated below when their implementation lands. ADR
   bodies remain immutable; only status lines and dated amendment blocks change (PRD §1.5).

ADRs 0045, 0056 and 0063 traced a Codex host's removal and restoration; this repository's port
supersedes them (ADR 0064) and is recorded in the ADR log rather than here.

## 7. ADR dispositions and traceability

This table finalizes the preliminary inventory on issue #179 against the approved PRD and the later
human rulings. It records what the rebuild must do and names the ADRs as their implementation lands.

**Reconciled 2026-09-07 (#207).** Every row below now names the ADR that carries its disposition,
and the dated amendment blocks are appended on the ADRs the rebuild overtook. ADR bodies were not
rewritten; a row whose disposition needs no ADR says so.

| Disposition | ADRs | Reason |
|---|---|---|
| Already superseded; history only | 0001–0005 | Later ADRs already replaced the initial package, superpowers, execution, lifecycle, and fixed-session forms. No rebuild action, and no ADR needed. |
| Stands as foundation | 0000, 0009, 0012, 0013, 0017, 0018, 0020, 0022, 0023, 0025, 0026, 0031, 0033, 0034, 0037, 0041, 0042 | ADR discipline; GitHub collaboration; worktree lifecycle; task-level design and document admission; operational memory; red-main recovery; universal PR/review/CI; record language; CI fallback; PR ownership; reference sizing; verdict publication; placement; and clean handback remain required by this architecture. Unchanged by the rebuild, so no ADR needed. |
| Superseded by the rebuild | 0006, 0008 → 0047; 0014 → 0048 | The native Workflow tool is no longer the whole harness because fixed dispatch and packet machinery are required, and direct in-session work is no longer the default beyond one- or two-line changes and research (0047); the full/light/mini setup fork is removed and weight is a bound on each issue (0048). The reusable parts of each decision — run sizing, rationing, and "the agent never guesses scope" — are restated by the superseding ADR. |
| Superseded by 0045 (issue #200), then 0045 superseded by 0056, then 0056 by 0063, then 0063 by 0064 | 0038, 0039, 0045, 0056, 0063 | Rebuild 0 removed Codex host delivery. ADR 0056 restored the host with shared roles, native workers and independent read-only CLI gating review; ADR 0063 removed it again on the human's ruling (#459), keeping Codex as a dispatched CLI executor; ADR 0064 removes the Codex executor and the Claude host together for this repository's dsh delivery. The older role-marker and adoption designs remain history. |
| Amended for role delivery | 0007, 0015, 0016, 0019 → 0049; 0015, 0036, 0040 → 0047; 0024 dated block; 0024, 0040 → 0050 | Static context is now one delivered artifact per role, injected by default with the carrier chosen from a measured size and a CI gate that fails an over-cap artifact (0049). The dispatch-first rule and the retirement of the ladder's rung vocabulary ride 0047. ADR 0050 supersedes 0024's cap and 0040's restatement; as amended 2026-09-19 (#406) the worker and the reviewer are anchored rather than routed by kind of work. ADR 0066 supersedes 0050's routing for this repository: one model at one effort, one anchor in the bundle's `cordis.patch.yml`, no tiers and no helper table. ADR 0045 reconciled the Codex host removal earlier. |
| Amended for acceptance and concurrency | 0011, 0035 | Already carried: the goal-centric contract by 0044, and the two-layer light review by 0046. Added 2026-09-07 as dated blocks on 0011, 0035 and 0046: the manifest version-line exemption to the byte-identical clause (#242, #256). Resolver dispatch needs no block here — it leaves both gates and the reviewed-diff rule as written; the live statement it overtook is 0015's, which its 0047 block carries. |
| Repository operations; unaffected | 0010, 0021, 0027–0030, 0032, 0043 | Rename history, this repository's pipeline upkeep, wording sweeps, translation and changelog policy, repo-only placement, and page-audit rules do not define the target collaboration model. No ADR needed. |
| Reviewer-contract ADR | 0044 | It records the approved Goal/Floor/Notes contract from PR #188; this architecture does not duplicate or supersede it. No ADR needed. |
| Written by the rebuild | 0045, 0046, 0047, 0048, 0049 | Codex host removal; the guarded merge and content-unchanged rebase; the shipped collaboration machinery with dispatch as the default; weight as a per-issue bound; and per-artifact injected role context. Each rode the PR that implemented its decision, except 0047–0049, which reconcile decisions already landed across Rebuild 0–6. |
| Host restoration, removal, and the dsh port | 0056, 0063, 0064 | 0056 added Codex packaging and a bounded host adapter around the existing collaboration machinery; 0063 removes them and keeps the Codex CLI executor; 0064 replaces the host surface with a dsh bundle for this repository, superseding 0063. All preserve the role split, guards, review contract and historical ADR bodies. |
| Written by the dsh port | 0064, 0065, 0066, 0067 | This repository delivers DevStandard natively for dsh; dispatch is the host's own subagent and a lane's isolation is the worktree, the role hook and review; every dispatched role runs one model at one effort; and the bound superpowers craft is ported into the package. |

### Structure traceability

| Named structure | PRD source | Why it exists |
|---|---|---|
| Supplementary harness for dsh, dispatching dsh's own subagents | §1.1, §1.5 | Native sessions do not supply the collaboration protocol or assumed team conventions. |
| dsh as the only host | §1.6, §5 | This repository delivers the method natively for dsh (ADR 0064); the Claude Code project continues as a sibling. |
| GitHub as durable coordination state | §2.1 | Reuses issues, PRs, review, and CI rather than inventing an agent state machine. |
| Orchestrator context set | §1.1, §1.5 | Removes human scheduling and delivers main-loop conventions to a fresh session. |
| Dispatched-executor purpose × host row | §1.1, §1.5 | Enables parallel execution while carrying the same role contract through one harness's delegation rows. |
| Worker context set and worker role reference | §1.2, §1.5, §2.3 | Makes completion evidence-bearing, supplies conventions, and binds execution craft. |
| Reviewer context set and ordinary packet | §1.2, §1.4 | Distrusts completion claims and stops peripheral review drift through a clean, current judging packet. |
| Resolver as a worker purpose | §1.2, §2.2 | Keeps conflict changes isolated and re-verifiable without granting merge authority. |
| Root-scoped system-prompt delivery of the orchestrator set | §1.5 | Ensures a fresh orchestrator receives the conventions it otherwise lacks, without a hook. |
| dsh worker-mechanics page | §1.5, §5 | Maps dsh's mechanics for a dispatched worker without copying the method, and is delivered beside the worker contract. |
| Harness-native carrier choice | §1.5, §5 | Makes static context delivery reliable: the orchestrator's page is a root-scoped system-prompt section and each role's page is its row's `persona`, delivered whole rather than read from a pointer. |
| Worker/reviewer delegation rows | §1.5, §2.3 | Carry the fixed role text, tool surface, model and role-bound skill bindings, because a dispatched child's role arrives as its `persona` — there is no session hook to deliver it and no read to perform. |
| Fixed dispatcher and same-lane continuation | §1.1, §1.4, §1.5, §2.2 | Creates N isolated lanes, keeps fix state in the lane rather than the executor, and reaches the same child through `send_message`. |
| Background delegation and the returned child id | §1.1 | A delegation runs in the background and its id is recorded on the issue; the child's end is observed at the tool boundary, not inferred. |
| Current-source ordinary review-packet assembler | §1.2, §1.4 | Delivers a complete, non-stale fulfillment claim to a clean reviewer. |
| Hard / structural / soft enforcement tiers | §1.2, §1.3, §1.5 | Mechanizes evidence and safety boundaries while retaining judgment only where required. |
| Workflow 3 edge tiers | §1.2, §1.3, §1.5, §2.2 | Assign evidence, stop, and isolation mechanisms to every worker-execution step without duplicating the PRD workflow. |
| Worktrees, branch protection, and CI-green-before-review order | §1.2, §2.1, §2.2 | Reuses native isolation and integration enforcement while ensuring the reviewer judges a green PR and merge requires both gates. |
| Reviewed-head merge guard | §1.2, §2.1 | Prevents an acceptance verdict for one head from authorizing a different merge unless both hard layers prove the rebased content unchanged — chapter 5's manifest version-line exemption apart — and the merged result green. |
| The role hook at `tools/pre-execute` | §1.3 | Refuses the ordinary spelling of the operations a role must never perform, cheaply enough to hold in one's head, without refusing ordinary work, and with nothing to configure: since ADR 0052 the words are in its source and it reads no file, no ref and no network, and since ADR 0051's 2026-09-11 amendment it judges a command's own text and never a tool name — no allowlist anywhere, with what a role may reach left to the delegation row's denials. Since ADR 0062 it refuses three things — a worker's `merge`, the orchestrator's `gh pr merge`, a reviewer's `gh api` write flags — plus the worker default-branch push that branch protection takes over, because a word that named a reversible act bought its refusals with false ones. |
| GitHub-first lane observability | §1.1, §1.2, §2.1 | Lets the orchestrator reconstruct state without trusting a worker's self-report. |
| Scope cutting and N-way lanes | §1.1, §2.2 | Provide parallel throughput while reducing writable overlap. |
| Per-PR round decision, reported round count, and orchestrator-first ruling | §1.1, §1.4 | Bounds revision without making the human schedule ordinary continuation decisions. |
| Same-lane goal repair and the two Floor-failure transitions | §1.2, §1.3, §1.4, §2.2 | Returns an evidence-free claim for proof while stopping unauthorized irreversible or out-of-scope work instead of treating it as a normal fix. |
| Resolver full review and two-layer content-unchanged-rebase light review | §1.2, §1.4, §2.1, §2.2 | Reviews changed conflict resolutions fully while checking byte identity — chapter 5's manifest version-line exemption apart — and merged-result integration for an unchanged PR. |
| Rule ledger and reference-corpus disposition | §1.6 | Prevent silent loss while deleting every clause that lacks a PRD reason. |

Decisions and their reasons: `docs/adr/`.

### Hard-edge implementation evidence (#204)

`scripts/guard` implements the reviewed-head/current-base check and the two-layer rebase path;
`scripts/dispatch` carries lane admission. Constructed negative
probes live in `.github/test-hard-edges.py` and `.github/test-dispatch.py`. The live protection
fixture refused while main passed, as recorded on #204. ADR 0046 records the interfaces;
`reference/orchestrator.md`'s Guarded operations section owns their operation. **The match/authorization defaults settled on
2026-09-06 (#204, #223) no longer exist**: the human signed off on the architecture-level change and
delegated three proposed defaults to the main session, which shipped them in a configuration file —
and ADR 0052 deleted that file with every rule that read it on 2026-09-10. Live host
enforcement remains **Unverified**, assigned to the main session by #204's second continuation
ruling; `.github/test-dsh-bundle.py` is the closest thing to a live probe, and neither command
matching nor classic status protection alone proves zero unauthorized
operations or a complete PR-only capability boundary.

**One rule per role (2026-09-10, #323).** The machinery above — a closed shell grammar, a
ten-family refusal table, a per-tool-call policy read from the remote default branch, an
authorization record for every irreversible orchestrator command, and a retry layer for the network
faults that read caused — cost seven review rounds and three releases over 2026-09-09/10 and still
refused ordinary research commands. On the human's ruling the hook reads command text instead of
parsing it and decides on a short word list per role, and no read failure can produce a refusal.
Each refusal is written as a reminder rather than a wall — the
word, what the role does instead, its page, and how to re-spell a benign command — because a
textual scan will sometimes hit one. The residual is accepted rather than chased. ADR 0051 records
the ruling, `reference/orchestrator.md`'s Guarded operations section owns the operative wording, and the rows above are written to
it.

**No configuration file (2026-09-10, #326).** The same day's second ruling finished the first one.
The chain that produced a policy file ran: a hook to stop a subagent writing to GitHub → a file so
the hook knew who the human was and what to require → rules for reading the file → an issue about
where the file lives; each layer solved the previous layer's problem. **The hook stays and
everything that existed only to feed it goes.** The word lists are in the source, the default
branch is `main` or `master` by name, `guard merge` keeps its own GitHub reads, derives the
repository owner from the repository's API record and judges CI by its own read of the head's
checks, with no name list to configure; `guard protection --apply` takes its check names from the
command line. The founding admission below is now the absence of a rule rather than a carve-out,
and the authorization record, the authorization issue and the standing-release entry are retired. ADR 0052
records the ruling and the chain it undoes.

**Founding admission (2026-09-07, #293; retired 2026-09-10, #326).** Proven policy absence once
narrowed what the guard granted and then also admitted one operation, because an authorization
record could not precede the policy file that named its issue. **The admission has no code left.**
Its protection half was dropped on 2026-09-10 (#323) with the remote reads; its policy half went
the same day with the file (#326), because the orchestrator's word list no longer carries `push`
at all. GitHub's own branch protection is what rejects a push to a protected branch, which is the
layer that check belongs to. `reference/orchestrator.md`'s Guarded operations section owns the wording and its limits; ADR 0046's
2026-09-07 and 2026-09-10 blocks record the admission, its narrowing and its retirement.

**Three rules (2026-09-20, #425).** The #379 audit read every word in the lists against one bar:
does it name an act that is irreversible *and* that no other layer stops? Three cleared it — a
worker's `merge`, the orchestrator's `gh pr merge`, a reviewer's `gh api` write flags — and every
other word was refusing reversible work while admitting the spelling that mattered. `tag` refused a
local `git tag` and admitted `git push --tags`; `release` refused `cargo build --release` in every
target project; `--force` stranded a worker on the lease-protected push its own brief required
(#236); the reviewer's whole list admitted `gh pr comment`, `gh pr review --approve` and
`gh pr edit`, so it carried no independence at all. The recursive-`rm` rule with its `/tmp/`
carve-out, and the re-spelling detour every refusal carried, go with them: the detour existed to
route around refusals these three do not make. **What widens is named rather than chased** — a
reviewer's shell reaches GitHub writes outside `gh api`, and a worker's recursive `rm` reaches any
target — because read-only is the `reviewer` row's write-tool denial, and the lane is a disposable
worktree whose branch is already pushed. ADR 0062 records the
ruling, and `reference/orchestrator.md`'s Guarded operations section owns the operative wording.

### Rebuild and port implementation evidence (2026-09-07, #207; ported 2026-10-05)

Rebuild 0 through 6 landed the mechanisms this document specifies, and the dsh port replaced the host
surface. `scripts/dispatch` validates the issue contract, creates and records the lane, and prepares
a delegation instruction (#202, #213; ported in #17). `scripts/review-packet` assembles current-source
packets, refuses a red or unreported head, publishes the whole verdict, and accounts rounds against
the cap (#203, #222; ported in #17). `scripts/guard` with `scripts/hard_edges.py` implements the
reviewed-head merge and the two-layer rebase proof (#204, #223). The bundle's `index.js` and
`cordis.patch.yml` rows deliver each role's page (#4, #6), and `guard.js` carries the role hook at
the host's `tools/pre-execute` (#8). Their constructed tests live in `.github/`. ADRs 0047 and 0049
record the decisions behind the shipped machinery and the delivery split; 0048 records weight as a
per-issue bound.

**Source labels reconciled 2026-09-11 (#342).** The original 2026-09-07 qualification (#279) told
readers to reinterpret absent-mechanism cells using this implementation record. The cells now name
the shipped source directly. Constructed tests qualify the mechanism they reach, not unrelated
behavior. What constructed tests leave **Unverified** includes live enforcement of the role hook at
the host's `tools/pre-execute`, and
the complete recovery path exercised as one sequence. A passing constructed probe is not a proof
about the harness.

### Port qualification (2026-10-05)

The bundle's live run drives `dsh --profile headless` against a local deterministic
OpenAI-compatible endpoint with the bundle composed in, and it gates the `dsh` CI job on macOS and
Ubuntu (`.github/test-dsh-bundle.py`, ADR 0064). **Verified — repository source and live run:** the
root's request carries `reference/orchestrator.md`'s exact bytes and no child's does; the `worker`
child carries `reference/worker.md` and not the reviewer's page; the `reviewer` child carries
`reference/code-review-prompt.md`, holds no write tool, and refuses a scripted write call; both
children carry the bundle's one model anchor; and the role hook refuses each role's own word through
`tools/pre-execute` and admits an ordinary command. A child maps to its own role through its durable
`subagent/descriptor` `persona`, not the worker-and-reviewer union (ADR 0062's 2026-10-06
amendment, issue #8). `.github/check-dsh-bundle.py` and `.github/check-dsh-guard.py` are the static
halves of the same gate.

**Unverified:** persistent UI resume, clear and compaction behavior; matcher-fixture coverage does
not qualify those UI transitions. The port claims no per-child OS sandbox: an in-process child
inherits the session's permissions and cwd, and the guarantee layers are the merge guard, branch
protection and the reviewer row's write-tool denial.

### Removed host (history; ADR 0064)

The Codex host and CLI executor and the Claude CLI worker this repository inherited were removed by
ADRs 0063 and 0064. Their qualification evidence, the retired runtime tests and the CLI supervisor's
lifetime machinery lived here before the port; the ADR log now records the removal, and nothing in
this document depends on them.
