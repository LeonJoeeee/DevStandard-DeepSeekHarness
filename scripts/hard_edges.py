#!/usr/bin/env python3
"""Mechanical guard primitives. Python 3.9+, git 2.38+, authenticated gh."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote
from review_packet import (FLOOR_LABELS, MANIFESTS, decision_line, floor_results, manifest_bump,
                           normalize, recovery_ruling, verdict_shape, version_only)


class Refusal(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Refusal(message)


def refusing(read, *args):
    """review_packet's pinned readers raise ValueError; at a guard boundary that is a Refusal."""
    try:
        return read(*args)
    except ValueError as error:
        raise Refusal(str(error)) from error


def ascending(pair):
    """True when a dotted numeric release sorts strictly above the one it replaces."""
    fields = [version.split('.') for version in pair]
    require(all(re.fullmatch('[0-9]+', field) for parts in fields for field in parts),
            'exempt version lines require dotted numeric releases: ' + repr(pair))
    return [int(field) for field in fields[0]] < [int(field) for field in fields[1]]


def run(*args, cwd=None, env=None, input=None):
    result = subprocess.run(args, cwd=cwd, env=env, input=input, text=True, capture_output=True)
    require(result.returncode == 0, result.stderr.strip() or result.stdout.strip() or f'{args[0]} failed')
    return result.stdout.rstrip('\n')


def api(endpoint, *args):
    raw = run('gh', 'api', endpoint, *args)
    if '--paginate' not in args:
        return json.loads(raw)
    decoder, pages = json.JSONDecoder(), []
    while raw.strip():
        page, end = decoder.raw_decode(raw.lstrip())
        pages.extend(page if isinstance(page, list) else [page])
        raw = raw.lstrip()[end:]
    return pages


PLAN_LIMIT = 'Upgrade to GitHub Pro or make this repository public'
PROTECTION_UNAVAILABLE = "unavailable on this repository's plan"


def protection_unavailable(error):
    """True only for GitHub's statement that this repository cannot have protection."""
    return PLAN_LIMIT in str(error)


def protection_read_refusal(subject, error):
    """Actionable refusal for a protection read or update that cannot proceed."""
    detail = str(error).strip() or 'GitHub returned no diagnostic'
    if protection_unavailable(error):
        why = f'branch protection is {PROTECTION_UNAVAILABLE}'
    else:
        why = ('GitHub did not return readable protection state; this response does not establish '
               'that protection is unavailable, so the server-side gate cannot be skipped')
    return (f'{subject} refused because {why}. GitHub returned: {detail}. '
            'To make the server-side gate available, make the repository public or use a paid '
            'GitHub plan. For any other response, restore permission to read protection. '
            "Read `reference/orchestrator.md`'s Branch protection section.")


# The name the shipped CI template reports for a PR's merge result, pinned to both SHAs.
MERGED_RESULT = 'merged-result / {base} / {head}'


def merged_result(base, head):
    """The integration check's name, pinned to this exact base and head."""
    return MERGED_RESULT.replace('{base}', base).replace('{head}', head)


def project_repo(project):
    """OWNER/REPO from this checkout's own origin remote; local, so no network."""
    url = run('git', '-C', str(project), 'remote', 'get-url', 'origin')
    match = re.search(r'[:/]([^/:]+/[^/]+?)(?:\.git)?/?$', url)
    require(match, f'cannot read OWNER/REPO from the origin remote: {url!r}')
    return match[1]


