#!/usr/bin/env python3
"""Exercise the dispatcher's real git lane machinery; fake GitHub I/O.

One implementation: the host's own subagent. The dispatcher prepares a lane and emits an
instruction for the bundle's `worker`/`reviewer` tool (or `send_message`, continuing one), so
there is no process to observe and no per-run liveness to fake here.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dispatch-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()  # macOS /var aliases /private/var.
        self.project = self.root / 'project'
        self.project.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.issue = self.root / 'issue.json'
        self.comments = self.root / 'comments.json'
        self.comments.write_text('[]')
        self.issue.write_text(json.dumps(dict(number=12, title='A small task', url='https://github.com/o/r/issues/12',
            state='OPEN', body='## Goal\nProduce evidence.\n## Bounds\nOne task only.\n## Done-check\nOutput is captured.')))
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
            ISSUE=str(self.issue), COMMENTS=str(self.comments), PR=str(self.root/'pr.json'), TMPDIR=str(self.root),
            GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Test')
        (self.project / '.gitignore').write_text('/.claude/worktrees/\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.tool('gh', '''import json,os,sys
from pathlib import Path
a=sys.argv[1:]; c=Path(os.environ['COMMENTS'])
def w(rows): t=c.with_name(c.name+'.tmp'); t.write_text(json.dumps(rows)); os.replace(t,c)
if a[:2]==['repo','view']: print('o/r')
elif a[:1]==['api']:
 if '/issues/comments/' in a[1]:
  rows=json.loads(c.read_text());row=next(r for r in rows if r['id']==int(a[1].rsplit('/',1)[1]))
  if '--input' in a:
   row['body']=json.loads(Path(a[a.index('--input')+1]).read_text())['body'];w(rows)
  print(json.dumps(row))
 elif '/issues/12/comments' in a[1]:
  assert '--paginate' in a
  rows=json.loads(c.read_text())
  print(json.dumps(rows[:1]));print(json.dumps(rows[1:]))
 elif '/comments' in a[1]: print(os.environ.get('REVIEW_COMMENTS','[]'))
 elif '/compare/' in a[1]: print(json.dumps({'behind_by':int(os.environ.get('PR_BEHIND','0'))}))
 elif '/git/trees/' in a[1] or '/git/blobs/' in a[1]:
  raise SystemExit('policy must be read from the local origin/main ref, not GitHub')
 else: print(json.dumps(json.loads(os.environ.get('DEFAULT_CI', '{"default_branch":"main","owner":{"login":"o"},"commit":{"sha":"abc"},"tree":[],"check_runs":[{"name":"test","status":"completed","conclusion":"success"}],"statuses":[]}'))))
elif a[:2]==['issue','view']:
 d=json.loads(Path(os.environ['ISSUE']).read_text());d['comments']=[dict(row,id='IC_fixture_'+str(i+1),url='https://github.com/o/r/issues/12#issuecomment-'+str(i+1)) for i,row in enumerate(json.loads(c.read_text()))];print(json.dumps(d))
elif a[:2]==['issue','comment']:
 body=Path(a[a.index('--body-file')+1]).read_text()
 record=json.loads(body.split('```json\\n')[1].split('\\n```')[0])
 if record['kind']=='run' and os.environ.get('PUBLICATION_PROBE'):
  import time
  time.sleep(.2)
  Path(os.environ['PUBLICATION_PROBE']).write_text(json.dumps(dict(record=record)))
 if record['kind']=='run' and os.environ.get('REJECT_RUN_PUBLICATION'): raise SystemExit('fixture publication failed')
 rows=json.loads(c.read_text());rows.append({'id':len(rows)+1,'body':Path(a[a.index('--body-file')+1]).read_text()});w(rows);print('https://github.com/o/r/issues/12#issuecomment-'+str(len(rows)))
elif a[:2]==['pr','view']:
 data=json.loads(Path(os.environ['PR']).read_text());rows=data if isinstance(data,list) else [data]
 print(json.dumps(next(p for p in rows if p['number']==int(a[2]))))
elif a[:2]==['pr','list']:
 p=Path(os.environ['PR']);rows=json.loads(p.read_text()) if p.exists() else []
 rows=rows if isinstance(rows,list) else [rows]
 if '--head' in a: rows=[row for row in rows if row['headRefName']==a[a.index('--head')+1]]
 if '--state' in a and a[a.index('--state')+1]!='all': rows=[row for row in rows if row['state']==a[a.index('--state')+1].upper()]
 print(json.dumps(rows))
else: raise SystemExit('unexpected gh: '+repr(a))
''')
        self.script = SOURCE / 'scripts/dispatch'

    def tool(self, name, body):
        p = self.bin / name
        p.write_text('#!/usr/bin/env python3\n'+body)
        p.chmod(0o755)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.project), *args], env=self.env, stderr=subprocess.DEVNULL, text=True).strip()

    def call(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(self.script), '12', *args, '--project', str(self.project)],
            env=self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
            self.result = r  # Keep stderr readable for the route assertion.
            return json.loads(r.stdout)
        self.assertNotEqual(r.returncode, 0)
        return r.stderr

    def start(self, *args):
        """A worker dispatch on the one native path (the host's own subagent)."""
        return self.call('--purpose', 'worker', '--base', 'origin/main', *args)

    def lane_records(self):
        return [json.loads(row['body'].split('```json\n')[1].split('\n```')[0])
                for row in json.loads(self.comments.read_text())]

    def instruction(self, run):
        return json.loads(Path(run['instruction']).read_text())

    def brief(self, run):
        return Path(run['brief']).read_text()

    def other_repo_worktree(self, branch):
        """A linked worktree of an entirely different repository, on the same branch name."""
        other = self.root/'other'; other.mkdir()
        def run(*args):
            return subprocess.check_output(['git','-C',str(other),*args],env=self.env,text=True).strip()
        run('init','-b','main')
        run('config','user.email','test@example.com'); run('config','user.name','Test')
        (other/'f.txt').write_text('other'); run('add','.'); run('commit','-m','base')
        wt = self.root/'other-worktree'
        run('worktree','add','-b',branch,str(wt),'HEAD')
        return wt

    def hand_made_lane(self):
        branch='feat/hand-made'; wt=self.root/'hand-made'
        self.git('worktree','add','-b',branch,str(wt),'origin/main')
        return branch,wt

    def review_packet(self, base=None, head=None, convention=None, identity='{REVIEWER_IDENTITY}'):
        import re
        base=base or self.git('rev-parse','origin/main');head=head or base
        template=re.search(r'\n```\n(.*?)\n```\n',
            (SOURCE/'reference/code-review-prompt.md').read_text(),re.S).group(1)
        predicate=re.search(r'<!-- BEGIN IN-REPO-WRITES PREDICATE -->.*?<!-- END IN-REPO-WRITES PREDICATE \(\d+ payload lines\) -->',
            (SOURCE/'reference/in-repo-writes.md').read_text(),re.S).group()
        slots=dict(ISSUE_GOAL_STATEMENT='Produce evidence.',ISSUE_BOUNDS='One task.',
            ISSUE_DONE_CHECK='Output captured.',ARCHITECTURE_LEVEL_FLAG='NO',
            COMPLETE_PR_DESCRIPTION='Complete report.',REVIEW_BASE_SHA=base,HEAD_SHA=head,
            CONVENTION_BASE_SHA=convention or base,ACCEPTED_SPEC_BLOB_SHA='NONE',
            CI_CONFIGURATION_PATHS='NONE',
            CI_FALLBACK_COMMENT_OR_NONE='NONE',IN_REPO_WRITES_PREDICATE=predicate,
            REVIEWER_IDENTITY=identity)
        packet=self.root/'review.txt'
        packet.write_text(json.dumps(dict(format='devstandard-review-packet-v1',template=template,slots=slots)))
        return packet

    def replace_run(self, record):
        rows = json.loads(self.comments.read_text())
        row = next(r for r in rows if record['brief'] in r['body'])
        row['body'] = '<!-- devstandard-dispatch-v1 -->\n```json\n'+json.dumps(record)+'\n```\n'
        self.comments.write_text(json.dumps(rows))

    def continuation_options(self):
        brief = self.root/'continue.txt'; brief.write_text('Complete the remaining work.')
        return ('--purpose', 'worker', '--continue', '--brief', str(brief))

    def pr(self, number, branch, state='OPEN'):
        return dict(number=number, url=f'https://github.com/o/r/pull/{number}', state=state,
                    mergedAt=None, baseRefName='main', headRefName=branch, headRefOid=self.git('rev-parse', branch))

    def test_a_worker_dispatch_emits_the_worker_tool_instruction_and_never_claims_a_launch(self):
        run = self.start()
        self.assertEqual(run['status'], 'awaiting-delegation')
        self.assertNotIn('pid', run)
        spawn = self.instruction(run)
        self.assertEqual(spawn['tool'], 'worker')
        self.assertEqual(spawn['description'], 'Issue 12 worker')
        self.assertTrue(spawn['run_in_background'])
        self.assertNotIn('model', spawn)
        self.assertNotIn('effort', spawn)
        self.assertNotIn('subagent_type', spawn)
        self.assertIn(run['brief'], spawn['prompt'])
        self.assertIn('IN FULL', spawn['prompt'])
        self.assertIn('Produce evidence.', self.brief(run))
        self.assertIn('record the returned child id', run['notice'])
        self.assertEqual([r['kind'] for r in self.lane_records()], ['lane', 'run'])

    def test_the_route_is_read_from_the_bundle_anchor_and_printed_with_its_source(self):
        """ADR 0066: one anchor in `cordis.patch.yml`; the run shows what it read and where."""
        run = self.start()
        self.assertEqual((run['model'], run['effort']), ('deepseek-v4.1-flash', 'max'))
        self.assertEqual(run['route_source'], str(SOURCE / 'cordis.patch.yml'))
        self.assertIn(f'dispatch route: deepseek-v4.1-flash at max from {SOURCE / "cordis.patch.yml"}',
                      self.result.stderr)
        self.assertIn('Executor: dsh deepseek-v4.1-flash max', self.brief(run))
        self.assertIn('Commit trailer: Co-Authored-By: dsh deepseek-v4.1-flash max <noreply@anthropic.com>',
                      self.brief(run))

    def test_a_resumed_continuation_uses_send_message_against_the_recorded_child(self):
        run = self.start()
        brief = self.root/'continue.txt'; brief.write_text('Repair the missing evidence only.')
        continued = self.call('--purpose', 'worker', '--continue', '--brief', str(brief),
                              '--resume', 'child-42')
        spawn = self.instruction(continued)
        self.assertEqual(spawn['tool'], 'send_message')
        self.assertEqual(spawn['agent_id'], 'child-42')
        self.assertIn(continued['brief'], spawn['message'])
        self.assertIn('Repair the missing evidence only.', self.brief(continued))
        self.assertEqual(continued['lane_id'], run['lane_id'])
        self.assertNotEqual(continued['brief'], run['brief'])

    def test_only_a_continuing_worker_may_resume(self):
        before = set(self.root.iterdir())
        self.assertIn('--resume', self.call('--purpose', 'worker', '--base', 'origin/main',
                                            '--resume', 'child-42', ok=False))
        self.assertEqual(set(self.root.iterdir()), before)
        self.assertEqual(self.lane_records(), [])

    def test_missing_fields_refused_before_any_lane_side_effect(self):
        """#427: only the reviewer reads these sections, so only the reviewer path still parses
        them — and it refuses before a packet is even opened."""
        for field in ['Goal', 'Bounds', 'Done-check']:
            with self.subTest(field=field):
                d=json.loads(self.issue.read_text()); original=d['body']
                d['body']=original.replace('## '+field, '## Other')
                self.issue.write_text(json.dumps(d))
                error=self.call('--purpose','reviewer','--packet',str(self.review_packet()),ok=False)
                self.assertIn(field.lower(),error.lower())
                self.assertFalse((self.project/'.claude').exists())
                self.assertEqual(json.loads(self.comments.read_text()),[])
                d['body']=original; self.issue.write_text(json.dumps(d))
        self.assertIn('base',self.call('--purpose','worker',ok=False))
        self.assertFalse((self.project/'.claude').exists())
        self.assertEqual(json.loads(self.comments.read_text()),[])

    def test_branch_and_worktree_defaults_are_deterministic_and_recorded(self):
        run=self.start()
        lane=self.lane_records()[0]
        self.assertEqual(lane['kind'],'lane')
        self.assertEqual(lane['branch'],'task/12-a-small-task')
        self.assertEqual(lane['worktree'],str(self.project/'.claude/worktrees/12-a-small-task'))
        self.assertEqual(lane['base'],'origin/main')
        self.assertEqual(lane['base_sha'],self.git('rev-parse','origin/main'))
        self.assertEqual(run['lane_id'],lane['lane_id'])
        self.assertEqual(run['issue_state'],'open')
        self.assertEqual(self.git('worktree','list','--porcelain').count('worktree '),2)

    def test_worker_packet_contains_the_verbatim_issue_and_human_comment_but_not_dispatch_records(self):
        """Dropping the preamble, a human comment, or retaining machine history breaks the handover."""
        issue = json.loads(self.issue.read_text())
        issue['body'] = ('Memo context that is outside the three contract headings.\n\n'
                         '## Goal\nProduce evidence.\n## Bounds\nOne task only.\n'
                         '## Done-check\nOutput is captured.')
        self.issue.write_text(json.dumps(issue))
        human_body = 'Human correction, kept byte for byte.\n\n```text\nDo the later thing.\n```'
        machine_body = ('<!-- devstandard-dispatch-v1 -->\n'
                        'Dispatcher lane observation.\n```json\n{"kind":"fixture"}\n```\n')
        self.comments.write_text(json.dumps([
            dict(id=41, user={'login':'human-owner'}, created_at='2026-09-13T12:34:56Z',
                 body=human_body),
            dict(id=42, user={'login':'human-owner'}, created_at='2026-09-13T12:35:00Z',
                 body=machine_body),
        ]))

        packet = self.brief(self.start())

        self.assertIn(issue['body'], packet)
        self.assertIn('Issue body (verbatim):', packet)
        self.assertIn('Issue comment by human-owner on 2026-09-13T12:34:56Z (verbatim):', packet)
        self.assertIn(human_body, packet)
        self.assertNotIn('<!-- devstandard-dispatch-v1 -->', packet)
        self.assertNotIn(machine_body, packet)

    def test_continuation_refetches_comments_for_its_worker_packet(self):
        """Reusing the first launch's issue snapshot would hide a conclusion added mid-lane."""
        first = self.start()
        first_packet = self.brief(first)
        later_body = 'Human conclusion added after the first launch, verbatim.'
        rows = json.loads(self.comments.read_text())
        rows.append(dict(id=99, user={'login':'human-owner'}, created_at='2026-09-13T12:40:00Z',
                         body=later_body))
        self.comments.write_text(json.dumps(rows))

        continued = self.call(*self.continuation_options())
        continued_packet = self.brief(continued)

        self.assertNotIn(later_body, first_packet)
        self.assertIn('Issue comment by human-owner on 2026-09-13T12:40:00Z (verbatim):',
                      continued_packet)
        self.assertIn(later_body, continued_packet)

    def test_reviewer_packet_carries_the_same_issue_record_without_changing_pinned_evidence(self):
        """Restricting the fresh issue to workers would leave the reviewer judging a stale task."""
        issue = json.loads(self.issue.read_text())
        issue['body'] = ('Memo and accepted design, kept byte for byte.\n\n'
                         '## Goal\nProduce evidence.\n## Bounds\nOne task only.\n'
                         '## Done-check\nOutput is captured.')
        self.issue.write_text(json.dumps(issue))
        human_body = 'Human task change for both dispatched purposes, verbatim.'
        self.comments.write_text(json.dumps([
            dict(id=51, user={'login':'human-owner'}, created_at='2026-09-14T08:15:00Z',
                 body=human_body),
        ]))

        worker = self.start()
        worker_prompt = self.brief(worker)
        packet = self.review_packet()
        packet_before = packet.read_bytes()
        review = self.call('--purpose', 'reviewer', '--packet', str(packet))
        reviewer_prompt = self.brief(review)

        def issue_record(prompt):
            start = prompt.index('Issue body (verbatim):')
            return prompt[start:prompt.index('\nExecutor:', start)]

        self.assertEqual(issue_record(reviewer_prompt), issue_record(worker_prompt))
        self.assertIn(issue['body'], reviewer_prompt)
        self.assertIn(human_body, reviewer_prompt)
        self.assertEqual(packet.read_bytes(), packet_before)

        marker = '## Pinned Git evidence\n'
        evidence = json.JSONDecoder().raw_decode(reviewer_prompt.split(marker, 1)[1])[0]
        sha = self.git('rev-parse', 'origin/main')
        command = f"git -C {worker['worktree']} diff --no-ext-diff --no-textconv --no-color"
        self.assertEqual(evidence, [
            dict(command=f'{command} --name-status {sha} {sha}', exit_code=0,
                 stdout=[], stderr=[]),
            dict(command=f'{command} --stat {sha} {sha}', exit_code=0,
                 stdout=[], stderr=[]),
            dict(command=f'{command} {sha} {sha}', exit_code=0, stdout=[], stderr=[]),
        ])

    def test_reviewer_identity_comes_from_the_anchor_not_the_caller(self):
        worker = self.start()
        for supplied in ('{REVIEWER_IDENTITY}', 'Wrong reviewer, stale-model'):
            with self.subTest(supplied=supplied):
                packet = self.review_packet(identity=supplied)
                history = '## PR fulfillment claim and evidence\nReviewer: Historical reviewer — reviewed old-head\n'
                data = json.loads(packet.read_text()); data['slots']['COMPLETE_PR_DESCRIPTION'] = history
                packet.write_text(json.dumps(data))
                review = self.call('--purpose', 'reviewer', '--packet', str(packet))
                prompt = self.brief(review)
                identity = 'dsh subagent, deepseek-v4.1-flash at max, read-only'
                self.assertIn(f'Reviewer: {identity} — reviewed', prompt)
                self.assertIn(f'Reviewer identity: {identity}.', prompt)
                self.assertNotIn(supplied, prompt)
                self.assertIn(history, prompt)
                self.assertEqual(review['model'], 'deepseek-v4.1-flash')

    def test_reviewer_reuses_lane_read_only_and_preserves_packet(self):
        run=self.start()
        packet=self.review_packet()
        review=self.call('--purpose','reviewer','--packet',str(packet))
        spawn=self.instruction(review)
        self.assertEqual(spawn['tool'],'reviewer')
        self.assertNotIn('model',spawn); self.assertNotIn('effort',spawn)
        self.assertNotIn('--dangerously-bypass-hook-trust',json.dumps(spawn))
        self.assertIn('Complete report.',self.brief(review))
        self.assertIn('Return the whole verdict to the caller',spawn['prompt'])
        self.assertEqual(review['worktree'],run['worktree'])

    def test_invalid_inputs_leave_no_worktree_or_comments(self):
        for options in [('--base','HEAD'),('--base','missing/ref'),('--base',self.git('rev-parse','HEAD')),
                        ('--base','origin/main','--branch','bad branch'),
                        ('--base','origin/main','--packet',str(self.root/'absent'))]:
            # Worker packets are not accepted: they must not be silently ignored.
            self.call('--purpose','worker',*options,ok=False)
            self.assertFalse((self.project/'.claude').exists())
            self.assertEqual(json.loads(self.comments.read_text()),[])

    def test_an_unparsed_issue_body_and_comment_still_reach_the_worker_verbatim(self):
        """#427: nothing has read the dispatcher's issue-contract parse since #402, and its own
        refusals stopped this issue's first dispatch for naming the token they look for."""
        body = ('## Goal\nUse a {PLACEHOLDER} token and leave the rest TBD.\n'
                '## Goal\nA second one, because a human wrote two.\n'
                '## Done-check\n')
        self.issue.write_text(json.dumps(dict(json.loads(self.issue.read_text()), body=body)))
        self.comments.write_text(json.dumps([dict(id=61, body='A comment with neither login nor date.')]))
        run = self.start()
        packet = self.brief(run)
        self.assertIn(body, packet)
        self.assertIn('Issue comment by unknown author on unknown date (verbatim):', packet)
        self.assertIn('A comment with neither login nor date.', packet)
        self.assertEqual(run['kind'], 'run')
        self.assertIn(run['branch'], self.git('branch', '--list', run['branch']))

    def test_a_closed_issue_dispatches_and_the_run_record_says_so(self):
        """#436: whether a closed issue deserves a lane is the orchestrator's call; the refusal
        only stranded work whose issue was already closed."""
        self.issue.write_text(json.dumps(dict(json.loads(self.issue.read_text()), state='CLOSED')))
        run = self.start()
        self.assertEqual(run['issue_state'], 'closed')
        self.assertIn(run['branch'], self.git('branch', '--list', run['branch']))
        self.assertEqual([r['kind'] for r in self.lane_records()], ['lane', 'run'])

    def test_a_brief_quoting_placeholder_tokens_still_dispatches(self):
        """#436: a continuation brief that quotes a Note or a template slot is prose. This class
        refused #427's own first two dispatches."""
        run = self.start()
        brief = self.root/'continue.txt'
        text = 'Answer the Note: the {SLOT} field is still TBD and the TODO list stands.'
        brief.write_text(text)
        continued = self.call('--purpose', 'worker', '--continue', '--brief', str(brief))
        self.assertIn(text, self.brief(continued))
        brief.write_text('   \n')  # An empty brief is still nothing to act on.
        self.assertIn('brief', self.call('--purpose', 'worker', '--continue',
                                         '--brief', str(brief), ok=False))

    def test_worker_continuation_without_a_ruling_refuses_before_launch(self):
        """#434: seven returned rounds no longer refuse; the missing ruling still does."""
        run = self.start()
        head = self.git('rev-parse', run['branch'])
        (self.root/'pr.json').write_text(json.dumps(dict(number=13, url='https://github.com/o/r/pull/13',
            state='OPEN', baseRefName='main', headRefName=run['branch'], headRefOid=head)))
        rows = [{'id':i, 'user':{'login':'o'}, 'body':f'## Merge check 1 — round {i}\nReviewer: Probe — reviewed {head}\n'} for i in range(1,8)]
        self.env['REVIEW_COMMENTS'] = json.dumps(rows)
        brief = self.root/'continue.txt'; brief.write_text('Repair the goal gap.')
        before = self.comments.read_text()
        self.assertIn('continuation ruling required',
                      self.call('--purpose','worker','--continue','--pr','13','--brief',str(brief),ok=False))
        self.assertEqual(self.comments.read_text(), before)

    def test_accepted_recovery_continuation_keeps_the_delivered_lane(self):
        import runpy
        verdicts = runpy.run_path(str(SOURCE / '.github/test-review-packet.py'))
        first = self.start()
        head = self.git('rev-parse', first['branch'])
        pr = dict(number=13, url='https://github.com/o/r/pull/13', state='OPEN', mergedAt=None,
                  baseRefName='main', headRefName=first['branch'], headRefOid=head)
        Path(self.env['PR']).write_text(json.dumps(pr))
        row = dict(id=1, user=dict(login='o'), body='## Merge check 1 — round 1\n' +
                   verdicts['canonical_verdict'](head))
        rule = dict(kind='ruling', round=1, head=head, decision='continue', reason='Rebase the accepted lane.')
        def rows():
            return json.dumps([row, dict(id=2, user=dict(login='o'),
                body='## Review ruling — after round 1\n\n<!-- devstandard-review-v1 -->\n```json\n' +
                     json.dumps(rule) + '\n```\n')])
        self.env['REVIEW_COMMENTS'] = rows()
        brief = self.root / 'continue.txt'
        brief.write_text('Rebase the accepted head onto current main and repeat the done-check.')
        before = self.comments.read_text()
        self.assertIn('Notes', self.call('--purpose', 'worker', '--continue', '--pr', '13',
                                        '--brief', str(brief), ok=False))
        self.assertEqual(self.comments.read_text(), before)
        (self.project / 'main.txt').write_text('Main advanced.\n')
        self.git('add', 'main.txt')
        self.git('commit', '-m', 'advance main')
        base = self.git('rev-parse', 'HEAD')
        rule['recovery'] = dict(kind='behind-base', head=head, base=base)
        self.env['REVIEW_COMMENTS'] = rows()
        continued = self.call('--purpose', 'worker', '--continue', '--pr', '13', '--brief', str(brief))
        for key in ('lane_id', 'branch', 'worktree'):
            self.assertEqual(continued[key], first[key])
        self.assertEqual(continued['pr'], pr['url'])

    def test_version_only_rebase_continuation_reuses_the_acceptance_without_a_ruling(self):
        """#421: main moved under an accepted head; the rebase costs no ruling and no round."""
        import runpy
        verdicts = runpy.run_path(str(SOURCE / '.github/test-review-packet.py'))
        first = self.start()
        head = self.git('rev-parse', first['branch'])
        Path(self.env['PR']).write_text(json.dumps(self.pr(13, first['branch'])))
        accepted = [dict(id=1, user=dict(login='o'), body='## Merge check 1 — round 1\n'
                         + verdicts['canonical_verdict'](head))]
        self.env['REVIEW_COMMENTS'] = json.dumps(accepted)
        brief = self.root / 'continue.txt'
        brief.write_text('Rebase onto current main and carry the lockstep bump.')
        options = ('--purpose', 'worker', '--continue', '--pr', '13', '--brief', str(brief))
        # (b) The PR's base is still the default branch's head: today's refusal stands.
        before = self.comments.read_text()
        self.assertIn('Notes', self.call(*options, ok=False))
        self.assertEqual(self.comments.read_text(), before)
        # (c) A recorded ruling governs unchanged, base advance or not.
        self.env['PR_BEHIND'] = '1'
        rule = dict(kind='ruling', round=1, head=head, decision='continue', reason='assessed gap')
        self.env['REVIEW_COMMENTS'] = json.dumps(accepted + [dict(id=2, user=dict(login='o'),
            body='## Review ruling — after round 1\n\n<!-- devstandard-review-v1 -->\n```json\n'
                 + json.dumps(rule) + '\n```\n')])
        self.assertIn('Notes', self.call(*options, ok=False))
        self.assertEqual(self.comments.read_text(), before)
        # (a) No ruling, base advanced: admitted on the acceptance and recorded as the rebase.
        self.env['REVIEW_COMMENTS'] = json.dumps(accepted)
        continued = self.call(*options)
        self.assertEqual(continued['continuation'], 'rebase')
        for key in ('lane_id', 'branch', 'worktree'):
            self.assertEqual(continued[key], first[key])
        self.assertEqual(continued['pr'], 'https://github.com/o/r/pull/13')
        # No round and no ruling: the lane published the run record and nothing else.
        self.assertEqual([r['kind'] for r in self.lane_records()], ['lane', 'run', 'run'])

    def test_delivered_lane_continues_into_an_open_replacement_pr_on_its_branch(self):
        branch,wt=self.hand_made_lane()
        old=self.pr(13,branch)
        (self.root/'pr.json').write_text(json.dumps(old))
        lane=self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main','--pr','13')
        replacement=self.pr(14,branch)
        (self.root/'pr.json').write_text(json.dumps([dict(old,state='CLOSED'),replacement]))
        brief=self.root/'continue.txt';brief.write_text('Continue the rewritten delivery.')

        continued=self.call('--purpose','worker','--continue','--brief',str(brief),'--pr','14')
        self.assertEqual(continued['lane_id'],lane['lane_id'])
        self.assertEqual(continued['pr'],replacement['url'])

    def test_delivered_lane_refuses_a_replacement_pr_from_another_branch(self):
        branch,wt=self.hand_made_lane()
        old=self.pr(13,branch)
        (self.root/'pr.json').write_text(json.dumps(old))
        self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main','--pr','13')
        other=self.pr(14,'main')
        (self.root/'pr.json').write_text(json.dumps([dict(old,state='CLOSED'),other]))
        brief=self.root/'continue.txt';brief.write_text('Continue the rewritten delivery.')

        self.assertIn('PR branch differs from lane',self.call('--purpose','worker','--continue',
            '--brief',str(brief),'--pr','14',ok=False))

    def test_delivered_lane_without_pr_resolves_the_open_pr_on_its_branch(self):
        branch,wt=self.hand_made_lane()
        old=self.pr(13,branch)
        (self.root/'pr.json').write_text(json.dumps(old))
        lane=self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main','--pr','13')
        replacement=self.pr(14,branch)
        (self.root/'pr.json').write_text(json.dumps([dict(old,state='CLOSED'),replacement]))
        brief=self.root/'continue.txt';brief.write_text('Continue the rewritten delivery.')

        continued=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertEqual(continued['lane_id'],lane['lane_id'])
        self.assertEqual(continued['pr'],replacement['url'])

    def test_delivered_lane_whose_pr_is_closed_or_ambiguous_continues_on_the_lane_branch(self):
        """#427: this family stranded #362's lane twice (#371/#372). A closed or ambiguous PR is
        reported in the run record; the continuation still reaches its lane branch."""
        branch,wt=self.hand_made_lane()
        old=self.pr(13,branch)
        (self.root/'pr.json').write_text(json.dumps(old))
        lane=self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main','--pr','13')
        brief=self.root/'continue.txt';brief.write_text('Continue the rewritten delivery.')

        # A delivered lane whose only PR has been closed.
        (self.root/'pr.json').write_text(json.dumps([dict(old,state='CLOSED')]))
        continued=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertEqual(continued['lane_id'],lane['lane_id'])
        self.assertIsNone(continued['pr'])
        self.assertIn('#13 CLOSED',continued['pr_note'])
        self.assertNotIn('\nPR:',self.brief(continued))

        # The named PR is closed: the caller's explicit choice is reported, not refused.
        named=self.call('--purpose','worker','--continue','--brief',str(brief),'--pr','13')
        self.assertEqual(named['pr'],old['url'])
        self.assertIn('#13 is CLOSED',named['pr_note'])

        # Two open PRs on the lane branch: pick none, say so, continue.
        (self.root/'pr.json').write_text(json.dumps([self.pr(14,branch),self.pr(15,branch)]))
        ambiguous=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertIsNone(ambiguous['pr'])
        self.assertIn('#14',ambiguous['pr_note']);self.assertIn('#15',ambiguous['pr_note'])
        self.assertEqual([r for r in self.lane_records() if r['kind']=='run'][-1]['pr_note'],
                         ambiguous['pr_note'])

    def test_pre_pr_continuation_reuses_recorded_lane(self):
        run=self.start()
        brief=self.root/'continue.txt';brief.write_text('Continue after the receipt escalation.')
        self.assertIn('--brief',self.call('--purpose','worker','--continue',ok=False))
        continued=self.call('--purpose','worker','--continue','--brief',str(brief))
        for key in ('lane_id','branch','worktree','base','base_sha'):
            self.assertEqual(continued[key],run[key])
        self.assertIsNone(continued['pr'])
        self.assertIn(brief.read_text(),self.brief(continued))
        self.assertNotIn('\nPR:',self.brief(continued))
        self.assertEqual(len([r for r in self.lane_records() if r['kind']=='lane']),1)
        self.assertEqual(self.git('worktree','list','--porcelain').count('worktree '),2)
        # A worker may have opened a PR without another dispatcher observation.
        (self.root/'pr.json').write_text(json.dumps(dict(number=13,url='https://github.com/o/r/pull/13',state='OPEN',baseRefName='main', headRefName=run['branch'],headRefOid=self.git('rev-parse',run['branch']))))
        delivered=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertEqual(delivered['pr'],'https://github.com/o/r/pull/13')

    def test_adopted_lane_supports_review_and_pre_pr_continuation(self):
        branch,wt=self.hand_made_lane()
        before=self.git('rev-parse',branch)
        lane=self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main')
        self.assertEqual(lane['kind'],'lane');self.assertEqual(lane['status'],'adopted')
        self.assertEqual(lane['branch'],branch);self.assertEqual(lane['worktree'],str(wt))
        self.assertEqual(self.lane_records(),[lane])
        self.assertEqual(self.git('rev-parse',branch),before)
        self.assertNotIn('pid',lane)
        packet=self.review_packet()
        review=self.call('--purpose','reviewer','--packet',str(packet))
        self.assertEqual(self.instruction(review)['tool'],'reviewer')
        brief=self.root/'continue.txt';brief.write_text('Continue the adopted work.')
        continued=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertEqual(continued['lane_id'],lane['lane_id'])
        self.assertEqual(continued['worktree'],str(wt))
        self.assertIn('lane exists',self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main',ok=False))

    def test_adoption_records_pr_and_continuation_keeps_it(self):
        branch,wt=self.hand_made_lane()
        pr=dict(number=13,url='https://github.com/o/r/pull/13',state='OPEN',baseRefName='main', headRefName=branch,headRefOid=self.git('rev-parse',branch))
        (self.root/'pr.json').write_text(json.dumps(pr))
        lane=self.call('--adopt','--branch',branch,'--worktree',str(wt),'--base','origin/main','--pr','13')
        self.assertEqual(lane['pr'],pr['url'])
        brief=self.root/'continue.txt';brief.write_text('Repair the delivered lane.')
        resolved=self.call('--purpose','worker','--continue','--brief',str(brief))
        self.assertEqual(resolved['pr'],pr['url'])
        continued=self.call('--purpose','worker','--continue','--brief',str(brief),'--pr','13')
        self.assertEqual(continued['pr'],pr['url']);self.assertEqual(continued['lane_id'],lane['lane_id'])

    def test_adoption_refuses_missing_or_mismatched_lane_without_side_effects(self):
        branch,wt=self.hand_made_lane()
        for options in [('--branch',branch),('--worktree',str(wt)),
                        ('--branch','feat/absent','--worktree',str(wt)),
                        ('--branch',branch,'--worktree',str(self.root/'absent')),
                        ('--branch','main','--worktree',str(self.project)),
                        ('--branch',branch,'--worktree',str(wt),'--continue')]:
            with self.subTest(options=options):
                self.call('--adopt','--base','origin/main',*options,ok=False)
                self.assertEqual(self.lane_records(),[])
                self.assertTrue(wt.exists())
                self.assertEqual(self.git('worktree','list','--porcelain').count('worktree '),2)
        self.assertIn('base',self.call('--adopt','--branch',branch,'--worktree',str(wt),ok=False))
        self.assertEqual(self.lane_records(),[])
        (self.root/'pr.json').write_text(json.dumps(dict(number=13,url='https://github.com/o/r/pull/13',state='OPEN',baseRefName='main', headRefName='feat/other')))
        self.assertIn('PR branch differs',self.call('--adopt','--base','origin/main','--branch',branch,'--worktree',str(wt),'--pr','13',ok=False))
        self.assertEqual(self.lane_records(),[])

    def test_lane_check_refuses_another_repository_and_a_main_checkout(self):
        """#436: what lane_check still bounds is where a later destructive cleanup would land."""
        branch, wt = self.hand_made_lane()
        foreign = self.other_repo_worktree(branch)
        self.assertIn('another repository', self.call(
            '--adopt','--base','origin/main','--branch',branch,'--worktree',str(foreign),ok=False))
        self.assertIn('linked worktree', self.call(
            '--adopt','--base','origin/main','--branch',branch,'--worktree',str(self.project),ok=False))
        self.assertEqual(self.lane_records(), [])
        # The bookkeeping that went with it: a recorded branch the worktree is not checked out on
        # is now recorded for the operator to read, not refused (#436).
        lane = self.call('--adopt','--base','origin/main','--branch','main','--worktree',str(wt))
        self.assertEqual((lane['branch'], lane['worktree']), ('main', str(wt)))

    def test_a_differently_spelled_path_still_names_the_same_checkout_and_lane(self):
        """Compare a caller's path with git's own as one filesystem object, not one spelling.

        `resolve()` normalizes symlinks but never case, so a macOS checkout reached as
        `/Users/leon/Projects/x` was refused as "not a checkout root" against git's spelling of
        the same directory (#443). Linux cannot write that difference — real git resolves every
        spelling available here — so this holds the property on the spellings it does have, and
        the macOS record on #379 stays the defect's evidence.
        """
        link = self.root/'project-link'
        link.symlink_to(self.project)
        spelled = link/'..'/link.name
        self.assertNotEqual(str(spelled), self.git('rev-parse', '--show-toplevel'))
        result = subprocess.run([sys.executable, str(self.script), '12', '--purpose', 'worker',
                                 '--base', 'origin/main', '--project', str(spelled)],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        record = json.loads(result.stdout)
        respelled = link/Path(record['worktree']).relative_to(self.project)
        continued = self.call(*self.continuation_options(), '--worktree', str(respelled))
        self.assertEqual((continued['worktree'], continued['lane_id']),
                         (record['worktree'], record['lane_id']))

    def test_symlink_looped_path_arguments_refuse_rather_than_traceback(self):
        """#453: the lane artifact family was one resolve site of several. A looped `--project`,
        a looped `--worktree` on lane creation, and a looped `--worktree` compared against the
        recorded lane each reached a bare `Path.resolve()`, which answers a loop by interpreter —
        `RuntimeError` through 3.12, the path itself from 3.13 — past a handler that catches
        neither. All three now route through `resolved()`/`same_path()`, so each refuses in the
        same words on 3.12 and on the default interpreter alike."""
        loop = self.root/'loop'; loop.symlink_to(loop)

        def refusal(*args, project=None):
            result = subprocess.run([sys.executable, str(self.script), '12', '--project',
                str(project or self.project), *args], env=self.env, text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            return result.stderr

        new = ('--purpose', 'worker', '--base', 'origin/main')
        self.assertIn(f'dispatch refused: malformed project: symlink loop at {loop}',
                      refusal(*new, project=loop))
        self.assertIn(f'dispatch refused: malformed worktree: symlink loop at {loop}',
                      refusal(*new, '--worktree', str(loop)))
        # The recorded-lane comparison reaches `same_path`'s lexical fallback: `samefile` itself
        # already refuses the loop with `ELOOP`, and the fallback used to resolve it raw.
        self.start()
        self.assertIn(f'dispatch refused: malformed path: symlink loop at {loop}',
                      refusal(*self.continuation_options(), '--worktree', str(loop)))

    def test_failed_run_publication_leaves_only_the_lane_without_a_recorded_run(self):
        probe = self.root/'publication.json'
        self.env.update(PUBLICATION_PROBE=str(probe), REJECT_RUN_PUBLICATION='1')
        error = self.call('--purpose', 'worker', '--base', 'origin/main', ok=False)
        self.assertIn('fixture publication failed', error)
        observed = json.loads(probe.read_text())
        self.assertEqual(observed['record']['kind'], 'run')
        # Only the lane record was published; the run never made it onto the issue.
        self.assertEqual([row['kind'] for row in self.lane_records()], ['lane'])

    def test_a_duplicate_branch_or_worktree_surfaces_gits_own_error(self):
        """#427: `git worktree add -b` raises each of these itself; the dispatcher relays it."""
        branch,wt=self.hand_made_lane()
        error=self.call('--purpose','worker','--base','origin/main','--branch',branch,ok=False)
        self.assertIn('git',error);self.assertIn('already exists',error)
        self.assertEqual(self.lane_records(),[])
        occupied=self.root/'occupied';occupied.mkdir();(occupied/'keep').write_text('keep')
        error=self.call('--purpose','worker','--base','origin/main','--worktree',str(occupied),ok=False)
        self.assertIn('already exists',error)
        self.assertEqual((occupied/'keep').read_text(),'keep')
        self.assertEqual(self.lane_records(),[])

    def test_reviewer_packet_inlines_pinned_diffs_and_convention_blobs(self):
        doc=self.project/'guide.md';doc.write_text('Convention content.\n\n')
        old=self.project/'old name.md';old.write_text('Renamed content.\n')
        (self.project/' notes').write_text('')
        self.git('add','.');self.git('commit','-m','convention docs')
        convention=self.git('rev-parse','HEAD')
        doc.write_text('Review base content.\n')
        self.git('add','.');self.git('commit','-m','review base')
        base=self.git('rev-parse','HEAD')
        self.git('update-ref','refs/remotes/origin/main',base)
        run=self.start();wt=Path(run['worktree'])
        (wt/'guide.md').write_text('Pinned head content.\n')
        (wt/'old name.md').rename(wt/'new name.md')
        (wt/'added.md').write_text('New documentation.\n')
        (wt/' notes').write_text('Prose without a documentation extension.\n')
        self.git('-C',str(wt),'add','.')
        self.git('-C',str(wt),'commit','-m','reviewed changes')
        head=self.git('rev-parse',run['branch'])
        packet=self.review_packet(base,head,convention,identity='dsh subagent, deepseek-v4.1-flash at max, read-only')
        # Neither the checkout nor a later branch tip may substitute for the pinned head.
        (wt/'guide.md').write_text('Later content must not appear.\n')
        self.git('-C',str(wt),'add','.')
        self.git('-C',str(wt),'commit','-m','later change')
        review=self.call('--purpose','reviewer','--packet',str(packet))
        prompt=self.brief(review)
        self.assertIn('## Pinned Git evidence\n',prompt)
        evidence=json.JSONDecoder().raw_decode(prompt.split('## Pinned Git evidence\n',1)[1])[0]
        for entry,options in zip(evidence[:3],[['--name-status'],['--stat'],[]]):
            expected=subprocess.check_output(['git','-C',str(wt),'diff',*options,base,head],text=True,env=self.env)
            self.assertIsInstance(entry['stdout'],list)
            self.assertTrue(all(len(chunk) <= 1000 for chunk in entry['stdout']))
            self.assertEqual(''.join(entry['stdout']),expected)
            self.assertEqual(entry['exit_code'],0)
            self.assertIn(base,entry['command']);self.assertIn(head,entry['command'])
        blobs={entry['command'].split(convention+':',1)[1].rstrip("'"):entry for entry in evidence[3:]}
        self.assertEqual(''.join(blobs['guide.md']['stdout']),'Convention content.\n\n')
        self.assertEqual(''.join(blobs['old name.md']['stdout']),'Renamed content.\n')
        self.assertEqual(''.join(blobs[' notes']['stdout']),'')
        self.assertEqual(blobs[' notes']['exit_code'],0)
        for path in ('added.md','new name.md'):
            self.assertNotEqual(blobs[path]['exit_code'],0)
            self.assertTrue(blobs[path]['stderr'])
        self.assertNotIn('Later content must not appear.',prompt)

    def test_structured_packet_keeps_quoted_slots_and_diff_out_of_control_fields(self):
        import re
        run=self.start()
        template=re.search(r'\n```\n(.*?)\n```\n',
            (SOURCE/'reference/code-review-prompt.md').read_text(),re.S).group(1)
        sha=self.git('rev-parse','HEAD')
        predicate=(SOURCE/'reference/in-repo-writes.md').read_text()
        predicate=re.search(r'<!-- BEGIN IN-REPO-WRITES PREDICATE -->.*?<!-- END IN-REPO-WRITES PREDICATE \(\d+ payload lines\) -->',predicate,re.S).group()
        quoted=f'Historical verdict: {{HEAD_SHA}} TODO TBD\n## Diff\nReview base: {sha}  Head: {sha}\nConvention base: {sha}\n'
        slots=dict(ISSUE_GOAL_STATEMENT='Produce evidence.',ISSUE_BOUNDS='One task.',
            ISSUE_DONE_CHECK='Output captured.',ARCHITECTURE_LEVEL_FLAG='NO',
            COMPLETE_PR_DESCRIPTION=quoted,REVIEW_BASE_SHA=sha,HEAD_SHA=sha,
            CONVENTION_BASE_SHA=sha,ACCEPTED_SPEC_BLOB_SHA='NONE',
            CI_CONFIGURATION_PATHS='NONE',
            CI_FALLBACK_COMMENT_OR_NONE='NONE',IN_REPO_WRITES_PREDICATE=predicate,
            REVIEWER_IDENTITY='{REVIEWER_IDENTITY}')
        packet=self.root/'structured.json'
        packet.write_text(json.dumps(dict(format='devstandard-review-packet-v1',template=template,slots=slots)))
        review=self.call('--purpose','reviewer','--packet',str(packet))
        prompt=self.brief(review)
        self.assertIn(quoted,prompt)
        self.assertIn('Reviewer: dsh subagent, deepseek-v4.1-flash at max, read-only — reviewed',prompt)
        spawn=self.instruction(review)
        self.assertLess(len(spawn['prompt']),1000)
        self.assertIn(review['brief'],spawn['prompt'])
        self.assertIn('IN FULL',spawn['prompt'])
        slots['HEAD_SHA']='{HEAD_SHA}'
        packet.write_text(json.dumps(dict(format='devstandard-review-packet-v1',template=template,slots=slots)))
        # #434: the assembler reports an unpinned slot; the dispatcher still cannot capture
        # pinned evidence without it, so commissioning a reviewer on one refuses here.
        self.assertIn('head must be a full SHA',self.call('--purpose','reviewer',
            '--packet',str(packet),ok=False))

    def test_reviewer_refuses_failed_git_evidence_before_writes(self):
        run=self.start()
        packet=self.review_packet(identity='dsh subagent, deepseek-v4.1-flash at max, read-only')
        real_git=shutil.which('git')
        self.tool('git',f'''import os,sys
if '--stat' in sys.argv:
 print('fixture diff failure',file=sys.stderr);sys.exit(1)
os.execv({real_git!r},[{real_git!r},*sys.argv[1:]])
''')
        before=self.comments.read_text();files=set(self.root.iterdir())
        error=self.call('--purpose','reviewer','--packet',str(packet),ok=False)
        self.assertIn('fixture diff failure',error)
        self.assertEqual(self.comments.read_text(),before)
        self.assertEqual(set(self.root.iterdir()),files)

    def test_reviewer_refuses_unpinned_or_unreachable_evidence_before_writes(self):
        run=self.start()
        good=self.review_packet(identity='dsh subagent, deepseek-v4.1-flash at max, read-only').read_text()
        sha=self.git('rev-parse','origin/main')
        packet=self.root/'review.txt'
        for bad in ('Incomplete packet.',good.replace(sha,'origin/main'),good.replace(sha,'f'*40)):
            with self.subTest(packet=bad):
                packet.write_text(bad)
                before=self.comments.read_text();files=set(self.root.iterdir())
                self.call('--purpose','reviewer','--packet',str(packet),ok=False)
                self.assertEqual(self.comments.read_text(),before)
                self.assertEqual(set(self.root.iterdir()),files)

    def test_a_second_delegation_never_blocks_and_cleanup_still_works(self):
        """A child's handle is the caller's own and nothing here observes it, so a fresh
        delegation and cleanup are never blocked by a recorded run (#427)."""
        first=self.start()
        packet=self.review_packet(identity='dsh subagent, deepseek-v4.1-flash at max, read-only')
        options=('--purpose','reviewer','--packet',str(packet))
        second=self.call(*options)
        self.assertNotEqual(first['instruction'],second['instruction'])
        self.assertEqual(second['status'],'awaiting-delegation')
        self.assertIn('record the returned child id', first['notice'])
        cleanup=self.call('--cleanup','--discard')
        self.assertEqual(cleanup['status'],'cleaned')

    def test_cleanup_from_inside_the_lane_worktree_refuses(self):
        """#427 kept this refusal: `worktree remove` cannot run from the tree it removes."""
        run=self.start()
        inside=subprocess.run([sys.executable,str(self.script),'12','--cleanup','--discard',
                               '--project',run['worktree']],env=self.env,text=True,capture_output=True)
        self.assertNotEqual(inside.returncode,0)
        self.assertIn('run cleanup from outside the lane worktree',inside.stderr)
        self.assertTrue(Path(run['worktree']).exists())
        self.assertIn(run['branch'],self.git('branch','--list'))

    def test_cleanup_refuses_a_checkout_inside_a_differently_spelled_lane(self):
        """#449: the containment half of that guard compared text, so a lane record carrying
        another spelling of the same directory — a symlinked route here, a differently-cased one
        on macOS (#443) — hid a checkout that `git worktree remove` was about to take with it.
        The dispatcher resolves `--project` itself, so the recorded spelling is the one that
        can still differ, and identity is what both halves of the guard now compare."""
        run=self.start()
        wt=Path(run['worktree']);inner=wt/'inner'
        self.git('worktree','add','-b','inner',str(inner),'origin/main')
        link=self.root/'lane-link';link.symlink_to(wt)
        rows=json.loads(self.comments.read_text())
        for row in rows:
            if '"kind": "lane"' in row['body']: row['body']=row['body'].replace(str(wt),str(link))
        self.comments.write_text(json.dumps(rows))
        recorded=Path(self.lane_records()[0]['worktree'])
        self.assertFalse(inner.is_relative_to(recorded));self.assertTrue(recorded.samefile(wt))
        outside=subprocess.run([sys.executable,str(self.script),'12','--cleanup','--discard',
                                '--project',str(inner)],env=self.env,text=True,capture_output=True)
        self.assertNotEqual(outside.returncode,0)
        self.assertIn('run cleanup from outside the lane worktree',outside.stderr)
        self.assertTrue(inner.exists());self.assertTrue(wt.exists())
        self.assertIn(run['branch'],self.git('branch','--list'))

    def test_cleanup_requires_merge_and_preserves_dirty_work(self):
        run=self.start()
        pr=dict(number=13,url='https://github.com/o/r/pull/13',state='OPEN',mergedAt=None,baseRefName='main', headRefName=run['branch'],headRefOid=self.git('rev-parse',run['branch']))
        (self.root/'pr.json').write_text(json.dumps(pr))
        self.assertIn('merged',self.call('--cleanup','--pr','13',ok=False))
        pr.update(state='MERGED',mergedAt='2026-01-01T00:00:00Z');(self.root/'pr.json').write_text(json.dumps(pr))
        stray=Path(run['worktree'])/'stray';stray.write_text('keep')
        self.assertIn('dirty',self.call('--cleanup','--pr','13',ok=False));self.assertTrue(stray.exists())
        stray.unlink()
        self.call('--cleanup','--pr','13')
        self.assertFalse(Path(run['worktree']).exists())
        self.assertNotIn(run['branch'],self.git('branch','--list'))

    def test_cleanup_after_worker_commits_and_real_git_squash_merge(self):
        """#427: a squash merge always leaves the lane head off main, so the old -D authorization
        was always required and stopped nothing. The checks that can actually lose work run first."""
        run=self.start()
        wt=Path(run['worktree'])
        for n in range(2):
            (wt/'result.txt').write_text('worker result '+str(n))
            self.git('-C',str(wt),'add','result.txt')
            self.git('-C',str(wt),'commit','-m','worker step '+str(n))
        self.assertEqual(self.git('rev-list','--count','origin/main..'+run['branch']),'2')
        head=self.git('rev-parse',run['branch'])
        self.git('merge','--squash',run['branch']);self.git('commit','-m','squash worker PR')
        self.git('update-ref','refs/remotes/origin/main','HEAD')
        self.assertNotEqual(head,self.git('rev-parse','origin/main'))
        self.assertEqual(self.git('diff','origin/main',run['branch']),'')
        # The lane head is not an ancestor of the integrated base: plain `git branch -d` refuses.
        self.assertNotEqual(subprocess.run(['git','-C',str(self.project),'merge-base','--is-ancestor',
                                            head,'origin/main'],capture_output=True).returncode,0)
        pr=dict(number=13,url='https://github.com/o/r/pull/13',state='MERGED',mergedAt='2026-01-01T00:00:00Z',baseRefName='main', headRefName=run['branch'],headRefOid=head)
        (self.root/'pr.json').write_text(json.dumps(pr))
        # The kept protections still fire, and each of them preserves the lane.
        stray=Path(run['worktree'])/'stray';stray.write_text('keep')
        self.assertIn('dirty',self.call('--cleanup','--pr','13',ok=False))
        stray.unlink()
        self.git('-C',run['worktree'],'commit','--allow-empty','-m','unpublished work')
        self.assertIn('unpublished work',self.call('--cleanup','--pr','13',ok=False))
        self.assertTrue(Path(run['worktree']).exists())
        self.git('-C',run['worktree'],'reset','--hard',head)
        # With them passed, cleanup needs no flag and still prints the inventory it printed before.
        result=subprocess.run([sys.executable,str(self.script),'12','--cleanup','--pr','13',
                               '--project',str(self.project)],env=self.env,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('worker step 0',result.stderr);self.assertIn('worker step 1',result.stderr)
        cleanup=json.loads(result.stdout)
        self.assertEqual(cleanup['status'],'cleaned')
        self.assertFalse(Path(run['worktree']).exists())
        self.assertEqual(self.git('branch','--list',run['branch']),'')
        self.assertEqual(self.git('worktree','list','--porcelain').count('worktree '),1)
        self.assertEqual(self.lane_records()[-1],cleanup)


if __name__ == '__main__':
    unittest.main()
