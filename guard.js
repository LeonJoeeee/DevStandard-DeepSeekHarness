/**
 * The DevStandard dsh guard: the role word engine, carried onto the harness's own
 * tool-interception point.
 *
 * This is the port of `scripts/hard_edges.py`'s role hook — the same three words ADR 0062
 * cleared and the same worker default-branch `push` rule, the same quoted-string and
 * here-document removal, the same whole-word boundary, and the same reminder wording —
 * from the Claude Code `PreToolUse` carrier onto dsh's `tools/pre-execute` waterfall. It is
 * a faithful port, not a new policy: `.github/check-dsh-guard.py` runs this engine and the
 * Python one over one corpus and fails if a single decision differs, so the two cannot drift.
 * Nothing here reads a file, a ref or the network, and there is nothing to configure.
 *
 * Two things differ from the Claude carrier, and only two (ADR 0062's 2026-10-05 amendment):
 * dsh's shell tool is named `bash`, not `Bash`/`exec_command`, and the command text comes
 * from `exec.arguments.command`, the same field. The role is chosen by the listener, not
 * here: `decide()` takes the role the caller resolved (see `index.js`).
 *
 * @module devstandard-dsh/guard
 */

/**
 * One refusal per role, and nothing else (#425). A word stays only where the act it names
 * is irreversible *and* no other layer stops it. The worker's `merge` is an unreviewed
 * squash to the default branch that `guard protection` does not stop; the orchestrator's
 * `gh pr merge` skips `guard merge`'s reviewed-head and rebase proof; the reviewer's
 * `gh api` write flags are the one reviewer rule with a real target. Everything else is
 * admitted: a local merge, a tag, a release build, a force-push, branch and worktree
 * deletion and a recursive `rm` included.
 */
const REFUSED_WORDS = {
  worker: ['merge'],
  reviewer: [],
  orchestrator: ['gh pr merge'],
}

/** The `gh api` flags a reviewer must not write through; the reviewer is read-only. */
const REVIEWER_GH_WRITE = ['-X', '--method', '-f', '-F', '--input']

/**
 * The two names a default branch has, written here rather than read from anywhere: a target
 * that calls its branch something else is outside this rule, and GitHub's branch protection
 * stops the push that this admits (#326).
 */
const DEFAULT_BRANCHES = ['main', 'master']

/**
 * Every refusal is a reminder, not a wall: what was refused, what the role does instead, and
 * the one page to read (#323). The harness feeds this text back to the model as the tool
 * result, so it is written to be acted on. #323's fourth part, telling the caller how to
 * re-spell a command that merely writes the word, went with the words that made it necessary.
 */
const INSTEAD = {
  worker: 'a worker pushes its own task branch and hands the PR back to the orchestrator, '
    + 'which owns acceptance, merge and teardown',
  reviewer: 'a reviewer returns a verdict and writes nothing',
  orchestrator: 'the orchestrator merges only through `<plugin>/scripts/guard merge`, which '
    + 'verifies the reviewed head, proves the rebase and reads GitHub itself',
}

const ROLE_PAGE = {
  worker: "`reference/worker.md`'s Never section",
  reviewer: "`reference/code-review-prompt.md`'s Output format section",
  orchestrator: "`reference/orchestrator.md`'s Acceptance and integration section",
}

