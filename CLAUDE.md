# Working on DevStandard itself

This file is **repo ops for this repository only**. It is not part of the method: nothing in
`reference/` points at it, and no seeded project receives it. Like `docs/adr/`
(below) it is copied into the plugin package, where nothing reads it — the host loads a
*project's* instructions chain, never a bundle's. Everything here is a practice we follow *while
building DevStandard*, not a rule DevStandard states.

**Never write the page total.** An ADR or a PR description may state what a change *cost* — ADR
0027's *"core.md pays 180 tokens"* for the sweep rule — because that is history and stays true
forever. It may not state what the page *measures afterwards* (`total 4,560 of 5,000`): that is a
snapshot, it is stale by the next change that moves anything, and the CI-enforced ceiling is the
only current figure a reader needs. Every such total written this month was wrong within a week —
and the ones already in `docs/adr/` stay exactly as written; an immutable body is not a defect to
clean up.

Two carve-outs. **A gate's own output quoted as evidence** — `<artifact> N bytes (cap <gate>)`
in a PR's evidence block — is the run's words, dated by the run, and is what a reviewer verifies
gate 2 against; quote it there and restate it nowhere else (including here, which is why this
example is a placeholder). And **an argument that turns on headroom** may state the distance to
the ceiling, because a delta cannot express it — but it states it once, in the ADR that makes the
argument.

**The line that decides what belongs here:** a method DevStandard *ships* goes in the shipped
pages; a practice useful only for maintaining *this* project goes here. When the two get
confused, repo-ops material ends up on a page every project pays to read every session — which
is what happened to the rule below (ADR 0030).

## Auditing our own pages (ADR 0032)

Our pages are the product, so their length is a cost every reader pays. Four rules, and when they
disagree the first one wins.

**1. Weight is earned by frequency × cost-of-getting-it-wrong *in a target project*** — never by
how vivid the incident was here. The question that finds the defect is not "is this rule true for
someone else?" (it usually is, which is why two audits passed it) but **"is its weight proportional
to how often a normal project hits it — or to how memorably we hit it?"** `reference/adr.md` failed
it hardest: 314 words on claiming a free ADR number, a collision we hit because our product is
decisions, sitting beside 66 words for the irreversible one. `reference/orchestrator.md`'s Worktree lifecycle section is
the standard — long exactly where the failure cannot be undone.

**2. A rule is stated in full in exactly one place; every other site carries the trigger and a
pointer.** One incident used to buy four documents — the CI-fallback family ran to 2,005 words
across five files. Prefer a small file sized to what the pointer asks for over pointing at a large
file that happens to contain the answer (ADR 0031); `reference/red-check.md` exists for exactly that
reason.

**3. Give the common cases, then a closing default — never chase an exhaustive enumeration of an
open-ended set.** (A genuinely closed set — a status vocabulary, an absolute NEVER list — is a
contract, not an enumeration, and rule 3 does not touch it.) Name explicitly the few cases where
taking the default is expensive, and let the default carry the rest. The signal that you are
enumerating: **round after round finds a new case the page does not decide, and the answer each
time is another rule.** **The count alone proves nothing** — a round whose findings are consequences
of the last round's fixes, or gaps in its verification, is the review working, however many there
are. Two things it never licenses dismissing: **a site whose statement has staled** (rule 2 and
*search twice*) and **a safety regression**. The review-side counterpart is operative in
`reference/code-review-prompt.md`'s Goal verdict — the open-ended-goal and stop-signal clauses,
which tell the reviewer to report non-convergence instead of writing another round's rule; #173 is
the measurement they came from.

**4. Before a page gains another rule, ask what could be removed instead — and whether the problem
is worth solving at all (ADR 0053).** Alone among these four it also ships, so read 0053 for the
statement: `reference/orchestrator.md` and `reference/code-review-prompt.md` carry the operative
wordings, and the eight-PR hook chain that bought it is the evidence.

**The trigger always stays resident.** A reader who does not recognise the situation never follows
the pointer, so rule 2 never applies to the sentence that makes someone *look* — which is why
`core.md`'s exception blocks were cleared rather than sunk. Sinking a trigger is not compression;
it is deletion with extra steps.

## Commands

Any change here is done-checked by the CI gates (`.github/workflows/ci.yml`), all runnable from the
repo root — **plus one pre-merge command that is deliberately not in CI.** A gate could be built
(`on: pull_request` already has the number and a token); 0034 rejects it because `.github/` is not
shipped, so target projects would inherit nothing from it. Quote the count nowhere: it keeps
changing, and a stated count is the snapshot-shaped claim the rule above forbids.

