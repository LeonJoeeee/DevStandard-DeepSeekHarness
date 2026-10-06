"""Current-contract packet boundary shared by assembly and dispatch (stdlib only)."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORMAT = 'devstandard-review-packet-v1'
SLOT = re.compile(r'\{([A-Z_][A-Z_0-9]*)\}')
SHA = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})')


def require(condition, message):
    if not condition:
        raise ValueError(message)


# One statement of the verdict's decision-line tolerance, read by every parser of a verdict:
# the assembler's outcome(), the guard's acceptance(), and the guard's round admission.
DECISION = re.compile(r'^[*_]{0,2}(?:([12])\. [*_]{0,2}(Evidence-backed completion claim|Authorization and scope)'
                      r'|(Ready to merge)): [*_]{0,2}(Yes|No|Pass|Fail)[*_]{0,2}(?=[\W_]|$)', re.M)


def decisions(text):
    """Strip emphasis from every decision line — around the result, the label, or both."""
    return DECISION.sub(lambda match: (f'{match[1]}. {match[2]}' if match[1] else match[3]) + f': {match[4]}', text)


FLOOR_LABELS = ('1. Evidence-backed completion claim', '2. Authorization and scope')
DECISION_LABELS = ('Goal verdict', *FLOOR_LABELS, 'Ready to merge')
GROUNDS = ' — .+'


def decision_line(label, grounds=False):
    """One decision line's pattern: its result, and under `grounds` the grounds that follow it.

    The contract writes all four lines as a result then its grounds after a spaced em dash, and
    the guard refuses a line stating a bare result. Stated once here so publication applies the
    same requirement and calls such a verdict malformed rather than accepted (#287).
    """
    if label == 'Goal verdict':
        return r'^### Goal verdict\n(Yes|No)' + (GROUNDS if grounds else r'(?=[\W_]|$)')
    if label == 'Ready to merge':
        return r'^Ready to merge: (Yes|No)' + (GROUNDS if grounds else r'\b')
    return '^' + re.escape(label) + r': (Pass|Fail)' + (GROUNDS if grounds else r'\b')


def floor_results(text, label):
    """Every result one Floor line records, read after the decision lines are normalised.

    A caller wanting the verdict's answer takes the first; a caller refusing on a failure
    tests the whole list, so a second contradicting line cannot hide behind the first. The
    reading stays plain on purpose: grounds decide a verdict's validity, never which result
    it recorded, so no Fail hides behind a missing em dash.
    """
    return re.findall(decision_line(label), decisions(text), re.M)


# The Goal answer sits under its own heading rather than after a label, so it is normalised here
# too: ignore presentation around the heading and the answer, never cross nonblank content.
GOAL_HEADING = re.compile(r'^ {0,3}###[ \t]+[*_]{0,2}Goal verdict[*_]{0,2}[ \t]*(?:#+[ \t]*)?\r?\n', re.M)
GOAL_ANSWER = re.compile(r'(^### Goal verdict\n)(?:[ \t]*\r?\n)*[ \t]*[*_]{0,2}(Yes|No)[*_]{0,2}(?=[\W_]|$)', re.M)


def normalize(text):
    """The plain form every verdict parser reads: emphasis stripped, the Goal answer on its heading."""
    return GOAL_ANSWER.sub(r'\1\2', GOAL_HEADING.sub('### Goal verdict\n', decisions(text)))


def missing_grounds(text):
    """Every decision line that states a result without the grounds required after it.

    Compare the first result each line records against the first the grounded form can read: a
    result only the plain form sees is the line the guard refuses.
    """
    text = normalize(text)
    return [label for label in DECISION_LABELS
            if re.findall(decision_line(label), text, re.M)[:1]
            != re.findall(decision_line(label, grounds=True), text, re.M)[:1]]


def verdict_shape(text, head, identity=None):
    """One whole-verdict shape check for publication and acceptance; return the defect, if any.

    Readiness policy is separate: a well-formed No/Fail verdict is still a valid return.
    Keep result extraction independent too, so malformed text cannot hide a Floor 2 Fail.
    """
    text = normalize(text)
    text = re.sub(r' — reviewed\s+([0-9a-f]{40,64})', r' — reviewed \1', text)
    reviewer = re.escape(identity) if identity is not None else r'[^\n]+'
    if not re.match(r'Reviewer: ' + reviewer + ' — reviewed ' + re.escape(head) + r'\n', text):
        return 'latest verdict does not review the exact accepted head and reviewer'
    missing = missing_grounds(text)
    if missing:
        return 'decision lines stating no grounds: ' + ', '.join(missing)
    headings = list(re.finditer(r'^### (Goal verdict|Floor|Notes)\b[^\n]*$', text, re.M))
    if ([match[0] for match in headings] != ['### Goal verdict', '### Floor', '### Notes']):
        return 'duplicate, missing, or out-of-order verdict section'
    goal_section = text[headings[0].end():headings[1].start()]
    # Count decision lines, not later prose such as 'No prior verdicts were supplied'.
    answers = re.findall(r'^[ \t]*[*_]{0,2}(Yes|No)[*_]{0,2}[ \t]+—(?:[ \t]|$)', goal_section, re.M)
    if len(answers) != 1:
        return 'duplicate or missing Goal decision'
    matches = [list(re.finditer(decision_line(label, grounds=True), text, re.M))
               for label in DECISION_LABELS]
    if any(len(found) != 1 for found in matches):
        return 'duplicate or missing grounded decision line'
    # Groundless duplicates must not hide behind a grounded first decision.
    if any(len(re.findall(decision_line(label), text, re.M)) != 1 for label in DECISION_LABELS):
        return 'duplicate or missing decision line'
    goal, floor1, floor2, ready = [found[0] for found in matches]
    if not (goal.start() == headings[0].start() < goal.end() <= headings[1].start()
            < floor1.start() < floor2.start() < ready.start() < headings[2].start()):
        return 'decision lines outside their ordered Goal/Floor sections'
    if ready[1] != ('Yes' if (goal[1], floor1[1], floor2[1]) == ('Yes', 'Pass', 'Pass') else 'No'):
        return 'readiness contradicts Goal/Floor'
    # The contract asks the reviewer to close with its verbatim line and to write Notes; neither
    # is refused here. Every recorded firing was a well-formed verdict, and none ever caught a
    # forged, truncated or substituted one — PR #408 spent a round republishing an identical
    # verdict that had merely lost the closing line (#426).
    return None


def recovery_ruling(ruling, head):
    """A trusted continuation ruling must carry recovery evidence for this accepted head.

    The ruling publisher verifies a base advance or records the orchestrator's guard-refusal
    attestation. Consumers use that same durable decision; they never infer recovery from Notes.
    """
    if not ruling or ruling.get('decision') != 'continue' or ruling.get('head') != head:
        return False
    recovery = ruling.get('recovery')
    if not isinstance(recovery, dict) or recovery.get('head') != head:
        return False
    if recovery.get('kind') == 'behind-base':
        base = recovery.get('base')
        return isinstance(base, str) and bool(SHA.fullmatch(base)) and base != head
    if recovery.get('kind') == 'guard-refusal':
        reason = recovery.get('reason')
        return isinstance(reason, str) and bool(reason.strip())
    return False


# The release manifest: the bundle's own `package.json` since the version story moved off the
# retired `.claude-plugin` pair (#18). One file, so nothing is synchronized against it.
MANIFESTS = ('package.json',)


def pinned_git(project, env=None):
    """Read-only git reader returning raw bytes; env is pinned by sanitizing callers."""
    def git(*args):
        result = subprocess.run(['git', '-C', str(project), *args], capture_output=True, env=env)
        require(result.returncode == 0, 'cannot read pinned version diff: ' + result.stderr.decode(errors='replace'))
        return result.stdout
    return git


def manifest_bump(project, base, head, path, env=None):
    """One manifest's pinned pair differs only in its declared version line; give [old, new]."""
    git = pinned_git(project, env)
    before, after = [git('show', pin + ':' + path) for pin in (base, head)]
    old_lines, new_lines = before.splitlines(keepends=True), after.splitlines(keepends=True)
    if len(old_lines) != len(new_lines):
        return None
    changed = [(old, new) for old, new in zip(old_lines, new_lines) if old != new]
    if len(changed) != 1:
        return None
    matches = [re.fullmatch(rb'([ \t]*"version"[ \t]*:[ \t]*)("[^"\r\n]*")([ \t]*,?[ \t]*(?:\r?\n)?)', line)
               for line in changed[0]]
    if not all(matches) or matches[0][1] != matches[1][1] or matches[0][3] != matches[1][3]:
        return None
    try:
        documents = [json.loads(blob) for blob in (before, after)]
        values = [doc['version'] for doc in documents]
        if values != [json.loads(match[2]) for match in matches] or values[0] == values[1]:
            return None
    except (ValueError, KeyError, IndexError, TypeError):
        return None
    return values


def version_only(project, base, head, env=None):
    """Prove the complete pinned diff is only the release manifest version lines."""
    if not (SHA.fullmatch(base) and SHA.fullmatch(head)):
        return False  # Unpinned ends the proof, never the review: an ordinary packet is assembled.
    paths = [path.encode() for path in MANIFESTS]
    raw = pinned_git(project, env)('diff', '--no-ext-diff', '--no-textconv', '--no-renames',
                                   '--raw', '-z', base, head)
    entries = raw.rstrip(b'\0').split(b'\0')
    if len(entries) != 2 * len(MANIFESTS) or set(entries[1::2]) != set(paths):
        return False
    for header in entries[::2]:
        fields = header.split()
        if (len(fields) != 5 or fields[0] not in (b':100644', b':100755')
                or fields[0][1:] != fields[1] or fields[4] != b'M'):
            return False
    versions = [manifest_bump(project, base, head, path, env) for path in MANIFESTS]
    return bool(versions[0]) and all(version == versions[0] for version in versions)


# CI configuration is what a CI run reads as its own definition: the workflow files, plus the gate
# commands those workflows invoke. Stated once here; the packet's flag line is computed from it.
CI_CONFIGURATION = re.compile(r'\.github/(?:workflows/.+|[^/]+\.py)')


def ci_configuration_paths(project, base, head, env=None):
    """Sorted CI-configuration paths the pinned name-status diff touches; a run the diff configured."""
    require(SHA.fullmatch(base) and SHA.fullmatch(head), 'the pinned diff form needs full base and head SHAs')
    raw = pinned_git(project, env)('diff', '--no-ext-diff', '--no-textconv', '--no-renames',
                                   '--name-status', '-z', base, head)
    # --no-renames leaves every record one status and one path, so the paths are the odd fields.
    paths = set(field.decode() for field in raw.rstrip(b'\0').split(b'\0')[1::2])
    return sorted(path for path in paths if CI_CONFIGURATION.fullmatch(path))


def issue_contract(body):
    # Locate headings on a masked copy, then take values from the original text.
    # Fenced commands and nested headings are part of the issue's contract, not delimiters.
    masked = re.sub(r'<!--.*?-->', lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), body, flags=re.S)
    headings, offset, fence = [], 0, None
    for line in masked.splitlines(keepends=True):
        marker = re.match(r'^\s{0,3}(`{3,}|~{3,})', line)
        if marker:
            if fence is None:
                fence = marker[1]
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
        elif fence is None:
            heading = re.match(r'^(#{1,6})\s+([^\n]+?)\s*#*\s*$', line)
            if heading:
                headings.append((offset, offset+len(line), len(heading[1]), heading[2].lower()))
        offset += len(line)
    fields = {}
    for i, (_, begin, level, name) in enumerate(headings):
        if name not in ('goal', 'bounds', 'done-check'):
            continue
        require(name not in fields, f'duplicate {name} section')
        end = next((h[0] for h in headings[i+1:] if h[2] <= level), len(body))
        value = body[begin:end].strip()
        require(value and not SLOT.fullmatch(value) and value not in ('TODO', 'TBD', '{field}'),
                f'missing or unresolved placeholder in {name}')
        fields[name] = value
    require(set(fields) == {'goal', 'bounds', 'done-check'}, 'missing issue goal, bounds, or done-check')
    return fields


