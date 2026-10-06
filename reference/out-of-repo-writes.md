# Where a write goes when it is not in the repo

`reference/where-it-goes.md` is the entry point. This page applies only after that placement rule has
established that a destination must be outside the project, and gives the three expensive kinds their
specific requirements. It exists because nothing said, and so every agent defaulted to `$HOME` — which is how a
home directory fills with `~/data`, `~/services`, `~/tools`, `~/labs`, and a folder dropped on the
Desktop, none of it the human's doing.

For adding documentation *inside* the repository, use `reference/in-repo-writes.md`. For what may
remain in the working tree at handback, use your role page's The tree you hand back section.

**The line is conventional, not visible.** A tool's own documented cache — `~/.cache/huggingface`,
`~/.npm`, `~/.cargo` — is fine; a place the agent invents on the human's machine is not, and a
leading dot changes nothing (ADR 0037 argues it). Whether a destination counts as
already-established — and what a document may relay — is the entry point's authority clause
(`reference/where-it-goes.md`); this page does not restate it.

## Three kinds of write, one rule each

**1. Downloads, environments, tool clones** — model weights, a venv, a cloned tool, whether they
serve one task or many. In order:

- the tool's own documented cache, if it has one, however many tasks the material serves — and most do (`hf download` uses
  `~/.cache/huggingface` unless told otherwise; overriding that to hand-build `~/data/mage-vl` is
  the exact move that produced this rule). An evictable cache is never the only durable copy of
  material that must be kept;
- else, material that dies with the task goes to scratch; for material that must be kept, use the
  cache root the repo's instructions file relays (`reference/repo-claude-md.md`) — a relay counts only for a
  root the authority clause already admits, so read that clause before treating an instructions-file line as
  the answer;
- else, where the entry-point rule has established that the write belongs outside the project,
  **stop and tell the main session** (a worker) or **ask the human** (the main session). Never an
  invented entry under `$HOME`, hidden or not — and a spec written for this very task does not settle
  it either; the authority clause says why.

**2. A deploy root or runtime state** — where a service the project runs keeps its files. The
location is the project's call, decided by the authority clause (`reference/where-it-goes.md`) like
any other destination. What this kind adds is that the root is **documented in that repo's
instructions file or architecture doc before anything lands there**, and that a declared root also says
what it retains — which copies are removed and when — because naming the place fixes where things
go, not how many pile up: a documented `~/services` still grew fourteen release directories and a
multi-gigabyte rehearsal leftover.

**3. Scratch, drops, and task-local deliverables** — session-local, gone when the session is; release
deliverables are not this kind. Write to the
scratch the session gives you — the location your harness names, or, where it names none, one dedicated `mktemp -d` directory per task. Post any durable result to the issue, PR, or
other destination the placement rule chose. Dispatcher lifecycle scratch
stays until lane cleanup under `reference/orchestrator.md`'s Dispatching to an executor section. A dispatched worker follows the scratch binding in `reference/worker.md`; it does not
assume the invoking session's scratch is writable.
The human's Desktop and `$HOME` are never a drop target unless the human names one: showing them a
result is what the PR, the issue, and the conversation are for.

## Say where you wrote

Every durable write outside the repo is named in the PR description or, where there is no
PR, at handback — the path, which branch of the rule applied, and why. **A committed write is
reviewable; an ad hoc one is not.** If the write is in the diff — a script,
a Makefile, a CI step that fetches to a path — merge check 1 sees it and can flag an invented
location like any other line. A write done by a command typed in the session (which is what every
row of the incident that prompted this rule was) leaves no trace in any diff; check 1 sees the diff
and the report and nothing else, so nothing catches an undisclosed one.
This is a discipline the acting agent keeps, not a gate — the same shape `reference/adr.md`'s
attribution rule and ADR 0036 name for their own duties. The disclosure gives a human, or a later
audit, the one place to look; the reviewer asks for it when a task plainly needed a location (a
model, a dataset, a service) and the report names none.
