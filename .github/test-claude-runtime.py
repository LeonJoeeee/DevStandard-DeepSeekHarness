#!/usr/bin/env python3
"""Exercise Claude Code plugin discovery and hooks with a local Anthropic fixture.

No external model calls, permission bypass, global settings edits or production
checkout changes. Requires Python 3.11+ and the Claude CLI. The isolated invocation
keeps HOME unchanged, ignores user/project/local settings, disables external MCP,
and permits only the fixture's harmless Bash printf commands. Stored logs include
the fixture requests and CLI events, never real authentication headers.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[1]
ALLOW = 'DEVSTANDARD_CLAUDE_ALLOWED_342'
DENY = 'DEVSTANDARD_CLAUDE_EXECUTED_342'
DUMMY_KEY = 'devstandard-local-fixture-no-real-credentials'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def text_fragments(value):
    """Every string in a fixture request, so escaping cannot hide a missing part."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from text_fragments(item)
    elif isinstance(value, list):
        for item in value:
            yield from text_fragments(item)


def delivered_contexts(selector='orchestrator'):
    """One artifact's complete emitted contexts, in part order, as the shipped hook emits them.

    A role page larger than one hook output is delivered across its declared handler calls
    (ADR 0059), so what the session must receive whole is every part, and these are the
    delivery's own bytes — header and body — rather than a restatement of the file.
    """
    groups = json.loads((ROOT / 'hooks/hooks.json').read_text())['hooks']['SessionStart']
    calls = []
    for group in groups:
        for handler in group['hooks']:
            args = handler['command'].split('"')[-1].split()
            if len(args) == 3 and args[0] == selector:
                calls.append((int(args[1]), int(args[2])))
    require(calls, 'no declared SessionStart handler for ' + selector)
    env = {key: value for key, value in os.environ.items()
           if key not in ('PLUGIN_DATA', 'CLAUDE_PLUGIN_DATA', 'DEVSTANDARD_ROLE')}
    env['CLAUDE_PLUGIN_DATA'] = 'devstandard-claude-runtime'
    parts = []
    for index, total in sorted(calls):
        result = subprocess.run([str(ROOT / 'hooks/session-start'), selector,
                                 str(index), str(total)],
                                input='{"source":"startup"}', capture_output=True, text=True,
                                cwd='/tmp', env=env, timeout=120, check=True)
        context = json.loads(result.stdout).get('hookSpecificOutput', {}).get('additionalContext', '')
        if context:
            parts.append(context)
    return parts


def part_bodies(contexts):
    """Each emitted context's page text, with its delivery header removed."""
    bodies = []
    for number, context in enumerate(contexts, start=1):
        head, blank, body = context.partition('\n\n')
        require(blank, f'part {number}: emitted context carries no delivery header')
        bodies.append(body)
    return bodies


def reconstruct_from_request(host_text, contexts, artifact):
    """Reassemble the page out of the text the HOST sent, in part order, and say where it landed.

    Each part is located by its own delivery header, which must appear exactly once, and the
    body is then taken FROM THE HOST TEXT rather than from the hook's output — so a part the
    host truncated, replaced with a persisted-output preview, escaped differently or dropped
    cannot reconstruct the page, and neither can a part that arrived twice. What the caller
    compares against the file is therefore the delivery as the model received it.

    The order is the parts' own numbering, which is what the delivery header tells the reader
    to reassemble by; the order they APPEAR in is the host's and is returned, never asserted.
    Measured on Claude Code 2.1.270 (issue #396): the declared handlers run concurrently and
    the host appends each context as its process finishes, and repeated runs of the same shipped
    three-part page produced all six orders of its parts. That is why the order is returned
    rather than asserted.
    """
    assembled = ''
    arrival = []
    for number, context in enumerate(contexts, start=1):
        head, blank, body = context.partition('\n\n')
        require(blank, f'{artifact} part {number}: emitted context carries no delivery header')
        anchor = head + blank
        seen = host_text.count(anchor)
        require(seen == 1, f'{artifact} part {number} of {len(contexts)}: its delivery header '
                           f'appears {seen} times in the host request, want exactly one')
        start = host_text.index(anchor) + len(anchor)
        assembled += host_text[start:start + len(body)]
        arrival.append(host_text.index(anchor))
    return assembled, [number for number, _ in
                       sorted(enumerate(arrival, start=1), key=lambda row: row[1])]