def template():
    matches = re.findall(r'\n```\n(.*?)\n```\n',
                         (ROOT / 'reference/code-review-prompt.md').read_text(), re.S)
    require(len(matches) == 1, 'current reviewer contract must have exactly one prompt fence')
    return matches[0]


PREDICATE_BEGIN = '<!-- BEGIN IN-REPO-WRITES PREDICATE -->'
PREDICATE_END = r'<!-- END IN-REPO-WRITES PREDICATE \((\d+) payload lines\) -->'


def predicate(text=None):
    """(unit, gap): the delimited in-repo-write unit this text carries, and what stopped a clean read.

    A gap is reported into the packet rather than refused (#434). The reviewer's own Floor check 1
    already fails a packet whose predicate is absent, unmarked, or miscounted, and a withheld packet
    never reaches the one reader whose job is to catch that.
    """
    if text is None:
        text = (ROOT / 'reference/in-repo-writes.md').read_text()
    if text.count(PREDICATE_BEGIN) != 1 or len(re.findall(PREDICATE_END, text)) != 1:
        return '', 'the predicate needs exactly one start marker and one counted end marker'
    match = re.search(re.escape(PREDICATE_BEGIN) + r'\n(.*?)\n' + PREDICATE_END, text, re.S)
    if not match:
        return '', 'the predicate markers do not delimit one unit'
    payload = len(match[1].split('\n'))
    if payload != int(match[2]):
        return match[0], f'the predicate declares {match[2]} payload lines and carries {payload}'
    return match[0], None


