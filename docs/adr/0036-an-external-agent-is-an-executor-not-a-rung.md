# 0036 — Another vendor's agent is an executor choice, not a new rung

Status: Amended by 0050 (2026-09-09). Accepted (2026-08-25). Amended by 0045 (2026-09-05). Amended by 0038 (2026-08-26). Amended by 0040 (2026-08-26). Amended by 0047 (2026-09-07). Amended (2026-09-07). Amended (2026-09-11). Extends 0008 (the ladder's executors; the rungs, run sizing and
rationing are unchanged). Cites 0024 without amending it: the cap and the tier names stand for every
agent this method spawns through its own harness, and do not reach a process it does not spawn. Amended by 0056 (2026-09-11). Amended by 0063 (2026-09-29). Amended by 0065 (2026-10-05).

## Context

The ladder (0008, amended by 0024) names its executors in Claude Code's own primitives — in-session,
Agent-tool subagents, Workflow-tool runs. Another vendor's coding agent, invoked as a process, fits
none of those names while doing the same work. The question was whether the method should say so.

**This was designed twice and rejected twice before anything shipped, and both rejections are the
reason to trust this one.** The first draft claimed mechanics "verified" against a CLI it had never
run; a challenge ran them and found the flagship invocation did not parse. It also failed 0032's
weight test outright — this repository had dispatched to such an agent exactly zero times, the same
ground on which issue #76's fully-designed proposal was shelved. The human's ruling was to pilot
first.

