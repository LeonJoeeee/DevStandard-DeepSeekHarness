# 0050 — Route model and effort by kind of work, without a tier cap

Status: Superseded by 0066 (2026-10-05). Originally Accepted (2026-09-09). Amends 0024 (the tier cap and mechanical-only downgrade rule) and 0040 (its restatement of the cap and uniform routing); amends 0008, 0036, 0039 and 0047 (their routing statements). Amended by 0056 (2026-09-11). Amended (2026-09-19). Amended (2026-09-20). Amended (2026-09-21). Amended (2026-09-23). Amended (2026-09-29).

## Context

The human ruled on issue #309 on **2026-09-09** that no model tier is off-limits. The previous
Claude cap prevented difficult judgments from reaching the strongest tier, and a single Codex
model/effort setting did not distinguish review, implementation, scanning, and mechanical work.
Nested helpers also needed an explicit routing rule instead of silently inheriting cheaper settings.

## Decision

Route by kind of work using two knobs, model tier and reasoning effort. The default table and
operative rules live in `reference/external-agent.md`, “Route it explicitly”: final dilemmas,
irreversible judgments and architecture acceptance take the top row; ordinary gating review,
implementation, scans and extraction each have their own row; deterministic work takes a script.
Claude tier aliases and explicit spawn settings remain required, with effort set wherever the
tool supports it. The human's own session model remains outside the method, and a project's root
`CLAUDE.md` or an issue naming a model overrides the table.

The executor asymmetry is deliberate. The human's cost rationale is that Claude's highest tier
costs twice the next tier per token and reviews are frequent, so ordinary Claude gating reviews
stay on the next tier; Codex's everyday top carries ordinary gating reviews too. This records the
human's rationale, not a price guarantee. Retaining the cap and using one strength for every kind
of work are rejected by that ruling; no other alternatives were recorded.

Stuck, ambiguous or unreliable work changes one thing per attempt: supply missing context, raise
effort, raise the model one tier, reduce task size, then ask the human. Never repeat unchanged;
irreversible questions and genuine dilemmas go straight to the top row. Recursion depth never
lowers the tier. Downgrade both knobs only for high-volume, low-difficulty work whose output is
mechanically checkable or can be spot-checked one tier up, after asking whether a script suffices.
A gating review never runs below its producer's tier; architecture review runs one tier above.

## Consequences

The dated standing-setting paragraph remains the single dispatch-default record, unchanged by
this decision. The table supplies routing defaults rather than an automatic task classifier;
the standing project setting and explicit project/issue overrides still apply. Codex-internal
helpers use the same routing table. Role TOML adds the gating row's subagent model and effort
defaults, with explicit spawn settings taking precedence; dispatch passes each root assignment
as its own CLI override while preserving the role hook. Claude worker/reviewer definitions add
explicit high effort and retain their default tier.

Routing now has more values to maintain. Model or tier changes require reconciling the canonical
table, role settings and their tests, plus dated ADR amendments where live instructions change.
The cap statements in 0024 and 0040 are superseded by dated blocks; their other decisions stand.