UNPINNED = 'NOT PINNED'
# Named in the packet's own integrity report, so the reviewer reads what assembly pinned beside
# what it could not. Ordering is fixed rather than sorted: pins first, then the two flags.
REPORTED_PINS = ('REVIEW_BASE_SHA', 'HEAD_SHA', 'CONVENTION_BASE_SHA', 'ACCEPTED_SPEC_BLOB_SHA',
                 'ARCHITECTURE_LEVEL_FLAG', 'CI_CONFIGURATION_PATHS', 'CI_FALLBACK_COMMENT_OR_NONE')


def validate(packet, identity=None):
    """The slots this packet renders with. A stale reviewer contract is the one refusal left (#434).

    It is kept because a reviewer judging by a contract other than the shipped one is not an
    independent reviewer. Every other integrity fact is reported by `integrity_report` into the
    packet's `## Packet integrity` section and decided by the reviewer's Floor check 1.
    """
    source = template()
    require(packet.get('template') == source, 'stale reviewer contract; assemble again')
    slots = dict(packet.get('slots', {}))
    if identity:
        slots['REVIEWER_IDENTITY'] = identity
    for key in set(SLOT.findall(source)):
        slots[key] = slots[key] if isinstance(slots.get(key), str) else UNPINNED
    current, _ = predicate()
    # The shipped predicate is what the reviewer applies; a packet carrying another one is a gap.
    slots['IN_REPO_WRITES_PREDICATE'] = SLOT.sub(lambda match: slots.get(match[1], UNPINNED), current)
    return slots