Five dispatches followed: four `reference/*.md` batches and one code change to this repo's own ADR
gate, each on its own branch and worktree, each through check 1 like any other work (PRs #136–#139,
#142). The second draft was written from that pilot — **and its challenge found two claims the
pilot's own record contradicted.** One asserted an attribution rule was practised every time when it
had lapsed on the batch dispatched *after* the gap was written down. The other blamed a factually
wrong `git branch -d` claim on the external agent when `git log -S` puts its first appearance in a
commit written by the main session.

So the evidence for this ADR is: **the practice works and the writing about it kept overstating.**
That shapes what follows — the rules below are the ones the pilot forced, and the ADR says where the
evidence is thin rather than papering over it.

## Decision

**An external agent is an admissible executor wherever the ladder hands work to a fresh subagent or a
separate session — implementing, reviewing, or challenging a design. It is not a new rung**, because
the rungs measure how much machinery the work needs, and the executor's vendor is orthogonal to that.

**Almost nothing else changes, and that is the finding, not a convenience.** A worker never merges;
one writer per worktree; done claims carry evidence; every gating review gets a clean reviewer that
did not write what it reviews; the reviewed diff is the merged diff. Every one of those is already
blind to who executes. The pilot needed none of them restated.

**Not a dependency.** Unlike superpowers (0016), a project without such a tool loses nothing: every
rung keeps its existing executor. The shipped text is permissive throughout; nothing prefers an
external agent, and no claim is made that a second vendor reviews better — that argument is real but
unmeasured, and asserting it would be a claim with no evidence behind it.

**Routing: set it explicitly; the level is the human's.** 0024 has two halves and only one transfers.
Its *cap* does not: `opus` is a Claude tier, and naming another vendor's model ids here is the
silent-rot failure 0024's Rejected (b) already refused. Its *"set the model on every spawn that takes
one"* does, and extends to any effort or reasoning knob the tool exposes — because such tools read a
config file when a flag is omitted, so an unset flag is not "no choice", it is a choice made
somewhere no reviewer will look. **Which level** is the target project's human to set, exactly as
their own session model and quota budget already are.

**Sandbox by role**, and stated because the pressure is real: reviews and design challenges run
read-only, so that the constraint is OS-enforced rather than promised in a prompt; implementing runs
get write access scoped to their worktree; a bypass-everything mode is never used, and a
sandbox-blocked action is a stop-and-tell like any other, never a reason to re-invoke with a looser
flag.

**The return file is the output channel.** `reference/worker-brief.md`'s "return the message in your
output to whoever spawned you" is satisfied by the file the agent's final message is written to. A
separate session's channel — a comment on the issue — does not apply, because nothing is watching
for one. Two consequences the pilot met: it cannot ask a question mid-task, so an unfilled field in
the brief gets guessed at rather than queried; and its report is a claim to verify, not a result.

**The record names the executor** — a trailer on a commit whose diff it wrote, and the reviewer named
in a verdict. Git's author field carries the local credentials for any local agent, so nothing else
distinguishes it. This matters most for a gating review: if independent judgment is the reason to use
a second vendor, a record that cannot say which vendor produced a verdict cannot support that reason
later.

**Unavailability never lowers a bar.** Missing, unauthenticated, or erroring → fall back to the
harness's own executor and say so. Skipping or weakening a review because an executor was
unavailable is the availability-keyed exception this method rejects everywhere else (0035).

Rejected: **a preference rule** ("use a different vendor for gating reviews") — the cross-vendor
independence argument is plausible and unmeasured, and shipping it would state as method what is
currently a hunch. Rejected: **a second reconciliation rule** for two vendors' rounds disagreeing —
the existing machinery already handles two rounds disagreeing (findings block until fixed and
re-reviewed); what was missing was only the attribution, above. Rejected: **folding this into
`reference/worker-brief.md`** — that file is what gets *pasted to* a worker; this is what a caller
does, a different reader (0031).

## Consequences

`core.md` pays two clauses — one on the ladder's rung 2, one on check 1's reviewer. Both are needed:
the pilot's only review dispatch was check 1 on PR #135, which the merge section governs and rung 2
does not. `reference/external-agent.md` carries the mechanics; `reference/worker-brief.md` gains a
clause naming the return file as the output channel, since its two existing channels fit a process
in neither form.

**What to watch, and it is named rather than solved: attribution has no gate behind it.** It lapsed
once already, on the best-informed dispatch of the pilot. Where this method has made a rule of this
shape stick, it did so by putting the instruction where the act falls due rather than where the work
is commissioned (0034) — here that means writing the attribution requirement into the dispatch brief
so the agent emits it. That is guidance, not enforcement, and this ADR does not claim otherwise.

**The evidence's shape, stated so "five dispatches" is not read as more than it is:** one operator,
one repository, four documentation batches and one code change. It clears the frequency-zero bar that
sank the first draft and issue #76. It does not establish anything about a second operator, a second
repository, or a task larger than a single file's worth of change. A target project adopting this is
extrapolating from that, and should know it.

**Mechanics are verified against one tool only.** `reference/external-agent.md` says so in the file
rather than in this ADR alone, because the file is what a future contributor will edit when adding a
second tool — and the failure this project already made twice is claiming verification it did not
have.

**Amendment (2026-08-26, see 0038):** the Consequences sentence *"The shipped text is permissive
throughout; nothing prefers an external agent"* — and the Rejected **preference rule** — are
overturned on one axis only: on these projects **Codex is the standing external executor** (the
human's ruling; the community and measured evidence are recorded in 0038). Neutrality stands for
every other tool, and the companion stance sharpens rather than reverses the review caution this ADR
recorded: an external reviewer's findings are verified before acting, never auto-applied.

**Amendment (2026-08-26, see 0040):** two stances above are reversed by the human's ruling. "Nothing prefers an external agent" — the pages now say: where Codex is installed, dispatched work goes to Codex, and a harness-native subagent only where the work especially suits one (`reference/external-agent.md`, "When a subagent, when Codex"). And "naming another vendor's model ids here is the silent-rot failure 0024's Rejected (b) already refused" — the standing model and effort are now written on that page, once and dated, so the rot is bounded to one visible line. One narrowing rides along: "anywhere this method would hand work to a fresh subagent or a separate session" becomes rung 2 only — a process executor takes the subagent's slot; it does not replace a separate live session (the lane for work that cannot be fully specified) and does not reach into a workflow run's agents. And its fallback — "fall back to your harness's own executor" — holds only where that executor keeps the gate's properties (fresh, process-isolated, read-only for a review); where it cannot, as for a Codex main session whose `spawn_agent` inherits the writable sandbox, the gate is blocked, not lowered. The rest stands: same rules, not a dependency, set it explicitly, sandbox by role, the record names the executor.

**Amendment (2026-09-05, see 0045):** Codex-main-session dispatch and its fallback example in the 0040 amendment are removed from scope. Codex remains the standing external executor invoked by Claude Code, with its role supplied by the dispatch brief. Executor preference, explicit settings, sandbox-by-role, and the blocked-if-no-qualified-reviewer rule remain on `reference/external-agent.md`.

**Amendment (2026-09-07, see 0047):** this ADR's placement vocabulary names a ladder that no longer
exists. "Not a new rung" now reads as: an external agent is an *implementation* of a dispatched
executor's purpose, not a separate kind of work — which is the same claim, in the vocabulary that
replaced the rungs. Everything the pilot established is unchanged: same rules, not a dependency, set
the model and effort explicitly, sandbox by role, the record names the executor, and unavailability
never lowers a bar. The return channel this ADR named gains a durable companion — the dispatcher
records the lane on the issue, so a caller no longer depends on the output file alone to know the
lane exists.

**Amendment (2026-09-07, issue #279):** the Decision's *"The return file is the output channel"*
quotes `reference/worker-brief.md`, which #235 reduced to a compatibility pointer and #270 deleted.
`reference/worker.md` carries the rule in the form this ADR settled: return the message in your
output to whoever launched you, and for a process executor its output file **is** that channel, with
an intermediate caller passing it to the orchestrator. The Rejected clause naming the brief as *"what
gets pasted to a worker"* reads the same way against that page — it is what dispatch expands into a
worker's prompt, while `reference/external-agent.md` is still what a caller reads — and the two
consequences this ADR drew from a process executor's silence are unchanged, except that the lane the
dispatcher records on the issue is now a durable companion to the output file (2026-09-07, see 0047).
The Consequences sentence listing which files that change touched is history and stays as written.

**Amendment (2026-09-09, see 0050):** The Routing paragraph's refusal to choose a level now reads
as a default ladder by kind of work, with project/issue overrides; the human's own session model
stays outside the method. The Claude
cap cited here is superseded. `reference/external-agent.md`, “Route it explicitly”, owns both
executors' model/effort defaults, including nested helpers. Explicit settings, executor
preference and gate properties remain; the standing dispatch record remains single-sited and
dated.

**Amendment (2026-09-11, see issue #332):** the shipped pages no longer prefer the external
executor. Dispatched work goes to the host's own subagent, and the human's instruction — for one
dispatch, or standing until their next — selects Codex (ADR 0040's 2026-09-11 amendment;
`reference/external-agent.md`, "When a subagent, when Codex"). This does not restore the original
stance quoted above: the pages do not return to silence on the choice, they state a default and
name who changes it. The rest of the 2026-08-26 block stands — the dispatched-executor slot, the
dated standing setting, and a fallback only where it keeps the gate's properties.

**Amendment (2026-09-11, see 0056):** The 0045 block's exclusion of Codex-main dispatch is retired
by 0056. A Codex host uses native workers and independent read-only CLI gating review, retaining
explicit settings and evidence. The unavailable-executor fallback still requires the gate's
properties; it never lowers them. `reference/external-agent.md` owns these implementation bindings.

**Amendment (2026-09-29, see 0063):** 0063 removes Codex-main dispatch and native Codex workers, so
the 0045 block's exclusion applies again. Codex is the CLI executor a Claude Code orchestrator
invokes, under its OS sandbox; the unavailable-executor fallback still keeps the gate's properties
and never lowers them. `reference/orchestrator.md`'s Dispatching to an executor section owns these
bindings.

**Amendment (2026-10-05, see 0065):** the executor set narrows to one. This repository dispatches to
the host's own subagent and to nothing else, so there is no external agent to choose between; the
never-lower-the-gate fallback for an unavailable executor stands, because a gate whose executor is
missing is still blocked rather than reduced.
