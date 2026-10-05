# 0018 — A repo-root CLAUDE.md joins the doc set: operational memory for clean-context workers

Status: Accepted (2026-07-16). Amended by 0045 (2026-09-05). Amended (2026-07-25). Amended by 0030. Amended (2026-08-13). Amended (2026-08-25). Amended by 0037 (2026-08-25). Amended by 0038 (2026-08-26). Amended by 0039 (2026-08-26). Amended by 0041 (2026-08-28). Amended by 0042 (2026-08-31). Amended (2026-09-07). Amended by 0056 (2026-09-11). Amended by 0063 (2026-09-29). Amended by 0064 (2026-10-05).

## Context

The optimization sweep's one genuine blind spot (`_source/devstandard-optimization-sweep.md`, proposal 2): the method is structurally amnesiac. Clean context is the design — fresh workers, fresh reviewers — so written memory is the only memory. Yet the doc set held design (`docs/architecture.md`), decisions (`docs/adr/`), and tasks (GitHub issues), and had **no home for operational facts**: which command runs the tests, which port is taken, which untracked files a new worktree must copy (`aids/worktree-lifecycle.md` referenced a "declared allowlist" that nothing ever created). Every fresh worker re-derived them by trial and error, or failed review on something one line would have prevented — the same lesson re-bought forever. A repo-root `CLAUDE.md` is the field's most-converged practice, and Claude Code reads it **natively** at session start — the same mechanism as the personal `~/.claude/CLAUDE.md`, scoped to the repo. AGENTS.md was rejected earlier for double-injection risk; CLAUDE.md carries none — it is Claude Code's own channel, separate from this plugin's hook.

## Decision

- **Every full setup generates a repo-root `CLAUDE.md`** in the same step as CI, when the project's commands have just been settled (section + template in `howto/cicd.md`). One page hard max; three kinds of content, nothing else: commands (install / test / run), environment gotchas, and the untracked-files list a new worktree copies. The template's last line is its fence: architecture, decisions, and task state live in their own homes and are never duplicated here.
- **Merge-time write-back** (`aids/worktree-lifecycle.md`, Death): before tearing down a merged task's worktree, ask — did this task expose a command, gotcha, or rule that would have prevented a review finding or a worker dead-end? If yes, one line into `CLAUDE.md` through the small-change lane. A design decision goes through the architecture process instead — never a quiet note.
- An existing repo adopts by a normal small change whenever wanted; the human's light-start declaration is respected as everywhere else.

Rejected: keeping lessons in session memory (evaporates by design); a new log file (the sweep found no load-bearing precedent, and a log is append-heavy where this file must stay one curated page); AGENTS.md (double-injection — already rejected and the reason still holds).

## Consequences

Operational facts reach every session, worktree, and separate session automatically (it is a tracked file — a worktree checkout carries it, and Claude Code loads it without being asked). Lessons stop evaporating: the file grows one line at a time, each line bought by a real incident. Costs: about a page of context per session in that repo, capped by the fence and the one-page rule; one extra question at every teardown. The plugin's own repo carries the first instance.

**Amendment (2026-07-25):** generation is conditional, not unconditional — a project generates the file only when it has commands, gotchas, a copy-list, or a non-English record to declare (howto/cicd.md); otherwise the first real line creates it through the write-back lane. The plugin's own repo no longer carries an instance: everything it held is now CI-enforced or convention (issue #66).

**Amendment (2026-08-06, see 0030):** this repo carries a root `CLAUDE.md` again. The
2026-07-25 amendment recorded that everything it held had become CI-enforced or convention, and
that was true then. It now holds a **Commands** section — this repo's four CI gates, which
were reconstructable only from `ci.yml` — plus two declarations that exist nowhere else: the
reworded-rule sweep, withdrawn from the shipped method as repo-only practice (0030), and the
human's standing delegation of per-release approval (issue #37), which lost both of its earlier
homes. **The conditional this ADR states is satisfied; 0030 widens this ADR's content fence for
this repo alone** — Commands meets the enumeration, and repo-ops practice is an additional kind
admitted here only. The fence `howto/cicd.md` ships to target projects is unchanged.

**Amendment (2026-08-13, caused by 0031):** four live pointers above now read `reference/`, one
per site rather than a count. **Decision bullet 1's** "(section + template in `howto/cicd.md`)" is
`reference/repo-claude-md.md` — 0031 split `cicd.md` into four files, so "now reads `reference/`"
does not name an address on its own. **Decision bullet 2's** "(`aids/worktree-lifecycle.md`,
Death)" is `reference/worktree-lifecycle.md`, "## Death", step 2 — and while there: that bullet's
*"through the small-change lane"* was retired by 0022, which made ceremony universal; the write-back
now rides a short-branch PR like any other change, as that file states. **The 2026-07-25
amendment's** "(howto/cicd.md)" and **the 2026-08-06 amendment's** "the fence `howto/cicd.md` ships
to target projects" are both `reference/repo-claude-md.md`, which carries the conditional-generation
rule and the three-kinds fence. Every rule named is unchanged — only the addresses, and the retired
lane.