def integrity(packet, slots):
    """Every packet-integrity gap assembly could not close, in the order a reader checks them."""
    gaps = list(packet.get('integrity_gaps') or [])
    if packet.get('format') != FORMAT:
        gaps.append(f'format: the packet declares {packet.get("format")!r}, not {FORMAT}')
    source = template()
    for key in sorted(set(SLOT.findall(source))):
        value = slots.get(key, UNPINNED)
        if value == UNPINNED:
            gaps.append(f'{key}: the contract names this slot and assembly did not fill it')
        elif not value.strip():
            gaps.append(f'{key}: filled with empty text')
        # Quoted evidence is opaque: only an entire slot still equal to a marker is unfilled.
        elif SLOT.fullmatch(value.strip()) or value.strip() in ('TODO', 'TBD', '{field}'):
            gaps.append(f'{key}: unresolved placeholder {value.strip()}')
        elif key in ('REVIEW_BASE_SHA', 'HEAD_SHA', 'CONVENTION_BASE_SHA') and not SHA.fullmatch(value):
            gaps.append(f'{key}: {value} is not a full SHA')
        elif key == 'ACCEPTED_SPEC_BLOB_SHA' and value != 'NONE' and not SHA.fullmatch(value):
            gaps.append(f'{key}: {value} is neither a full blob SHA nor NONE')
        elif key == 'ARCHITECTURE_LEVEL_FLAG' and value not in ('YES', 'NO'):
            gaps.append(f'{key}: {value} is neither YES nor NO')
    current, gap = predicate()
    if gap:
        gaps.append('IN_REPO_WRITES_PREDICATE: the shipped source is unreadable — ' + gap)
    elif set(SLOT.findall(current)) - {'CONVENTION_BASE_SHA', 'REVIEW_BASE_SHA'}:
        gaps.append('IN_REPO_WRITES_PREDICATE: the shipped source carries an unknown control slot')
    stored = (packet.get('slots') or {}).get('IN_REPO_WRITES_PREDICATE')
    if not isinstance(stored, str):
        gaps.append('IN_REPO_WRITES_PREDICATE: the packet carries no predicate')
    else:
        unit, stored_gap = predicate(stored)
        if stored_gap:
            gaps.append('IN_REPO_WRITES_PREDICATE: ' + stored_gap)
        elif unit not in (current, slots.get('IN_REPO_WRITES_PREDICATE')):
            gaps.append('IN_REPO_WRITES_PREDICATE: the packet carries a predicate this source no '
                        'longer states; the shipped one is rendered above')
    return gaps