def protection_check(repo, branch, checks=()):
    """Protection's shape, plus any contexts the caller named on the command line (#326)."""
    checks = list(checks)
    unavailable = {'repo': repo, 'branch': branch, 'checks': checks,
                   'protection': PROTECTION_UNAVAILABLE,
                   'merge_queue': 'unavailable with branch protection on this repository\'s plan'}
    try:
        state = api(f'repos/{repo}/branches/{quote(branch, safe="")}/protection')
    except Refusal as error:
        if protection_unavailable(error):
            return unavailable
        raise Refusal(protection_read_refusal('classic branch protection read', error)) from error
    status = state.get('required_status_checks') or {}
    require(status.get('strict') is True, 'protection requires strict up-to-date checks')
    require(set(checks) <= set(status.get('contexts', [])), 'protection missing required checks')
    require((state.get('enforce_admins') or {}).get('enabled') is True, 'protection must enforce admins')
    for field in ('allow_force_pushes', 'allow_deletions'):
        require((state.get(field) or {}).get('enabled') is False, f'protection must disable {field}')
    # Classic protection carries no queue field; rulesets are where the API exposes one.
    try:
        rules = api(f'repos/{repo}/rules/branches/{quote(branch, safe="")}', '--paginate')
    except Refusal as error:
        # A merge queue is itself a ruleset feature. GitHub's plan-limit response establishes
        # that neither rulesets nor classic protection can exist, rather than leaving a queue
        # unreadable and therefore possible.
        if protection_unavailable(error):
            return unavailable
        raise Refusal(protection_read_refusal('branch rules read', error)) from error
    require(isinstance(rules, list) and all(isinstance(rule, dict) for rule in rules),
            'branch rules unreadable, so a merge queue cannot be ruled out')
    require(not any(rule.get('type') == 'merge_queue' for rule in rules),
            'protection must not enable a merge queue: it merges a server-built commit '
            'that no reviewer saw and no guarded merge produced')
    return {'repo': repo, 'branch': branch, 'checks': checks, 'protection': 'pass',
            'merge_queue': 'off'}