// A here-document body ends at its terminator line, or at the end of the text when there is
// none; `<<<` is a here-string and `1 << 2` a shift, so a delimiter starts like a name. The
// Python `\Z` becomes `(?![\s\S])` (end of input); `re.S | re.M` becomes the `s` and `m`
// flags.
const HEREDOC = /(?<!<)<<-?[\t ]*(?<quote>['"]?)(?<delimiter>[A-Za-z_][A-Za-z0-9_.-]*)\k<quote>(?<rest>[^\n]*)\n.*?(?:^[\t ]*\k<delimiter>[\t ]*$|(?![\s\S]))/gms
// A quoted string runs to the next quote of the same kind, whichever kind opens first, and
// over newlines as the shell does; what never pairs is left exactly as written.
const QUOTED = /'[^']*'|"[^"]*"/g

const REGEX_SPECIALS = /[.*+?^${}()|[\]\\]/g

/** Escape a literal for interpolation into a `RegExp`, as Python's `re.escape` does. */
function escapeRegExp(word) {
  return word.replace(REGEX_SPECIALS, '\\$&')
}

/**
 * The command with the data it carries removed: here-doc bodies and quoted contents.
 *
 * A here-document body, a commit message, an issue body, a search pattern: text the command
 * writes or matches rather than runs. Reading it refused ordinary writes for every role and
 * cost whole lanes (#351), so the scan judges the text without it. A substitution body —
 * `$( … )` or a backtick outside quotes — is command text and is still read. This is a regex
 * pass and not a shell grammar: an unbalanced quote or an unterminated here-document removes
 * what it can and is never itself a reason to refuse. Removal is one-directional, because
 * the quote characters and the line structure stay, so the scan can only admit more than it
 * did, never refuse more.
 */
export function commandOnly(text) {
  // A body begins on the line after the operator, so a command holding no newline holds no
  // here-document. Saying so spares the scan a quadratic walk over one line of `<<` tokens.
  let out = text
  if (out.includes('\n')) out = out.replace(HEREDOC, (...args) => '<<' + args.at(-1).rest)
  return out.replace(QUOTED, (match) => match[0].repeat(2))
}

/**
 * True where a phrase's words stand next to each other as whole words.
 *
 * A word matches where it begins at a non-identifier position and ends at one that continues
 * neither an identifier nor a hyphenated word — the one boundary rule that keeps `merge`
 * from reading `merged`, `--merged` or `mergeable`, `main` from reading `task/mainline`, and
 * `git merge-base` from reading `git merge`. A phrase of several words matches only where
 * those words stand together.
 */
export function carries(text, phrase) {
  const body = phrase.split(/\s+/).filter(Boolean).map(escapeRegExp).join('\\s+')
  return new RegExp('(?<!\\w)' + body + '(?![\\w-])').test(text)
}

/**
 * True where the text carries this option, with or without its value written onto it.
 *
 * `-XPOST` is one word to the shell and one flag to `gh`, so the reviewer's write-flag rule
 * keeps the older boundary — begins at a non-identifier position, not continued by a hyphen.
 */
export function carriesFlag(text, flag) {
  return new RegExp('(?<!\\w)' + escapeRegExp(flag) + '(?!-)').test(text)
}

/** The one refusal template, filled with the word the caller actually wrote. */
export function refusal(role, word, subject = 'a command', qualifier = '') {
  return `${role} role refuses ${subject} carrying '${word}'${qualifier}. `
    + `Instead, ${INSTEAD[role]}. Read ${ROLE_PAGE[role]}.`
}

/**
 * The whole shell decision for one role: which of its words the command's own text carries.
 *
 * The union role is reserved for a child the listener could not map to a row (`index.js`);
 * it fires a worker rule or a reviewer rule, in that order, and is the fallback ADR 0062's
 * amendment named. Every mapped child takes its own role's exact list.
 */
export function commandRefusal(role, raw) {
  if (role === 'child') {
    return commandRefusal('worker', raw) ?? commandRefusal('reviewer', raw)
  }
  const text = commandOnly(raw)
  for (const word of REFUSED_WORDS[role]) {
    if (carries(text, word)) return refusal(role, word)
  }
  if (role === 'reviewer' && carries(text, 'gh')) {
    for (const flag of REVIEWER_GH_WRITE) {
      if (carriesFlag(text, flag)) return refusal(role, flag, 'a `gh` command')
    }
  }
  // The orchestrator's default-branch push is not refused: founding pushes its first commits
  // to the default branch, and once founding has set protection GitHub refuses the push
  // server-side. This one survives for that same window, on the lane side, and nothing else.
  if (role === 'worker' && carries(text, 'push')) {
    const named = DEFAULT_BRANCHES.find((name) => carries(text, name))
    if (named !== undefined) {
      return refusal(role, 'push', 'a command',
        ` that also names the default branch '${named}'`)
    }
  }
  return undefined
}

/**
 * The guard's whole decision for one pending call: `undefined` to admit, or the reminder
 * text to deny with.
 *
 * The role is the caller's — `orchestrator` at the root, `worker`/`reviewer`/`child` for a
 * spawned child. A tool other than the shell tool `bash` is admitted for every role: file
 * content goes through the host's editing tools, which the guard never reads (#334, #351).
 *
 * @param role - the resolved role: `orchestrator`, `worker`, `reviewer`, or the union `child`.
 * @param tool - the model-facing tool name (`exec.name`).
 * @param args - the parsed model arguments (`exec.arguments`).
 * @returns the refusal reminder, or `undefined` to admit the call.
 */
export function decide(role, tool, args) {
  if (tool !== 'bash') return undefined
  const command = args === null || typeof args !== 'object' ? '' : args.command
  if (typeof command !== 'string') return undefined
  return commandRefusal(role, command)
}