def integrity_report(packet, slots):
    """The `## Packet integrity` section: what assembly pinned, and what it could not."""
    def summary(value):
        first = (value.strip().splitlines() or [''])[0]
        return first[:200] + (' …' if len(first) > 200 or first != value.strip() else '')

    payload = re.search(PREDICATE_END, slots.get('IN_REPO_WRITES_PREDICATE', ''))
    pinned = [f'- {key}: {summary(slots.get(key, UNPINNED))}' for key in REPORTED_PINS]
    pinned.append('- IN_REPO_WRITES_PREDICATE: '
                  + (f'{payload[1]} declared payload lines' if payload else 'no counted end marker'))
    gaps = integrity(packet, slots) or ['NONE']
    return ('## Packet integrity (assembly report; judged under Floor check 1)\n'
            'Pinned:\n' + '\n'.join(pinned) + '\nCould not pin:\n'
            + '\n'.join('- ' + gap for gap in gaps) + '\n')


def render(packet, identity=None):
    slots = validate(packet, identity)
    # A single substitution never treats braces or headings inside evidence as template syntax.
    result = SLOT.sub(lambda match: slots[match[1]], packet['template'])
    result += '\n\n' + integrity_report(packet, slots)
    # Quoted whole and never scanned: the substitution above ran on the template alone, so a
    # `{TOKEN}` the issue happens to quote stays the issue's text rather than a slot.
    if packet.get('issue_body') is not None:
        result += '\n\n## Complete issue body (quoted evidence)\n' + packet['issue_body']
    if packet.get('accepted_spec_contents') is not None:
        result += '\n\n## Accepted spec blob contents (pinned above)\n' + packet['accepted_spec_contents']
    if packet.get('rebase_result') is not None:
        result += ('\n\n## Rebuild 5 comparison result (evidence only; full review still applies)\n'
                   + json.dumps(packet['rebase_result'], indent=2) + '\n')
    for prior in packet.get('prior_verdicts', []):
        result += '\n\n## Prior returned verdict (historical evidence, verbatim)\n' + prior
    return result


def decode(text):
    if text.lstrip().startswith('{'):
        return json.loads(text)
    return None