```sh
# Dispatcher integration checks (real git/processes; GitHub boundary doubles)
python3 .github/test-dispatch.py
# Review-packet assembly, green-head admission, publication, and round accounting
python3 .github/test-review-packet.py

# Guard, authorization, reviewed-head and constructed-rebase probes. Needs 3.11+ (tomllib)
python3 .github/test-hard-edges.py
HARD_EDGE_SHARD=0/2 python3 .github/test-hard-edges.py   # One zero-based role word-list sweep shard

# The dsh bundle gate: the role rows, the one model anchor, and the byte-identity of each
# embedded persona against its source page — one operative source per role (#16 retired the
# agent-definition gate whose byte-identity check this replaces).
# It is also the generator: after editing reference/worker.md or reference/code-review-prompt.md
# run --write, which rewrites the persona regions in cordis.patch.yml. Needs PyYAML; in CI.
python3 .github/check-dsh-bundle.py
python3 .github/check-dsh-bundle.py --write

# The dsh guard: runs the ported JS engine in guard.js and scripts/hard_edges.py over one
# corpus and fails if a decision differs, so the dsh carrier cannot drift from the policy.
# Needs `node` (the bundle is a Node package); in CI.
python3 .github/check-dsh-guard.py

# The dsh bundle end to end: the gate above, then a live run against a local deterministic
# OpenAI-compatible endpoint proving the root carries reference/orchestrator.md, the `worker`
# and `reviewer` children carry their own page and tool surface, and both run on the anchor.
# Needs an installed `dsh`, Node and pnpm; the `dsh` CI job installs them and runs it (ADR 0064).
python3 .github/test-dsh-bundle.py

# 1. no @path references (they force-load at session start)
! grep -rn "@[a-zA-Z0-9_-]*/" reference/ --include='*.md' | grep -v actions/ | grep -v anthropic | grep .

# 2. every ADR amendment block is announced by its status line, in the matching form
python3 .github/check-adr-index.py

# 3. NOT a CI gate — before merging a PR needing check 1 (see Version bumps below):
#    Counting all comments passes on a CI-FALLBACK block or a bot note, so match the verdict itself.
PR=<number>
test "$(gh api "repos/LeonJoeeee/devstandard/issues/$PR/comments" \
  --jq '[.[] | select(.body | test("[Mm]erge check 1"))] | length')" -ge 1
#    Matches the heading reference/code-review-prompt.md prescribes and scripts/review-packet now
#    emits for every returned verdict, so coverage is guaranteed rather than coincidental since #203.
#    Verdicts predating that convention carry headings of their own; on a PR that old, read for
#    yourself rather than trusting this matcher's silence.

# 4. the bundle's release manifest declares a dotted numeric version (equal to the tag, on release)
python3 -c 'import json,re; v=json.load(open("package.json"))["version"]; assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", v), v; print("release manifest", v)'
```