**Amendment (2026-08-25, issue #132):** the "One page hard max" in Decision bullet 1 gains the two
things it never had — a measurable proxy and an owner. **The cap is unchanged;** what was missing is
that it could not fire. One page had no number a worker could check, and growth was one-directional:
this ADR's own write-back mechanism only ever appends, and nothing said who removes a line, when, or
by what test. Every long-lived project reaches the cap and then quietly exceeds it, because exceeding
it is nobody's job to notice.

**~30 lines** is the proxy — roughly twice the template `reference/repo-claude-md.md` ships, which is
what a filled-in instance of that template runs to. It is a rendering of "one page", not a new
allowance. **The trim is enforced at write time by whoever is writing:** a write-back that would cross
the cap also drops the line it most clearly supersedes, or otherwise the stalest gotcha — never a
separate cleanup pass, because a pass with no trigger and no owner is how the cap stopped binding in
the first place. Gotchas are the eviction default because they are what the write-back mechanism
grows fastest; Commands and the copy-list are what a cold worker cannot function without.

Recorded here rather than left in the reference file's prose alone, because a future session wanting
to move the number needs the reasoning, not just the number. `reference/repo-claude-md.md` carries the
operative wording.

**Amendment (2026-08-25, see 0037):** the "Gotchas" kind admits one more instance — **a cache or
deploy root the repo uses outside its own tree** (`~/.cache/foo`, `/srv/app`). It is an environment
gotcha of exactly the kind already fenced — a fact about the machine a clean-context worker needs so
it does not invent its own location for a download or a deploy (0037, `reference/out-of-repo-writes.md`)
— the same shape as "port 3000 is taken", recorded here rather than as a new kind, following the
2026-08-06 amendment's precedent of placing new content inside an existing kind. The three-kinds
fence and the one-page rule are unchanged.

**Amendment (2026-08-26, see 0038):** the Rejected line's `AGENTS.md (double-injection — already
rejected and the reason still holds)` clause is qualified — not removed; this log is append-only.
That rejection was of `AGENTS.md` as *this method's operational-memory channel* on Claude Code —
and as such it stands: `CLAUDE.md` remains that channel, on
every harness (a Codex worker reads it explicitly and writes back through its PR — 0038). What 0038
adds to a repo, on request, is a *fallback delivery block* in `AGENTS.md` — Codex startup guidance
for environments where the session hook is unavailable, never memory — so a repo using DevStandard
on both harnesses may carry both files. The double-injection concern does not transfer: **measured,
Claude Code does not read `AGENTS.md` at all when a `CLAUDE.md` is present** (a sentinel in each;
only the `CLAUDE.md` one loaded), and even were a future Claude Code to read it, the block holds no
operational memory — its worst case is a redundant role note, never the *second, conflicting*
injection this ADR's double-injection concerned. The two files stay what they are — `CLAUDE.md` is
the project's memory, `AGENTS.md` is Codex-side startup guidance and fallback delivery.

**Amendment (2026-08-26, see 0039):** the 0038-era block above is reframed — there is no managed
`AGENTS.md` block or adopter any more; the fallback is a README-documented snippet for hookless
environments only, prepended into the repo's effective instruction file. `CLAUDE.md` remains the
operational-memory file on every harness (a Codex session reads it explicitly and writes back via
PR), and the co-presence measurement recorded below stands.

**Amendment (2026-08-28, see 0041):** merge-time write-back no longer invites an unrestricted
“rule.” It writes only the fence this ADR already admits: a command, environment gotcha, worktree
copy-list entry, or record-language declaration. A design rule stays in architecture/ADR, and task or
handoff state stays on the issue or PR. The conditional creation rule, content fence, and line cap are
unchanged.

**Amendment (2026-08-31, see 0042):** recording a cache or deploy root in `CLAUDE.md` relays a place
that pre-existing authority already assigned to this project or the human chose. The line never
authorises a root the same change invents; the Gotchas kind and the content fence remain unchanged.

**Amendment (2026-09-05, see 0045):** The Codex startup fallback described by the 0038/0039 amendments and the README snippet are retired with Codex host delivery. `CLAUDE.md` remains the operational-memory file for the orchestrator and workers; `reference/worker-brief.md` now carries the explicit read requirement for Codex executors. No DevStandard delivery block is installed in `AGENTS.md` or `AGENTS.override.md`.

**Amendment (2026-09-07, issue #279):** the 2026-09-05 block's *"`reference/worker-brief.md` now
carries the explicit read requirement for Codex executors"* names a page #235 reduced to a
compatibility pointer and #270 deleted. `reference/worker.md` carries that requirement, in the
before-the-first-write step that tells a worker to read the repo-root `CLAUDE.md` **IN FULL** and
says Codex must read it explicitly. Everything the block records about this ADR stands: `CLAUDE.md`
remains the operational-memory file for the orchestrator and workers, and no DevStandard delivery
block is installed in `AGENTS.md` or `AGENTS.override.md`.

**Amendment (2026-09-11, see 0056):** 0056 restores Codex main sessions as readers of the canonical
`CLAUDE.md`, explicitly alongside existing `AGENTS.md` instructions. No operational facts move, and
no managed delivery block is installed in either AGENTS file. The content fence, conditional
creation and write-back lane remain; `reference/repo-claude-md.md` owns this memory rule.

**Amendment (2026-09-29, see 0063):** 0063 removes Codex main sessions. `CLAUDE.md` stays the
operational-memory file: the Claude Code orchestrator and every dispatched worker read it, a Codex
worker explicitly, alongside a project's existing `AGENTS.md`. No managed block is installed in
either file; `reference/repo-claude-md.md` owns the rule.

**Amendment (2026-10-05, see 0064):** the instructions file is the host's. dsh reads `AGENTS.md` and
`CLAUDE.md` in one chain, per agent, so the rule names the repo-root file the host reads rather than
Claude Code's own; a dispatched worker receives the project's file exactly as before. `CLAUDE.md`
remains a name that host reads, not one this method requires. `reference/repo-claude-md.md` owns the
rule.
