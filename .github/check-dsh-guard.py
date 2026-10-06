#!/usr/bin/env python3
"""Pin the dsh guard's ported engine to `scripts/hard_edges.py`'s policy (issue #8).

The guard rides dsh's `tools/pre-execute` from a Node plugin, so the word engine that the
Claude Code carrier keeps in Python is ported into `guard.js`. A port is a second copy, and
a second copy drifts. This gate is what stops it: it runs the same corpus of commands
through the Python engine (`scripts/hard_edges.py`) and through the ported JS engine
(`guard.js`), and fails on the first decision they do not agree on.

`guard.js` is the one operative policy for the dsh carrier and `hard_edges.py` for the
Claude carrier; both must decide every command identically, down to the refusal's exact
wording, because a refusal is the reminder text the harness feeds back to the model. The
corpus below pairs each surviving word with the benign command it must not refuse, the
boundary cases the whole-word rule turns on, and the here-document and quoted-string
positions `command_only` removes (#351, ADR 0062).

The `child` role has no Python counterpart: it is the worker-and-reviewer union the JS
listener falls back to for a child it cannot map to a row, so its expectation is computed
here as the Python worker rule or else the reviewer rule.

Needs `node` (the bundle is a Node package). It is deliberately independent of `dsh`: the
bundled plugin is imported directly, so nothing here composes a profile or starts a harness.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True  # importing the engine must not litter scripts/__pycache__
sys.path.insert(0, str(ROOT / "scripts"))

from hard_edges import command_refusal  # noqa: E402 -- resolved from the bundle's own scripts/

ROLES = ("worker", "reviewer", "orchestrator", "child")

# Commands whose decision this gate pins. Each (command) is run for every role above, so one
# entry covers four decisions; the role-specific refusals (a worker's `merge`, the
# orchestrator's `gh pr merge`, a reviewer's write flags, the worker default-branch `push`)
# all appear, and so does ordinary work each role must be allowed.
COMMANDS = [
    # The three cleared words plus the worker's stopgap push rule.
    "git merge feature",
    "gh pr merge 12",
    "gh pr merge --admin",
    "gh api -X POST /repos/o/r/issues/1/comments -f body=x",
    "git push origin main",
    "git push origin master",
    # Boundary cases the whole-word rule turns on: none of these is the act.
    "git merge-base main HEAD",
    "git log --merged",
    "echo merged mergeable",
    "git merge-base --is-ancestor a b",
    "task/mainline",
    "mainline",
    "domain",
    "x-merge y",
    "merge-x",
    # The benign commands each struck-out word once refused (#425): a word that comes back
    # brings its false refusal back with it.
    "cargo build --release",
    "git tag v1",
    "rm -rf node_modules",
    "git push --tags",
    "git branch -D task/x",
    "git worktree remove ../lane",
    # The data a command carries is removed, not judged (#351).
    "git commit -m \"please merge this\"",
    "gh issue create --body 'gh pr merge'",
    "echo 'git merge x'",
    "echo \"push origin main\"",
    "cat <<EOF\ngit merge x\nEOF",
    "cat <<-EOF\n\tgit push origin main\n\tEOF",
    # A substitution body is command text and is still read.
    "echo $(git merge x)",
    "echo `git merge x`",
    # `-XPOST` is one flag; `-XPOST`-like words that are not flags stay admitted.
    "gh api -XPOST /x",
    "gh api --method POST /x",
    "gh api --input body.json",
    "gh api --method=POST /x",
    # A worker keeps the GitHub writes the reviewer's flag rule names; the mapping must not
    # collapse to the union. For a worker this is admitted, for a reviewer refused.
    "echo gh -X POST",
    "echo merge",
    # Ordinary work every role must be allowed.
    "echo hello",
    "git status --porcelain -uall",
    "ls -la",
    "python3 -m pytest",
    "   ",
]


def python_refusal(role: str, command: str) -> str | None:
    """The policy's decision for one call, with the union role spelled out for `child`."""
    if role == "child":
        return command_refusal("worker", command) or command_refusal("reviewer", command)
    return command_refusal(role, command)


def js_decisions(node: str, cases: list[dict]) -> list[str | None]:
    """Every decision `guard.js` makes for the corpus, in order, through a real Node import."""
    guard = json.dumps(str(ROOT / "guard.js"))
    program = (
        f"import {{ decide }} from {guard};\n"
        "import { readFileSync } from 'node:fs';\n"
        "const cases = JSON.parse(readFileSync(process.argv[1], 'utf8'));\n"
        "process.stdout.write(JSON.stringify("
        "cases.map((c) => decide(c.role, c.tool, c.arguments) ?? null)));\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(cases, handle)
        corpus_path = handle.name
    try:
        result = subprocess.run([node, "--input-type=module", "-e", program, corpus_path],
                                capture_output=True, text=True)
    finally:
        Path(corpus_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise AssertionError(f"node could not import guard.js: {result.stderr.strip()[-800:]}")
    return json.loads(result.stdout)


def check(node: str) -> None:
    cases = [{"role": role, "tool": "bash", "arguments": {"command": command}}
             for command in COMMANDS for role in ROLES]
    got = js_decisions(node, cases)
    require(len(got) == len(cases), "guard.js returned a decision per call")
    mismatches = []
    for (case, decision) in zip(cases, got):
        expected = python_refusal(case["role"], case["arguments"]["command"])
        if (expected or None) != (decision or None):
            mismatches.append((case["role"], case["arguments"]["command"], expected, decision))
    require(not mismatches, "guard.js disagrees with scripts/hard_edges.py:\n"
            + "\n".join(f"  {role}: {command!r}\n    python: {py!r}\n    js:     {js!r}"
                        for role, command, py, js in mismatches))
    print(f"guard.js agrees with scripts/hard_edges.py on all {len(cases)} decisions "
          f"({len(COMMANDS)} commands x {len(ROLES)} roles)")

    # The two things only the carrier changes: the shell tool is `bash`, and every non-shell
    # tool is admitted for every role (#334). A wrong tool name would silently guard nothing.
    for role in ROLES:
        require(decide_is_none(node, role, "read", {"file_path": "/x"}),
                f"{role}: a non-shell tool call must be admitted")
        require(decide_is_none(node, role, "bash", {}),
                f"{role}: a `bash` call with no command string must be admitted")
    require(any(not decide_is_none(node, role, "bash", {"command": "git merge x"})
                for role in ("worker",)),
            "the shell tool `bash` must still reach the word engine")
    print("tool gating: only `bash` with a command string reaches the word engine")

    print("RESULT: the dsh guard's ported engine matches the policy it was ported from")


def decide_is_none(node: str, role: str, tool: str, arguments: dict) -> bool:
    """Whether `guard.js` admits one call (its decision is `null`)."""
    return js_decisions(node, [{"role": role, "tool": tool, "arguments": arguments}]) == [None]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default=shutil.which("node"), help="the node executable (default: PATH)")
    args = parser.parse_args()
    require(args.node, "node was not found on PATH; pass --node")
    check(args.node)


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"\nFAILED: {error}", file=sys.stderr)
        sys.exit(1)