**The verdict is posted when it arrives, not when you remember.** Five consecutive merges once went
out with no published verdict, the last two after the diagnosis was already written (issue #118) —
so knowing the rule was never the safeguard, and command 3 above is the pre-merge check that catches
the omission. What replaced remembering is the machinery: `scripts/review-packet start` reserves the
round as a PR comment *before* the reviewer runs, so an unpublished verdict is a visible reservation
rather than nothing at all. `start` returns the `reviewer` delegation instruction; publish the whole
result the child returns with `scripts/review-packet publish --attempt ID --verdict FILE`, which
replaces the reservation with `## Merge check 1 — round N` and the unedited verdict. Check 1 still
runs read-only, and when the `reviewer` tool is missing or the child errors,
`reference/orchestrator.md`'s "When it is not there" governs: the gate blocks rather than lowering.
**The safeguard is the assembler's round accounting, not anyone reproducing a prompt correctly** —
which is why `reference/orchestrator.md` forbids a bespoke review prompt outright. Hand invocation
remains the fallback, and it inherits neither the reservation nor the accounting.

## Rewording a rule: search twice

Our product is prose, so nothing mechanical catches a stale statement. Rename a function and
the compiler finds every caller; reword a rule and **nothing responds**. Six recorded instances
(issue #79), plus several more during the 0028/0029 work.

When you change the wording of a rule that exists in more than one place, **search twice**:

1. **Every other statement of the clause** — the `reference/` files, `docs/architecture.md`, and
   the ADR that recorded it.
2. **Every site that cites or paraphrases it**, found by *its pointer to the rule* — the file
   it names, the rule's subject — and **never by the words you just added.** This is the half
   that matters and the half that keeps being skipped: searching for the word you added finds
   every site that already has it, and by construction cannot find the sites that should now
   carry it.

Reconcile each in the same diff, or say in the PR description why it needs none — a site simply
absent from the sweep is a silent omission, not a clearing.

**Cite the rule, not the line.** A `reference/orchestrator.md:NN` pointer is stale the moment
anything above it moves.
One trim of `core.md` staled **every live citation below its first cut** — four sites, three of them
in immutable ADR bodies correctable only by appending, and the cut that broke the oldest of them was
nowhere near the rule it named. Name the rule or its paragraph instead; that survives an edit, and it
is what a reader searches for anyway.

The one place a line number belongs is **an amendment recording the move** — there the number *is*
the correction, and a reader holding the old one needs the mapping. Give the rule's name beside it, so
the block still works after the next trim moves it again.

**Record the ruling, not the tally.** Do not close a sweep with "N sites" — three consecutive
review rounds on one PR were each closed by such a count, and each later pass found the count
short. A count is also the total-shaped claim the rule above forbids: it is a snapshot, and the
next commit that quotes an old path moves it. State which sites are reconciled and which are
cleared and why; if a measurement is worth giving, give it with the commit it was taken at.

Two sites take a specific form:

- **An ADR** is reconciled by appending a dated `**Amendment (YYYY-MM-DD, see NNNN):**` block,
  never by a rewritten body (`reference/adr.md`). And the distinction that decides whether it needs
  one at all — sharpened after PR #108 answered it one way for this file and the other way for
  `docs/adr/` without noticing: **would a reader *act* on the sentence, or only read it?** A
  statement they would follow — where a rule lives now, what a future action will cost — is a live
  instruction and is reconciled. A statement they would only read — what was true when the decision
  was made, what a change cost at the time — is history and never is. **Ask what the sentence is
  *for*, not what tense it is in:** a Consequences sentence listing which files a change touched
  (*"core.md, `reference/ci-pipelines.md` … are updated to carry the rule"*) is history even in the
  present tense — it records what happened; a sentence whose job is to **route** (*"X carries the
  operative wording"*, *"Operational checklist: X"*, *"the fence X ships is unchanged"*) is live
  even inside a Consequences section. **The cue is structure, not the verb:** a *standalone*
  sentence whose only job is to say where a rule lives is live; the same verb inside a list of what
  this change touched is not — "carries" appears on both sides of the line.
- **A historical record** — a merged PR description, a released tag's notes — is not a site.

## The release delegation

The role pages' two-checks paragraph says releasing is the human's call. **For this repo that call
was delegated standing on 2026-07-24** (issue #37): since v0.9.3 the agent releases right after each merge —
tag, push — with the release manifest already at its version (`package.json`), without asking per
release. The goal was that every merged improvement reaches the human's other sessions as fast as
possible.

**The delegation is issue #37, and nothing machine-readable.** It was a `standing_release` entry in
the guard's configuration file until 2026-09-10, when that file — with `human_logins`,
`record_logins`, `authorization_issue` (#204), `required_checks` and `merge_method` — was deleted
whole, along with every rule that existed to read it (#326, ADR 0052). Nothing in the hook or the
guard looks a delegation up any more, and the hook no longer recognizes `tag` or `release` at all.
What clears a release is that rule plus this paragraph.

Withdrawing it is the human's to do, and it takes saying so — on #37 or here — rather than editing a
file. **Target projects are unaffected:** there, release go/no-go
stays on the human's ask-axes and `reference/ci-pipelines.md`'s tag-triggered default governs.

**Version bumps:** fold the version bump into the change PR and put the semver call in its
description; a reviewer's disagreement is a Note, never a separate PR (human ruling, 2026-09-06,
issue #226). If a bare bump PR is unavoidable, it needs no issue or check-1 reviewer: the
release-manifest version check is its review. It still merges through `scripts/guard merge`.
The guard's bare-bump waiver and rebase exemption cover the bundle manifest's version field, with
a rising dotted version and no other line or mode changes; the rebase proof keeps its ordering
checks (`reference/orchestrator.md`'s Merge and rebase proof section).

## ADRs in this repo

`docs/adr/` ships inside the plugin package (the human's ruling on issue #93: we are the only
installer today, and the log is more useful one directory away than absent). Consequence:
**an ADR that decides how we operate, rather than what the method says, must say so in its own
title and text** — otherwise a reader in a seeded project takes it for an instruction. ADR 0028
is the model; 0029 needed three review rounds to learn it.

**Two amendment blocks of the same date share one status entry**, and that is correct rather than a
gap: the status line is a set of dates, and one `Amended (YYYY-MM-DD)` announces every block carrying
it. Verified when the first such pair appeared (0007, 2026-08-17) — removing that single entry makes
`.github/check-adr-index.py` fail on **both** blocks, so nothing hides under it. Not to be confused
with the dateless `Amended by NNNN` gap ADR 0033 records, which is a different form and a real one.

**Claiming a number here is a real collision risk, and it is not in normal projects.** We write
ADRs at a rate a target project never will — our product *is* decisions — and several branches
are usually open at once. `reference/adr.md` states the rule (claim at write time; next above the
highest claimed anywhere, never the lowest free); these are the four places to look, kept here
because the file is read by projects that will never need the incantations:

```sh
# 1. the merged log — not `ls`, which shows your own working tree
git ls-tree --name-only origin/main docs/adr/
# 2. every remote branch. --no-renames, or an ADR moved in shows as a rename and hides from -A
git fetch --all && git log --all --diff-filter=AR --no-renames --name-only --pretty=format: -- 'docs/adr/*' | sort -u | grep .
# 3. every open PR
gh pr list --state open   # then: gh pr diff <n> --name-only | grep docs/adr/
```

The fourth place has no command: **an open issue that reserved a number for work not yet
written.** It has happened here — a number whose only claim lived in an issue, with nothing in
any tree, branch or PR to find. Record which number you took and what you checked it against in
the PR description, so check 1 can verify it like any other claim.