# How a request from the spawned child is told apart from its parent's: a string that appears
# in the child's own system prompt and in no parent's. The reviewer's definition opens with a
# hand-written identity line. The worker's definition body is role source verbatim since #402 —
# since #409 the shared contract page followed by `reference/harness-claude.md` (ADR 0061) — so its
# marker is the contract page's own opening declaration, the sentence CI pins in
# `.github/workflows/ci.yml` and which no other shipped page carries.
CHILD_MARKER = {'worker': '**This brief is what makes you a worker.**',
                'reviewer': 'You are the DevStandard reviewer'}


# What `agents/worker.md`'s generated body concatenates, in order (ADR 0061): the shared contract
# page every executor receives, then the Claude harness page only a Claude worker receives.
# `.github/check-agents.py` owns the concatenation rule; this names the same sources so the runtime
# proves the whole body — not just its first page — reaches the model.
WORKER_BODY_SOURCES = ('reference/worker.md', 'reference/harness-claude.md')


def role_page_carrier(host_text, role, case, log_dir):
    """What carries a dispatched Claude worker its role pages: `agents/<role>.md`'s own body.

    `scripts/dispatch` reads `reference/worker.md` into the brief only where no definition can
    carry it — `codex`. Both Claude paths send the task packet alone: the
    DEFAULT `--implementation claude` since #332, and `--implementation claude-cli` since #411,
    which ran `--agent devstandard:worker` and prepended the page as well until then. Until #402
    the definition carried no role text either, only the source path and an IN FULL read
    instruction, which this helper recorded honestly as an UNPROVEN carrier because a
    deterministic fixture cannot witness a model performing a read.

    The definition body is now the role source itself (ADR 0060), so the harness loads it as the
    subagent's system prompt and the bytes are here to be checked. Since #409 the worker's body is
    two pages concatenated byte for byte — the shared contract and the Claude harness mechanics
    under it (ADR 0061) — and the body is the only carrier that delivers the harness page to a
    Claude worker at all, so this asserts the whole of it: each page arrives byte-identical,
    exactly once, and the concatenation itself arrives intact, in the request the host actually
    sent.
    """
    sources = WORKER_BODY_SOURCES if role == 'worker' else ('reference/%s.md' % role,)
    pages = []
    for source in sources:
        path = ROOT / source
        require(path.is_file(), case + ': no shipped role page at ' + str(path))
        page = path.read_text()
        found = host_text.count(page)
        require(found == 1,
                case + ': ' + source + ' reached the host ' + str(found) + ' times, want '
                'exactly one byte-identical copy carried by the agent definition body')
        pages.append(page)
    body = ''.join(pages)
    require(host_text.count(body) == 1,
            case + ': the pages reached the host but not as the definition body\'s exact '
            'concatenation of ' + ' + '.join(sources))
    record = {'artifact': list(sources), 'page_bytes': [len(page.encode()) for page in pages],
              'body_bytes': len(body.encode()),
              'carrier': 'agents/%s.md body, loaded by the harness as the subagent system '
                         'prompt' % role,
              'page_delivered_in_prompt': True,
              'copies_in_host_request': 1,
              'proven_byte_identical_here': True,
              'why': 'the definition body IS the role sources concatenated, so their bytes are '
                     'in the request this fixture captured — no model read is involved'}
    (log_dir / (case + '.role-delivery.json')).write_text(json.dumps(record, indent=2) + '\n')
    return record