**Amendment (2026-09-11, see 0056; issue #346):** the dated standing record describes the
gating-review row. Dispatch purpose now selects the implementation or gating-review row; explicit
`--model` and `--effort` override their respective fields. `reference/external-agent.md` owns the
routing and caller-carried project/issue overrides; no additional record store is introduced.

**Amendment (2026-09-19, issue #406):** the human ruled that the two dispatched roles are
**anchored** rather than routed. The worker and the reviewer both run `gpt-6-astra` at `medium` on
Codex and `opus` at `high` on Claude, so the six-row kind-of-work table and the dated 2026-09-05
standing-setting sentence are both gone; `reference/orchestrator.md`'s **Model and effort** section
carries the anchors and is the one live record, replacing this ADR's pointer at
`reference/external-agent.md`, which no longer exists. The orchestrator's own model stays the
human's hand-made choice.

Arbitration — a genuine dilemma, an irreversible judgment, an architecture-level acceptance — takes
Claude `fable`, whose effort inherits the session so no third agent definition is needed, or Codex
`gpt-6-astra` at `xhigh`; the human declined a higher Codex setting on cost. A one-off subagent a
role spawns for its own task is not one of these roles: on Claude it is always `opus` at the
spawning role's effort, and on Codex it is `gpt-6-astra` at `medium` for judgment work — research,
checking a diff, challenging a design — and `gpt-5.6-luna` at `max` for scans, first-pass triage,
evidence gathering, fixed-field extraction, list making and format conversion. That last row is the
human's call from experience that Luna at `max` beats the cheaper rows it replaces, which is why
`gpt-5.6-terra` and `gpt-5.6-sol` are now named nowhere live. Bulk repetitive work — building a
retrieval index or a knowledge graph, batch extraction and tagging — is not agent work at all but a
script against a cheap model endpoint, named in the needing project's `CLAUDE.md` rather than on a
shipped page.

Three rules survive unchanged: a gating review never runs below the tier that produced the work,
stuck work changes one thing per attempt, and deterministic work takes a script. Added with them is
the mechanism behind the Claude column: effort is set only in an agent definition's frontmatter,
because the Agent tool takes a `model` per call and no effort, and an undefined effort inherits the
session's. `scripts/dispatch` therefore reads each Claude anchor's effort from `agents/<role>.md`
and refuses when the page's anchor and the definition disagree, so the page's statement is what runs
rather than a decoration. The Codex role TOML's subagent defaults follow the judgment row at
`medium`. The tier cap this ADR removed was never a harness limit, so nothing here restores one.

**Amendment (2026-09-20, issue #436):** The 2026-09-19 block's *"`scripts/dispatch` therefore reads
each Claude anchor's effort from `agents/<role>.md` and refuses when the page's anchor and the
definition disagree, so the page's statement is what runs rather than a decoration"* no longer
describes the dispatcher. That read is deleted. It never ran on the Codex column, and on
`--implementation claude-cli` the page's effort is what the command line passes, so on that path it
compared against a field which was not what ran. The mechanism the block states is unchanged — on
the native Claude Agent path effort still comes only from the definition's frontmatter, and the
prepared receipt still obliges the caller to report an unsupported effort rather than claim it — and
`reference/orchestrator.md`'s **Model and effort** section is still the one live record of the
anchors, with CI still enforcing one machine-readable row per role in the cell form. What replaces
the refusal for a row the dispatcher cannot find or parse is a warning naming the page plus the
caller's explicit `--model`/`--effort`; only a knob neither supplies still refuses. **Nothing now
checks the definition's `effort:` against the page:** `.github/check-agents.py` checks the model
alias, the absent tool allowlist, the writer denial, the skill and hook bindings and the generated
body, and has never read that field.

**Amendment (2026-09-21, issue #443):** `.github/check-agents.py` now asserts that
`agents/worker.md`'s `effort:` equals the Claude worker cell in `reference/orchestrator.md`'s
**Model and effort** table. This closes the worker-definition gap recorded in the #436 block
above without restoring the dispatcher's runtime comparison. Native Claude effort still comes
from frontmatter; the page remains the single live anchor record.

**Amendment (2026-09-23, issue #457):** after the new model releases the human ruled, in their
words, "仲裁开高档，平时干活 Opus 和 Sol，简单活 Luna" — arbitration at the high setting, everyday
work on Opus and Sol, simple work on Luna. The Codex column of the anchored table therefore reads
`gpt-6-sol` at `high` for both the worker and the reviewer, replacing the 2026-09-19 block's
`gpt-6-astra` at `medium`; the Claude column stays `opus` at `high`, and the `opus` alias, which
now resolves to Opus 5.5, is unchanged in `agents/worker.md` and `agents/reviewer.md`. Codex
arbitration is `gpt-6-astra` at `high`, lowered from `xhigh`; Claude arbitration stays `fable`
with the session's effort. A Codex one-off subagent's judgment work takes `gpt-6-sol` at `high`
instead of `gpt-6-astra` at `medium`, which moves the Codex role configuration's
`agents.default_subagent_*` defaults with it because they are read from that clause, and its
scans, triage, evidence gathering, extraction, list making and format conversion take
`gpt-6-luna` at `max` instead of `gpt-5.6-luna`, so no `gpt-5.6` model is named anywhere live.
Every other rule the 2026-09-19 block records stands, and `reference/orchestrator.md`'s **Model
and effort** section remains the one live record of these settings. The orchestrator's model
stays the human's hand-made choice and is not written on the page.

**Amendment (2026-09-29, issue #460):** with Claude Code the only main session (0063), the human
re-routed every model choice on tier equivalence: Claude `opus` and Codex `gpt-6-astra` are one
tier, Opus better and cheaper, so main work prefers Opus; Claude `sonnet` and Codex `gpt-6-sol` are
one tier at about the same price; `gpt-6-luna` is the tier below; Claude `fable` and `haiku` are no
longer used. Both harnesses hit quota at times, so the routing keeps both in use. The worker and
reviewer stay anchored on Claude `opus` at `high`; their Codex cell becomes `gpt-6-astra` at `high`,
replacing the 2026-09-23 block's `gpt-6-sol` at `high`, as the equal-tier executor a human selects and
the disclosed re-dispatch when Claude cannot run. Arbitration is Codex `gpt-6-astra` at `max`, run
read-only from the Claude main session; it informs a genuine dilemma or irreversible judgment, which
stays the human's. With a PR it goes through the existing Codex reviewer path (`review-packet start
--implementation codex --model gpt-6-astra --effort max`); before a PR exists it is a fresh,
ephemeral, read-only `codex exec` with the question and evidence on stdin, its captured answer
posted on the issue, and no script is added. The pinned Codex CLI accepts that setting, CI asserts
that the two routes name the same one and that the direct one stays read-only, and Claude `fable`
is named nowhere live. A one-off subagent — a helper — always uses its
own harness's built-in subagent, never the other harness, and takes its model from its work: one
whose conclusion directly decides a merge or a design takes `opus` or `gpt-6-astra` at `high`,
ordinary judgment `sonnet` or `gpt-6-sol` at `high`, mechanical work `sonnet` or `gpt-6-luna` at
`max`; a Claude helper's effort still inherits its caller's. That replaces the 2026-09-19 block's
"always `opus`" on Claude and the 2026-09-23 block's two Codex rows. Because only the orchestrator
reads `reference/orchestrator.md`, each role is now told the rule where it already reads: the Claude
column rides `reference/harness-claude.md` (so `agents/worker.md`'s generated body) and
`agents/reviewer.md`, which `.github/check-agents.py` checks against the table; the Codex column is
read from the table by `scripts/dispatch` into every Codex packet, since CI forbids restating a Codex
model on another live page. The Codex role configuration's `agents.default_subagent_*` defaults
follow the table's ordinary-judgment row, which keeps them at `gpt-6-sol` at `high`.
`reference/orchestrator.md`'s **Model and effort** section remains the one live record, and every
other rule the earlier blocks record stands.