def compare_rebase(project, old_base, old_head, new_base, new_head):
    """Replay in a disposable clone; never move the caller's refs/index/worktree.

    The project path is used verbatim: `git -C` and `git clone --shared` each resolve the
    caller's spelling themselves, and the clone's alternates record an absolute path either way.
    Resolving it here bought nothing and raised `RuntimeError` on a symlink loop through 3.12,
    past a handler that catches it nowhere; git's own refusal names the path instead (#453).
    """
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    clean_env.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
                     GIT_TERMINAL_PROMPT='0', GIT_EDITOR='true', GIT_AUTHOR_NAME='Rebase proof',
                     GIT_AUTHOR_EMAIL='proof@example.invalid', GIT_COMMITTER_NAME='Rebase proof',
                     GIT_COMMITTER_EMAIL='proof@example.invalid')

    def git(at, *args):
        return run('git', '-C', str(at), '-c', 'core.hooksPath=/dev/null', *args, env=clean_env)

    pins = [old_base, old_head, new_base, new_head]
    require(all(re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', pin) for pin in pins), 'comparison requires full immutable SHAs')
    for pin in pins:
        require(git(project, 'rev-parse', '--verify', pin + '^{commit}') == pin, 'pin is not a commit')
    git(project, 'merge-base', '--is-ancestor', old_base, old_head)
    git(project, 'merge-base', '--is-ancestor', old_base, new_base)
    git(project, 'merge-base', '--is-ancestor', new_base, new_head)
    require(not git(project, 'rev-list', '--merges', f'{old_base}..{old_head}'), 'merge commits require full review')
    require(not git(project, 'rev-list', '--merges', f'{new_base}..{new_head}'), 'merge commits require full review')

    def changed(base, head):
        # -z retains whitespace/newlines in names; no rename inference hides a deleted path.
        raw = git(project, 'diff', '--no-ext-diff', '--no-textconv', '--no-renames', '--name-only', '-z', base, head)
        return set(raw.rstrip('\0').split('\0')) if raw else set()

    def exempt_conflict(clone):
        """Conflicted paths when the replay stopped only on the exempt manifest version lines."""
        raw = git(clone, 'ls-files', '--unmerged', '-z')
        stopped = {row.split('\t', 1)[-1] for row in raw.rstrip('\0').split('\0')} if raw else set()
        if not stopped or not stopped <= set(MANIFESTS):
            return set()
        try:  # git's :1/:2/:3 are the conflict's base, the new base's side and the reviewed lane's.
            sides = [manifest_bump(clone, ':1', side, path, clean_env)
                     for path in sorted(stopped) for side in (':2', ':3')]
        except ValueError:
            return set()
        return stopped if all(sides) else set()

    paths = changed(old_base, old_head) | changed(new_base, new_head)
    require(paths, 'empty PR requires full review')
    bumps = {}
    for path in sorted(paths):
        # Entry identity includes mode, object type and blob bytes, including deletion and symlinks.
        old = git(project, 'ls-tree', '-z', old_head, '--', ':(literal)' + path)
        new = git(project, 'ls-tree', '-z', new_head, '--', ':(literal)' + path)
        # The bump rides the change PR, so rebasing past a merged bump moves only these version lines.
        if old != new and path in MANIFESTS and old.split()[:2] == new.split()[:2]:
            bumps[path] = refusing(manifest_bump, project, old_head, new_head, path, clean_env)
        require(old == new or bumps.get(path), f'PR-changed path is not byte/mode-identical: {path!r}')
        require(not old.startswith('160000 '), 'submodules require full review')
    require(not bumps or (set(bumps) == set(MANIFESTS)
                          and all(bump == bumps[MANIFESTS[0]] for bump in bumps.values())),
            'exempt manifest version lines must move in lockstep: ' + repr(bumps))
    with tempfile.TemporaryDirectory(prefix='devstandard-rebase-proof-') as scratch:
        clone = Path(scratch) / 'replay'
        run('git', 'clone', '--shared', '--no-checkout', '--quiet', str(project), str(clone), env=clean_env)
        git(clone, 'checkout', '--detach', old_head)
        step = ['rebase', '--no-autostash', '--no-gpg-sign', '--reapply-cherry-picks',
                '--empty=keep', '--onto', new_base, old_base]
        while True:
            try:
                git(clone, '-c', 'rerere.enabled=false', *step)
                break
            except Refusal as error:
                # The comparison exempts these version lines, so the replay feeding it does too. Taking
                # the new base's side leaves the ordering checks below a version they must beat.
                stopped = exempt_conflict(clone)
                if not stopped:
                    raise Refusal(f'conflict-free rebase proof refused: {error}') from error
                for path in sorted(stopped):
                    git(clone, 'checkout', '--ours', '--', ':(literal)' + path)
                    git(clone, 'add', '--', ':(literal)' + path)
                step = ['rebase', '--continue']
        replay = git(clone, 'rev-parse', 'HEAD')
        if git(clone, 'rev-parse', replay + '^{tree}') != git(project, 'rev-parse', new_head + '^{tree}'):
            require(refusing(version_only, clone, replay, new_head, clean_env),
                    'new head differs from conflict-free replay tree')
            # The exemption admits a bump the head declares, never a silent revert of the base's.
            replayed = refusing(manifest_bump, clone, replay, new_head, MANIFESTS[0], clean_env)
            require(bumps and replayed and bumps[MANIFESTS[0]][1] == replayed[1],
                    'exempt version lines must carry the reviewed head bump: ' + repr(bumps))
            require(ascending(bumps[MANIFESTS[0]]) and ascending(replayed),
                    'exempt version lines must sort above the versions they replace: '
                    + repr([bumps[MANIFESTS[0]], replayed]))
    return {'old_base': old_base, 'accepted_head': old_head, 'base': new_base, 'head': new_head,
            'paths': sorted(paths), 'version_bump': bumps.get(MANIFESTS[0]), 'comparison': 'pass'}


def commit_checks(repo, sha, required=()):
    """No observed check may have failed; `required` additionally names checks that must be green.

    Silence is never green, a failed check always refuses, and an unfinished or skipped check
    that nothing requires does not (#426). Each refusal names the observed checks and the
    required set actually applied, and only a check that failed is reported as failing (#314).
    """
    pages = api(f'repos/{repo}/commits/{sha}/check-runs?per_page=100', '--paginate')
    if isinstance(pages, dict):  # Also accepts a single page from API boundary doubles.
        pages = [pages]
    runs = [row for page in pages for row in page.get('check_runs', [])]
    pages = api(f'repos/{repo}/commits/{sha}/status?per_page=100', '--paginate')
    if isinstance(pages, dict):
        pages = [pages]
    statuses = [row for page in pages for row in page.get('statuses', [])]
    # The API returns newest first; an older successful run must not hide a current red run.
    latest = {}
    for row in sorted(runs, key=lambda row: row.get('id', 0), reverse=True):
        latest.setdefault(row['name'], row.get('conclusion') if row.get('status') == 'completed' else 'pending')
    for row in sorted(statuses, key=lambda row: row.get('id', 0), reverse=True):
        latest.setdefault(row['context'], row.get('state'))
    # An empty required set never admits an unchecked head: silence is not green.
    require(latest, f'no CI checks reported for {sha}: required={list(required)!r}')
    # Anything outside this set is read as a failure, so an unrecognized conclusion refuses.
    failed = {name: value for name, value in latest.items()
              if value not in ('success', 'neutral', 'skipped', 'pending')}
    require(not failed, f'CI failing for {sha}: failed={failed!r}, '
                        f'required={list(required)!r}, observed={latest!r}')
    # Absent or reported anything but success: other observed checks cannot stand in for these.
    unmet = [name for name in required if latest.get(name) != 'success']
    require(not unmet, f'required CI checks unmet for {sha}: unmet={unmet!r}, '
                       f'required={list(required)!r}, observed={latest!r}')
    return latest


def acceptance(comments, head, allow_goal_no=False):
    """Read the canonical whole verdict, never a readiness substring in arbitrary prose."""
    verdicts = [row for row in comments if re.match(r'^## Merge check 1 — round [1-9][0-9]*\s*\n', row['body'])]
    require(verdicts, 'no whole Merge check 1 verdict')
    row = verdicts[-1]
    # Remove only the public heading and optional record envelope; validate the same whole return
    # as publication, never a readiness substring in the record or arbitrary surrounding prose.
    body = row['body'].split('\n', 1)[1].lstrip('\n')
    envelope = re.match(r'<!-- devstandard-review-v1 -->\n```json\n.*?\n```\n', body, re.S)
    if envelope:
        body = body[envelope.end():].lstrip('\n')
    defect = verdict_shape(body, head)
    require(defect is None, defect)
    body = normalize(body)
    goal = re.search(decision_line('Goal verdict', grounds=True), body, re.M)
    require(goal and (allow_goal_no or goal[1] == 'Yes'),
            'Goal Yes verdict required (or recorded orchestrator ruling)')
    for label in FLOOR_LABELS:
        require(floor_results(body, label) == ['Pass'],
                'both Floor checks must Pass')
    return row


REVIEW_AUTHOR_ASSOCIATIONS = frozenset({'OWNER', 'MEMBER', 'COLLABORATOR'})


def operative_review_comments(comments):
    """Comments published by accounts GitHub associates with this repository."""
    return [row for row in comments
            if row.get('author_association') in REVIEW_AUTHOR_ASSOCIATIONS]


def review_history(comments):
    """Consume #203's public record format; the review-packet command owns publication."""
    attempts, rulings, active = [], [], []
    for row in comments:
        body = row['body']
        match = re.match(r'^## (?:Review attempt|Merge check 1|Review ruling) — [^\n]+\n\n'
                         r'<!-- devstandard-review-v1 -->\n```json\n(.*?)\n```\n', body, re.S)
        if match:
            record = json.loads(match[1])
            record['row'] = row
            if record['kind'] == 'ruling':
                rulings.append(record)
            elif record.get('status') == 'returned':
                record['row'] = dict(row, body=f"## Merge check 1 — round {record['round']}\n" + body[match.end():].lstrip('\n'))
                attempts.append(record)
            elif record.get('status') in ('reserved', 'dispatched'):
                active.append(record)
        elif body.startswith('## Merge check 1'):
            match = re.match(r'^## Merge check 1 — round ([1-9][0-9]*)\n', body)
            require(match, 'ambiguous legacy review round; reconcile history')
            head = re.search(r'^Reviewer: [^\n]+ — reviewed\s+([0-9a-f]{40,64})', body, re.M)
            attempts.append({'round': int(match[1]), 'head': head[1] if head else None, 'row': row})
    attempts.sort(key=lambda row: row['round'])
    require([row['round'] for row in attempts] == list(range(1, len(attempts)+1)),
            'missing or duplicate review rounds; reconcile history')
    last = attempts[-1] if attempts else None
    rulings = [r for r in rulings if last and r['round'] == last['round'] and r['head'] == last['head']]
    # An unreturned reservation is reported, not refused on: each caller decides what it means.
    return attempts, last, rulings[-1] if rulings else None, active


def base_advanced(repo, base_ref, head):
    """True when main moved under the PR: its head does not carry the default branch's head.

    This is the fact `merge_check` refuses an un-rebased merge on with `merge-base --is-ancestor
    base head`, and the one `review-packet rule` counts for behind-base recovery, so the rebase
    admission below cannot disagree with either. `pull.base.sha` is NOT that fact: GitHub reports
    the base ref's current head there, so it equals the default branch's head whether or not the
    PR was ever rebased onto it (measured on PR #423). A PR aimed anywhere but the default branch
    has no such route -- `merge_check` refuses it outright -- so it never admits one.
    """
    default = api(f'repos/{repo}')['default_branch']
    if base_ref != default:
        return False
    base = api(f'repos/{repo}/branches/{quote(default, safe="")}')['commit']['sha']
    return api(f'repos/{repo}/compare/{base}...{head}')['behind_by'] > 0


def round_check(comments, head, rebase=False):
    attempts, last, ruling, active = review_history(comments)
    # A reservation that never returned is a warning, never a refusal (#435). One transient
    # GitHub failure used to strand the lane behind a fifth command (#377), and what authorizes
    # the next step is the accepted verdict on the exact head — which a reservation is not.
    # The round count decides nothing either (#434): no record exists of the cap ever firing, and
    # the stop signal #173 measured is findings of the same shape round after round, which the
    # reviewer reports. `review-packet` counts the rounds and warns.
    warnings = [f"review attempt {row['round']} is still {row['status']}" for row in active]
    reuse = False
    if last:
        # Read the decision the verdict parsers read; raw text let emphasis hide a Fail (#260).
        require('Fail' not in floor_results(last['row']['body'], '2. Authorization and scope'),
                'Floor check 2 failed; stop lane and escalate to human')
        try:
            acceptance([last['row']], head)
        except Refusal:
            pass
        else:
            # An accepted head whose base has advanced is continued for the rebase alone: no
            # ruling, and no review round. `guard merge --old-base/--old-head` re-establishes
            # that same acceptance from the replay, so a round would only re-derive by hand
            # what the proof settles mechanically (#421). A recorded ruling is a deliberate
            # act and still governs, so the base advance never reinterprets one.
            reuse = rebase and not ruling
            if not reuse:
                require(recovery_ruling(ruling, head), 'accepted verdict: Notes do not authorize another round')
        if not reuse:
            require(ruling and ruling['decision'] == 'continue', 'explicit orchestrator continuation ruling required')
    return {'rounds': len(attempts), 'next_round': len(attempts)+1, 'head': head,
            'rebase': reuse, 'warnings': warnings}


def merge_acceptance(comments, head):
    _, last, ruling, active = review_history(comments)
    require(not active, 'review attempt active; wait for whole verdict')
    require(last, 'no whole Merge check 1 verdict')
    if ruling:
        require(ruling['decision'] == 'merge-as-is', 'latest orchestrator ruling does not authorize merge')
    result = acceptance([last['row']], head, allow_goal_no=bool(ruling))
    return dict(result, record=last)


def merge_check(project, repo, number, old_base=None, old_head=None, execute=False):
    """Require review and integration evidence, then optionally merge the verified head."""
    require(project_repo(project) == repo,
            'merge repository differs from this checkout\'s origin')
    pr = api(f'repos/{repo}/pulls/{number}')
    repository = api(f'repos/{repo}')
    default = repository['default_branch']
    base = api(f'repos/{repo}/branches/{quote(default, safe="")}')['commit']['sha']
    head = pr['head']['sha']
    require(pr['state'] == 'open', 'merge requires an open PR')
    require(pr['base']['repo']['full_name'] == repo and pr['base']['ref'] == default,
            'merge requires the default branch of this repository')
    require(pr['base']['sha'] == base, 'PR base is not current default-branch head')
    run('git', '-C', str(project), 'merge-base', '--is-ancestor', base, head)
    # No branch-protection read here (#435). GitHub enforces strict up-to-date checks, admin
    # enforcement, force-push and deletion bans and the queue server-side at the merge itself,
    # so re-reading them could only turn an API hiccup into a refused merge. `guard protection`
    # is the audit that keeps every one of those conditions.
    comments = api(f'repos/{repo}/issues/{number}/comments?per_page=100', '--paginate')
    review_comments = operative_review_comments(comments)
    bare_bump = refusing(version_only, project, base, head)
    verdict = None if bare_bump else merge_acceptance(review_comments, old_head or head)
    proof = None
    if old_head and not bare_bump:
        require(old_base, 'prior acceptance requires its review base')
        require(verdict['record'].get('base') == old_base,
                'prior acceptance must record the exact old review base (#203 record)')
        proof = compare_rebase(project, old_base, old_head, base, head)
    ci = commit_checks(repo, head, [merged_result(base, head)])
    # Only the two SHAs everything above is pinned to. Comparing the whole PR record refused on
    # an edited title or a new comment count, twice on 2026-09-20 (PRs #418, #419) — #435.
    latest = api(f'repos/{repo}/pulls/{number}')['head']['sha']
    latest_base = api(f'repos/{repo}/branches/{quote(default, safe="")}')['commit']['sha']
    require(latest == head and latest_base == base,
            f'PR head or base moved during verification: head {head} -> {latest}, '
            f'base {base} -> {latest_base}')
    result = {'repo': repo, 'pr': number, 'base': base, 'head': head,
              'verdict': verdict['id'] if verdict else None, 'comparison': proof, 'checks': ci, 'merge': 'pass'}
    if execute:
        message = run('git', '-C', str(project), 'log', '-1', '--format=%B', head)
        trailers = re.findall(r'^(?:Claude-Session|Codex-Session|Co-authored-by):[^\r\n]+',
                              message, re.I | re.M)
        # GitHub rechecks strict protection; the SHA precondition rejects a moved PR head.
        result['result'] = api(f'repos/{repo}/pulls/{number}/merge', '--method', 'PUT',
                              '-f', 'sha=' + head, '-f', 'merge_method=squash',
                              '-f', f'commit_title={pr["title"]} (#{number})',
                              '-f', 'commit_message=' + '\n'.join(trailers))
        require(result['result'].get('merged'), 'GitHub refused the verified merge')
    return result


# ---------------------------------------------------------------------------
# The role hook's one rule (#323, ADR 0051).
#
# The hook reads the command's own text — here-document bodies and quoted-string
# contents removed, substitution bodies still read — and refuses when that text
# carries one of its role's words as a whole word. There is no parsing and no
# grammar, so unparseable syntax is never a reason to refuse for any role. Nothing
# here reads a file, a ref or the network, and there is nothing to configure: the
# words below are the whole policy (#326, ADR 0052).
# It judges commands and nothing else: a tool name is never a reason to refuse, so
# every non-shell tool call is admitted for every role (#334). File content therefore
# goes through the host's editing tool — `Write`/`Edit`, `apply_patch` — which the
# hook never reads (#351).
# Obfuscation, interpreter scripts, forged local refs and runtime data are outside
# this boundary by design; `guard merge`, branch protection and the sandboxes are the
# layers that remain (`reference/orchestrator.md`).
# ---------------------------------------------------------------------------

# A here-document body ends at its terminator line, or at the end of the text when there is
# none; `<<<` is a here-string and `1 << 2` a shift, so a delimiter starts like a name.
HEREDOC = re.compile(r'(?<!<)<<-?[\t ]*(?P<quote>[\'"]?)'
                     r'(?P<delimiter>[A-Za-z_][A-Za-z0-9_.-]*)(?P=quote)'
                     r'(?P<rest>[^\n]*)\n'
                     r'.*?(?:^[\t ]*(?P=delimiter)[\t ]*$|\Z)', re.S | re.M)
# A quoted string runs to the next quote of the same kind, whichever kind opens first, and
# over newlines as the shell does; what never pairs is left exactly as written.
QUOTED = re.compile(r'\'[^\']*\'|"[^"]*"')


def command_only(text):
    """The command with the data it carries removed: here-doc bodies and quoted contents.

    A here-document body, a commit message, an issue body, a search pattern: text the
    command writes or matches rather than runs. Reading it refused ordinary writes for
    every role and cost whole lanes (#351), so the scan judges the text without it.
    A substitution body — `$( … )` or a backtick outside quotes — is command text and is
    still read. This is a regex pass and not a shell grammar: an unbalanced quote or an
    unterminated here-document removes what it can and is never itself a reason to refuse.
    Removal is one-directional, because the quote characters and the line structure stay:
    nothing removed can join two fragments into a word nobody wrote, so the scan can only
    admit more than it did, never refuse more.
    """
    # A body begins on the line after the operator, so a command holding no newline holds no
    # here-document and the pattern cannot match it. Saying so costs one test and spares the
    # scan a quadratic walk over a single line of thousands of `<<` tokens.
    if '\n' in text:
        text = HEREDOC.sub(lambda match: '<<' + match['rest'], text)
    return QUOTED.sub(lambda match: match[0][0] * 2, text)


def carries(text, phrase):
    """True where the phrase's words stand next to each other as whole words.

    A word matches where it begins at a non-identifier position and ends at one that
    continues neither an identifier nor a hyphenated word. That one boundary rule is why
    `merge` never reads `merged`, `--merged` or `mergeable`, why `main` never reads
    `task/mainline`, and why `git merge-base` is not `git merge`. A phrase of several
    words matches only where those words stand together, so an option wedged between them
    escapes — inside the accepted residual.
    """
    return re.search(r'(?<!\w)' + r'\s+'.join(re.escape(word) for word in phrase.split())
                     + r'(?![\w-])', text) is not None


def carries_flag(text, flag):
    """True where the text carries this option, with or without its value written onto it.

    `-XPOST` is one word to the shell and one flag to `gh`, so the reviewer's write-flag
    rule keeps the older boundary — begins at a non-identifier position, not continued by
    a hyphen — rather than the whole-word rule above.
    """
    return re.search(r'(?<!\w)' + re.escape(flag) + r'(?!-)', text) is not None


# Three rules and nothing else (#425). A word stays only where the act it names is
# irreversible *and* no other layer stops it. Everything the lists used to carry failed
# that bar in one direction or the other, and each one bought its refusals with false ones:
# `tag` refused a local reversible `git tag` while admitting `git push --tags`; `release`
# refused `cargo build --release` in every target project; `--force` stranded a worker on
# the lease-protected push its own brief required (#236); `branch -D`, `branch --delete`,
# `push --delete` and `worktree remove` name reversible acts on a disposable lane whose
# branch is already pushed; the reviewer's whole list admitted `gh pr comment`,
# `gh pr review --approve` and `gh pr edit`, so it carried no independence of its own —
# that rests on `agents/reviewer.md`'s `disallowedTools` and the Codex `-s read-only`
# sandbox; and the orchestrator's `git merge` named a local, reversible merge while
# refusing an ordinary `gh issue create --body` (#351).
REFUSED_WORDS = {
    # An unreviewed squash to the default branch cannot be undone, and `guard protection`
    # configures no required review, so nothing else on the path stops it.
    'worker': ('merge',),
    # Read-only is the agent definition's and the sandbox's; the one command rule with a
    # real target is the `gh api` write flags below.
    'reviewer': (),
    # Merging outside `guard merge` skips the reviewed head, the rebase proof and the
    # green-checks read.
    'orchestrator': ('gh pr merge',),
}
# A `gh` command carrying one of these writes through the API; the reviewer is read-only.
REVIEWER_GH_WRITE = ('-X', '--method', '-f', '-F', '--input')
# The two names a default branch has. Written here rather than read from anywhere: a target that
# calls its branch something else is outside this rule, and the layer that catches the push it
# admits is GitHub's branch protection (#326).
DEFAULT_BRANCHES = ('main', 'master')

# ---------------------------------------------------------------------------
# Every refusal is a reminder, not a wall. A role that reaches for a guarded word has usually
# forgotten which lane it is in rather than defected, and the harness feeds this text back to
# the model as the tool result — so it is written to be acted on: what was refused, what the
# role does instead, and the one page to read (#323). #323 carried a fourth part, telling the
# caller how to re-spell a command that merely writes the word; #425 removed it with the words
# that made it necessary, because it existed to route around refusals these three do not make.
# ---------------------------------------------------------------------------
INSTEAD = {
    'worker': ('a worker pushes its own task branch and hands the PR back to the orchestrator, '
               'which owns acceptance, merge and teardown'),
    'reviewer': 'a reviewer returns a verdict and writes nothing',
    'orchestrator': ('the orchestrator merges only through `<plugin>/scripts/guard merge`, which '
                     'verifies the reviewed head, proves the rebase and reads GitHub itself'),
}
ROLE_PAGE = {
    'worker': "`reference/worker.md`'s Never section",
    'reviewer': "`reference/code-review-prompt.md`'s Output format section",
    'orchestrator': "`reference/orchestrator.md`'s Acceptance and integration section",
}


def refusal(role, word, subject='a command', qualifier=''):
    """The one refusal template, filled with the word the caller actually wrote."""
    return (f'{role} role refuses {subject} carrying {word!r}{qualifier}. '
            f'Instead, {INSTEAD[role]}. Read {ROLE_PAGE[role]}.')


def command_refusal(role, raw):
    """The whole shell decision: which of this role's words the command's own text carries."""
    text = command_only(raw)
    for word in REFUSED_WORDS[role]:
        if carries(text, word):
            return refusal(role, word)
    if role == 'reviewer' and carries(text, 'gh'):
        for flag in REVIEWER_GH_WRITE:
            if carries_flag(text, flag):
                return refusal(role, flag, subject='a `gh` command')
    # The orchestrator's is not here: founding pushes its first commits to the default
    # branch, and once founding has set protection GitHub refuses the push server-side.
    # This one survives for that same window, on the lane side, and nothing else.
    if role == 'worker' and carries(text, 'push'):
        named = next((name for name in DEFAULT_BRANCHES if carries(text, name)), None)
        if named:
            return refusal(role, 'push',
                           qualifier=f' that also names the default branch {named!r}')
    return None


def tool_decision(role, tool, arguments):
    """The hook's whole decision: this role's word list, against a command's own text.

    A tool name is admitted for every role, so the host's editing tool writes any file
    content whatever words it carries. Only a shell tool supplies command text for the
    role's word list to decide.
    """
    # The one carrier that is live today: dsh's shell tool is `bash` (model-facing, lowercase),
    # read at `tools/pre-execute` (ADR 0064). `Bash` was the Claude hook's, and `exec_command`
    # the Claude CLI's exec tool; both left with their carriers — `hooks/` here (#16) and the
    # Codex surface (#14) — so nothing sends either name now.
    if tool not in ('bash',):
        return None
    return command_refusal(role, arguments.get('command', arguments.get('cmd', '')) or '')


# ---------------------------------------------------------------------------
# The port's one model anchor (ADR 0066). The two delegation rows in `cordis.patch.yml` carry
# `agentOptions` for the single dispatched-role route; the worker row states it and the reviewer
# row aliases it. `.github/check-dsh-bundle.py` fails if the model id is stated anywhere else, so
# this reader has one place to look and a gate keeping it there. There are no tiers, no per-kind
# routing and no helper table: every dispatched role, the reviewer included, takes one route.
# ---------------------------------------------------------------------------
ANCHOR_PATH = 'cordis.patch.yml'


def model_anchor(root):
    """The one dispatched-role route as (model, effort), read from `cordis.patch.yml`.

    Parsed as YAML so the anchor/alias is resolved rather than scraped; `require` refuses a file
    that states no route, more than one, or a route missing either half.
    """
    import yaml
    routes = []
    for row in yaml.safe_load((Path(root) / ANCHOR_PATH).read_text()) or []:
        for entry in (row.get('insert') or []):
            options = (entry.get('config') or {}).get('agentOptions')
            if isinstance(options, dict):
                routes.append((options.get('model'), options.get('reasoningEffort')))
    require(routes, f'{ANCHOR_PATH} states no agentOptions route')
    require(all(route == routes[0] for route in routes),
            f'{ANCHOR_PATH} states more than one route: {routes!r}')
    model, effort = routes[0]
    require(model and effort, f'{ANCHOR_PATH} route lacks a model or effort')
    return model, effort