class AnthropicFixture:
    """The refused probe stays a harmless `printf`, with the guarded word as an unquoted
    operand. Until #351 it sat inside the quoted string the marker shares; the hook read
    quoted text then and does not now, so the word has to stand in the command itself for
    this probe to exercise a refusal at all (`reference/orchestrator.md`, The role hook).
    """

    def __init__(self, forbidden, native_role=None, diagnostic=None, parent_denial=False):
        self.requests = []
        self.child_requests = []
        self.main_requests = []
        self.errors = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                try:
                    require(self.path.split('?', 1)[0] == '/v1/messages',
                            'unexpected local endpoint: ' + self.path)
                    require(self.headers.get('x-api-key') == DUMMY_KEY,
                            'fixture did not receive its dummy API key')
                    require(not self.headers.get('Authorization'),
                            'fixture unexpectedly received an authorization header')
                    body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    outer.requests.append(body)
                    if diagnostic:
                        diagnostic.write_text(json.dumps(outer.requests, indent=2))
                    step = len(outer.requests)
                    require(step <= (8 if parent_denial else 7 if native_role else 3),
                            'unexpected extra model continuation')
                    model = body['model']
                    is_child = native_role and (CHILD_MARKER[native_role]
                                                in json.dumps(body.get('system')))
                    lane = outer.child_requests if is_child else outer.main_requests
                    lane.append(body)
                    logical_step = len(lane) if not native_role or is_child else 3
                    require(not is_child or len(lane) <= 3, 'unexpected child continuation')
                    block = ({'type': 'tool_use', 'id': 'toolu_devstandard_' + str(logical_step),
                              'name': 'Bash', 'input': {'command':
                              "printf '%s\\n' '" + (ALLOW if logical_step == 1 else DENY) + "'"
                              + ('' if logical_step == 1 else ' ' + forbidden)}}
                             if logical_step in (1, 2)
                             else {'type': 'text', 'text': 'Fixture complete.'})
                    if native_role and not is_child and len(lane) == (2 if parent_denial else 1):
                        block = {'type': 'tool_use', 'id': 'toolu_devstandard_agent',
                                 'name': 'Agent', 'input': {
                                     'subagent_type': 'devstandard:' + native_role,
                                     'description': 'Verify isolated role hooks',
                                     'prompt': 'Exercise the deterministic local fixture.'}}
                    elif parent_denial and not is_child and len(lane) == 1:
                        block = {'type': 'tool_use', 'id': 'toolu_devstandard_parent_denied',
                                 'name': 'Bash', 'input': {
                                     'command': "printf '%s\\n' '" + DENY + "' merge"}}
                    uses_tool = block['type'] == 'tool_use'
                    events = [
                        ('message_start', {'type': 'message_start', 'message': {
                            'id': 'msg_devstandard_' + str(step), 'type': 'message',
                            'role': 'assistant', 'model': model, 'content': [],
                            'stop_reason': None, 'stop_sequence': None,
                            'usage': {'input_tokens': 100, 'output_tokens': 1}}}),
                        ('content_block_start', {'type': 'content_block_start', 'index': 0,
                            'content_block': ({**block, 'input': {}} if uses_tool
                                              else {'type': 'text', 'text': ''})}),
                        ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                            'delta': ({'type': 'input_json_delta',
                                       'partial_json': json.dumps(block['input'])} if uses_tool
                                      else {'type': 'text_delta', 'text': block['text']})}),
                        ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                        ('message_delta', {'type': 'message_delta', 'delta': {
                            'stop_reason': 'tool_use' if uses_tool else 'end_turn',
                            'stop_sequence': None}, 'usage': {'output_tokens': 20}}),
                        ('message_stop', {'type': 'message_stop'}),
                    ]
                    payload = ''.join('event: ' + name + '\ndata: ' + json.dumps(data)
                                      + '\n\n' for name, data in events).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as error:
                    outer.errors.append(str(error))
                    if diagnostic:
                        diagnostic.with_suffix('.errors.json').write_text(json.dumps(outer.errors))
                    self.send_error(500)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def runtime(binary, fixture_dir, log_dir, role):
    case = role
    from_worker = case == 'native-reviewer-from-cli-worker'
    native = role.startswith('native-')
    marker = role.startswith('cli-')
    role = 'reviewer' if from_worker else role.removeprefix('native-').removeprefix('cli-')
    # Each role's own surviving rule since #425.
    forbidden = {'orchestrator': 'gh pr merge', 'worker': 'merge',
                 'reviewer': 'gh api -X'}[role]
    with AnthropicFixture(forbidden, role if native else None,
                          log_dir / (case + '.requests.json')) as fixture:
        env = {key: value for key, value in os.environ.items()
               if key in ('HOME', 'USER', 'LOGNAME', 'PATH', 'LANG', 'LC_ALL', 'TMPDIR')}
        env.update(TMPDIR=str(fixture_dir), ANTHROPIC_API_KEY=DUMMY_KEY,
                   ANTHROPIC_BASE_URL='http://127.0.0.1:' + str(fixture.server.server_port),
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                   CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL='1',
                   CLAUDE_CODE_DISABLE_THINKING='1',
                   CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK='1')
        if marker or from_worker:
            env['DEVSTANDARD_ROLE'] = 'worker' if from_worker else role
        command = [binary, '-p', 'Exercise the deterministic local fixture.',
                   '--restricted', '--setting-sources', '',
                   '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--plugin-dir', str(ROOT), '--tools',
                   'Bash,Read,Write,Edit' + (',Agent' if native else ''),
                   '--allowedTools', 'Bash(printf *)', '--permission-mode', 'dontAsk',
                   '--permission-prompts', 'none', '--no-session-persistence',
                   '--no-chrome', '--disable-slash-commands',
                   '--output-format', 'stream-json', '--verbose', '--include-hook-events',
                   '--debug-file', str(log_dir / (case + '.debug.log')),
                   '--model', 'claude-sonnet-4-6']
        if native:
            command += ['--allowedTools', 'Agent']
            if from_worker:
                command += ['--agent', 'devstandard:worker']
        elif role != 'orchestrator':
            command += ['--agent', 'devstandard:' + role]
        try:
            result = subprocess.run(command, cwd=fixture_dir, env=env,
                                    capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired as error:
            result = subprocess.CompletedProcess(command, 124,
                (error.stdout or b'').decode() if isinstance(error.stdout, bytes)
                else error.stdout or '',
                (error.stderr or b'').decode() if isinstance(error.stderr, bytes)
                else error.stderr or '')
    (log_dir / (case + '.stdout.jsonl')).write_text(result.stdout)
    (log_dir / (case + '.stderr.log')).write_text(result.stderr)
    (log_dir / (case + '.requests.json')).write_text(json.dumps(fixture.requests, indent=2))
    require(not fixture.errors, 'fixture protocol errors: ' + repr(fixture.errors))
    require(result.returncode == 0, role + ' CLI failed: ' + result.stderr[-2000:])
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    init = next((row for row in rows if row.get('type') == 'system'
                 and row.get('subtype') == 'init'), {})
    plugins = init.get('plugins', [])
    require([row['name'] for row in plugins] == ['devstandard'],
            'unexpected plugins in isolated invocation: ' + repr(plugins))
    require(not init.get('mcp_servers'), 'unrelated MCP server was loaded')
    require(len(fixture.child_requests if native else fixture.requests) == 3,
            case + ' did not complete both shell requests')
    request_text = json.dumps(fixture.requests[0], ensure_ascii=False)
    require('unknown harness' not in request_text, 'Claude plugin environment not recognized')
    if role == 'orchestrator' or (native and not from_worker):
        artifact = 'reference/orchestrator.md'
        contexts = delivered_contexts()
        bodies = part_bodies(contexts)
        page = (ROOT / artifact).read_bytes()
        require(''.join(bodies).encode() == page,
                'the hook does not rebuild ' + artifact + ' from its declared parts')
        require('DevStandard operating context: ' + artifact in request_text,
                'missing delivered artifact ' + artifact)
        delivered_text = '\n'.join(text_fragments(fixture.requests[0]))
        assembled, arrival = reconstruct_from_request(delivered_text, contexts, artifact)
        require(assembled.encode() == page,
                f'{artifact} did not arrive byte-identical: the parts taken from the host '
                f'request reassemble to {len(assembled.encode())} bytes, the file is '
                f'{len(page)}')
        (log_dir / (case + '.delivery.json')).write_text(json.dumps(
            {'artifact': artifact, 'page_bytes': len(page),
             'parts': len(contexts), 'part_bytes': [len(body.encode()) for body in bodies],
             'context_bytes': [len(context.encode()) for context in contexts],
             'reassembled_from_host_request_bytes': len(assembled.encode()),
             'byte_identical_to_file': assembled.encode() == page,
             # The host's, not ours: recorded so a change in it is visible, never asserted on.
             'prompt_arrival_order': arrival}, indent=2) + '\n')
    else:
        require('DevStandard operating context: reference/orchestrator.md' not in request_text,
                'direct CLI worker/reviewer inherited orchestrator context')
        # Since #402 the worker definition's body is role source verbatim — since #409
        # `reference/worker.md` followed by `reference/harness-claude.md` (ADR 0061) — so the
        # hand-written "You are the DevStandard worker" line it used to open with no longer
        # exists; `role_page_carrier` asserts the stronger thing that replaced it. The
        # reviewer's contract is assembled per review rather than shipped as a page, so its
        # definition keeps the hand-written identity line and is checked for that.
        if ('worker' if from_worker else role) == 'worker':
            role_page_carrier('\n'.join(text_fragments(fixture.requests[0])), 'worker', case,
                              log_dir)
        else:
            require('You are the DevStandard ' + role in request_text,
                    'direct CLI reviewer did not receive its shipped role')
    tool_results = []
    evidence_request = fixture.child_requests[-1] if native else fixture.requests[-1]
    for message in evidence_request['messages']:
        if isinstance(message.get('content'), list):
            tool_results += [block for block in message['content']
                             if block.get('type') == 'tool_result']
    allow_id = 'toolu_devstandard_1'
    deny_id = 'toolu_devstandard_2'
    allow = [block for block in tool_results if block.get('tool_use_id') == allow_id]
    deny = [block for block in tool_results if block.get('tool_use_id') == deny_id]
    require(len(allow) == len(deny) == 1, 'missing shell result evidence')
    require(not allow[0].get('is_error') and ALLOW in json.dumps(allow[0]),
            'harmless allowed command did not execute')
    require(deny[0].get('is_error') and role in json.dumps(deny[0])
            and 'refus' in json.dumps(deny[0]).lower(),
            'guard did not refuse the forbidden command for ' + role)
    if native:
        if role != 'worker':  # see above: the worker definition carries the page, not a line
            require('You are the DevStandard ' + role in json.dumps(fixture.child_requests[0]),
                    'native Agent did not receive the shipped role')
        require('DevStandard operating context: reference/orchestrator.md'
                not in json.dumps(fixture.child_requests[0]),
                'native Agent inherited orchestrator context')
        if role == 'worker':
            role_page_carrier('\n'.join(text_fragments(fixture.child_requests[0])),
                              role, case + '.child', log_dir)
    if role == 'reviewer':
        role_request = fixture.child_requests[0] if native else fixture.requests[0]
        writers = {'Write', 'Edit'} & {tool['name'] for tool in role_request['tools']}
        require(not writers, 'reviewer exposes disallowed built-in writers: ' + repr(writers))
    return {'role': case, 'requests': len(fixture.requests),
            'plugin': plugins[0], 'allowed': 'executed', 'forbidden': 'denied by role hook'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', default=shutil.which('claude'))
    parser.add_argument('--log-dir', type=Path, required=True)
    parser.add_argument('--roles', default='orchestrator,worker,reviewer,native-worker,native-reviewer,cli-worker,cli-reviewer,native-reviewer-from-cli-worker')
    args = parser.parse_args()
    require(args.claude, 'Claude CLI not found; provide --claude')
    for path in (Path('/etc/claude-code/managed-settings.json'),
                 Path('/Library/Application Support/ClaudeCode/managed-settings.json')):
        require(not path.exists(), 'runtime isolation unavailable: managed settings ' + str(path))
    args.log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='devstandard-claude-runtime-') as temporary:
        results = [runtime(args.claude, Path(temporary), args.log_dir, role)
                   for role in args.roles.split(',')]
    version = subprocess.check_output([args.claude, '--version'], text=True).strip()
    print(json.dumps({'status': 'pass', 'claude': version, 'cases': results}, indent=2))


if __name__ == '__main__':
    main()
