#!/usr/bin/env python3
"""Validate the DevStandard dsh bundle and prove its role delivery end to end.

Issue #6's done-check, in two parts:

  1. Static validation. `.github/check-dsh-bundle.py` runs as the bundle gate
     (row shape, the single model anchor, and the byte-identity of each embedded
     persona); here we add that every row's package name resolves from the dsh
     installation, the composed profile, or the bundle itself.

  2. A live run. A throwaway `$DSH_HOME` gets a `headless`-derived profile with
     the bundle composed in; a local deterministic OpenAI-compatible endpoint
     scripts the root to call the `worker` tool and then the `reviewer` tool;
     `dsh --profile <p> --json <task>` runs. The assertions are:

     - the root's request carries `reference/orchestrator.md`'s exact bytes, and
       no child's does (probe 2 item 1, from issue #4);
     - the worker child's request carries `reference/worker.md`'s exact bytes and
       not the reviewer's;
     - the reviewer child's request carries `reference/code-review-prompt.md`'s
       exact bytes, its tool catalog holds no write tool, and a write call the
       endpoint scripts is rejected;
     - both children's requests carry the bundle's one model anchor;
     - the guard refuses each role's own word through `tools/pre-execute`, names
       the role and the word in the reminder, and admits an ordinary command --
       the root's `gh pr merge`, the worker's `merge` and default-branch `push`,
       the reviewer's `gh api` write flag (issue #8);
     - a child maps to its own role, not the worker-and-reviewer union: a worker's
       `echo gh -X POST` is admitted and a reviewer's `echo merge` is admitted.

Probe 2 item 2 (issue #6): `subagent/start` carries the child id but not the row's
persona or label, so it cannot map a child to its role; the child's own durable
`subagent/descriptor` does carry the row's `persona`, so (2) resolves the role from
that and the guard uses the exact per-role rules, not the union fallback.

Requires `dsh` on PATH, Node and pnpm (the dsh plugin manager shells out to
pnpm). No network: the endpoint is local and the profile links the bundle.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True  # importing the engine must not litter scripts/__pycache__
sys.path.insert(0, str(ROOT / "scripts"))
from hard_edges import command_refusal  # noqa: E402 -- the policy the dsh guard ports

ORCHESTRATOR = ROOT / "reference" / "orchestrator.md"
WORKER_PAGE = ROOT / "reference" / "worker.md"
REVIEWER_PAGE = ROOT / "reference" / "code-review-prompt.md"
GATE = ROOT / ".github" / "check-dsh-bundle.py"

# A marker the endpoint plants in each child's task; a request whose *user* message
# carries one is that child's request, whatever the child inherited. The root's own
# requests carry the marker only inside tool-call arguments, never in a user message.
WORKER_MARKER = "DEVSTANDARD-WORKER-TASK-5c1f9a"
REVIEWER_MARKER = "DEVSTANDARD-REVIEWER-TASK-7d2e4b"
TASK = "Delegate a short task to the worker, then to the reviewer, then answer."
WRITE_TOOLS = {"write", "edit", "str_replace_editor"}

# Ordinary commands the endpoint scripts each agent to run; their stdout proves the guard
# admitted them. The two `echo gh -X POST` / `echo merge` commands are the split proof: the
# reviewer's flag rule and the worker's word rule would each refuse them under the union, so
# admitting them shows the child took its own role and not the fallback.
ROOT_OK = "DEVSTANDARD-ROOT-OK-9a1c"
WORKER_OK = "DEVSTANDARD-WORKER-OK-4f2d"
REVIEWER_OK = "DEVSTANDARD-REVIEWER-OK-7b3e"
ROOT_ALLOWED = f"echo {ROOT_OK}"
WORKER_ALLOWED = f"echo {WORKER_OK}"
REVIEWER_ALLOWED = f"echo {REVIEWER_OK}"
WORKER_WORD = "git merge upstream"
WORKER_PUSH = "git push origin main"
REVIEWER_WRITE = "gh api -X POST /repos/o/r/issues/1/comments -f body=x"
ROOT_WORD = "gh pr merge 12"
WORKER_SPLIT_PROOF = f"echo gh -X POST {WORKER_OK}"
REVIEWER_SPLIT_PROOF = f"echo merge {REVIEWER_OK}"


def run(cmd, *, env=None, cwd=None, timeout=180, capture=True):
    """Run one command, echoing it as evidence, and return (code, stdout, stderr)."""
    print(f"$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        [str(c) for c in cmd], env=env, cwd=cwd, timeout=timeout,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None, text=True,
    )
    if capture:
        print(f"  exit {result.returncode}")
        if result.stderr.strip():
            print("  stderr:", result.stderr.strip()[-2000:])
    return result.returncode, result.stdout or "", result.stderr or ""


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def anchor_options():
    """The port's one model anchor, read from the bundle's own `cordis.patch.yml`."""
    rows = yaml.safe_load((ROOT / "cordis.patch.yml").read_text())
    options = [
        entry.get("config", {}).get("agentOptions")
        for row in rows for entry in row.get("insert", [])
        if entry.get("config", {}).get("agentOptions") is not None
    ]
    require(options, "cordis.patch.yml states no agentOptions anchor")
    require(len({json.dumps(o, sort_keys=True) for o in options}) == 1,
            f"cordis.patch.yml states more than one agentOptions: {options}")
    return options[0]


# --------------------------------------------------------------------------- #
# Part 1: static validation


def dsh_package_dir(dsh_bin):
    """The installed `@deepseek-ai/dsh` package directory, found beside the binary."""
    cursor = Path(dsh_bin).resolve()
    for parent in [cursor, *cursor.parents]:
        manifest = parent / "package.json"
        if manifest.exists():
            try:
                if json.loads(manifest.read_text()).get("name") == "@deepseek-ai/dsh":
                    return parent
            except json.JSONDecodeError:
                pass
    return None


def resolve_package(name, anchors):
    """Resolve a package name, or `name/subpath`, to a directory under one anchor's node_modules.

    An anchor that is itself the named package counts too, so a bundle's own row
    resolves before the bundle is composed into a profile.
    """
    parts = name.split("/")
    package = "/".join(parts[:2]) if name.startswith("@") else parts[0]
    for anchor in anchors:
        if anchor is None:
            continue
        anchor = Path(anchor)
        manifest = anchor / "package.json"
        if manifest.exists():
            try:
                if json.loads(manifest.read_text()).get("name") == package:
                    return anchor
            except json.JSONDecodeError:
                pass
        candidate = anchor / "node_modules" / package
        if (candidate / "package.json").exists():
            return candidate
    return None


def validate(repo, profile_dir, dsh_bin):
    print("== static validation ==")
    # The bundle gate owns row shape, the one model anchor, and the generated
    # personas; running it here keeps the evidence script's preflight in one place.
    code, _, err = run([sys.executable, repo / ".github" / "check-dsh-bundle.py"])
    require(code == 0, f"the bundle gate failed: {err[-800:]}")

    # The guard gate owns the port fidelity — `guard.js` against `scripts/hard_edges.py`
    # — so the live refusals below rest on an engine that cannot have drifted.
    code, _, err = run([sys.executable, repo / ".github" / "check-dsh-guard.py"])
    require(code == 0, f"the guard gate failed: {err[-800:]}")

    # Resolution is the one static claim the gate cannot make: it needs the dsh
    # installation and (in a composed profile) the profile's own node_modules.
    rows = yaml.safe_load((repo / "cordis.patch.yml").read_text())
    anchors = [repo, profile_dir, dsh_package_dir(dsh_bin)]
    declared = 0
    for row in rows:
        require(isinstance(row, dict), f"patch row is not a mapping: {row!r}")
        entries = row.get("insert", [])
        require(isinstance(entries, list), "patch row `insert` must be a list")
        for entry in entries:
            require(isinstance(entry, dict), f"inserted entry is not a mapping: {entry!r}")
            name = entry.get("name")
            require(isinstance(name, str) and name, "inserted entry needs a string name")
            resolved = resolve_package(name, anchors)
            require(resolved is not None, f"inserted entry names an unresolvable package: {name}")
            declared += 1
            print(f"  row {entry['id']} -> {name} resolves to {resolved}")
    require(declared, "cordis.patch.yml inserts no plugin rows")
    print("  cordis.patch.yml: every row names a resolvable package")


# --------------------------------------------------------------------------- #
# Part 2: the live run


class FakeOpenAI:
    """A deterministic OpenAI-compatible endpoint that scripts the worker and reviewer calls."""

    def __init__(self):
        self.requests = []
        self.calls = 0
        # A continuable child runs detached, so the root's final step waits on these before
        # it answers: otherwise the turn ends and the harness tears the children down.
        self.worker_done = threading.Event()
        self.reviewer_done = threading.Event()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}/v1"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            # SSE has no length; close-delimited HTTP/1.0 bodies are what the OpenAI
            # SDK's streaming parser terminates on after `data: [DONE]`.
            protocol_version = "HTTP/1.0"

            def log_message(self, *args):
                pass

            def _json(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.endswith("/models"):
                    self._json({"object": "list", "data": [{"id": "probe-model", "object": "model"}]})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                length = int(self.headers.get("content-length", "0"))
                try:
                    body = json.loads(self.rfile.read(length))
                except json.JSONDecodeError:
                    body = {}
                outer.requests.append(body)
                messages = body.get("messages") or []
                tools = body.get("tools") or []
                tool_roles = [m for m in messages if m.get("role") == "tool"]

                def user_marker(marker):
                    for message in messages:
                        if message.get("role") == "user" and marker in json.dumps(message.get("content")):
                            return True
                    return False

                # `n` is the number of tool results already in this agent's history: the step
                # each agent is on. The sequences below script the root, the worker child and
                # the reviewer child, one tool call per step, ending in a final text.
                n = len(tool_roles)
                if not tools:
                    return self._text("probe title")
                if user_marker(WORKER_MARKER):
                    if n == 0:
                        return self._bash(WORKER_WORD)
                    if n == 1:
                        return self._bash(WORKER_PUSH)
                    if n == 2:
                        return self._bash(WORKER_SPLIT_PROOF)
                    if n == 3:
                        return self._bash(WORKER_ALLOWED)
                    outer.worker_done.set()
                    return self._text("worker-final")
                if user_marker(REVIEWER_MARKER):
                    if n == 0:
                        return self._bash(REVIEWER_WRITE)
                    if n == 1:
                        return self._bash(REVIEWER_SPLIT_PROOF)
                    if n == 2:
                        return self._bash(REVIEWER_ALLOWED)
                    if n == 3:
                        # Call a tool the reviewer row's filter removed; the harness must reject it.
                        return self._tool_call("write", json.dumps({"file_path": "/tmp/probe", "content": "x"}))
                    outer.reviewer_done.set()
                    return self._text("reviewer-final")
                if n == 0:
                    return self._bash(ROOT_WORD)
                if n == 1:
                    return self._bash(ROOT_ALLOWED)
                if n == 2:
                    return self._tool_call("worker", json.dumps({
                        "description": "spawn the worker",
                        "prompt": f"do the worker task {WORKER_MARKER}",
                        "run_in_background": True,
                    }))
                if n == 3:
                    return self._tool_call("reviewer", json.dumps({
                        "description": "spawn the reviewer",
                        "prompt": f"do the reviewer task {REVIEWER_MARKER}",
                        "run_in_background": True,
                    }))
                # Both children were delegated continuable, so they run detached. Hold the
                # root's last step until each has reached its final text; a child that stalls
                # fails the run below rather than silently vanishing with the root's turn.
                if not outer.worker_done.wait(120):
                    print("  WARNING: the worker child did not finish before the root's last step")
                if not outer.reviewer_done.wait(120):
                    print("  WARNING: the reviewer child did not finish before the root's last step")
                return self._text("root-final")

            def _bash(self, command):
                # dsh's `bash` schema requires a `description` as well as `command`; the guard
                # reads only `exec.arguments.command`, so the description is inert here.
                return self._tool_call("bash", json.dumps(
                    {"command": command, "description": "Probe one command for the role guard"}))

            def _start(self):
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.send_header("cache-control", "no-cache")
                self.send_header("connection", "close")
                self.end_headers()

            def _chunk(self, delta, finish=None):
                payload = {
                    "id": "chatcmpl-devstandard-probe",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": "probe-model",
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
                }
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
                self.wfile.flush()

            def _text(self, text):
                self._start()
                self._chunk({"role": "assistant", "content": text})
                self._chunk({}, "stop")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

            def _tool_call(self, name, arguments):
                # One id per emitted call: the same tool is scripted several times per agent
                # (the guard's refused and allowed `bash` calls), and a repeated id would let
                # the harness mis-resolve the second call against the first.
                outer.calls += 1
                call_id = f"call_probe_{outer.calls}_{name}"
                self._start()
                self._chunk({"role": "assistant", "tool_calls": [
                    {"index": 0, "id": call_id, "type": "function",
                     "function": {"name": name, "arguments": ""}}]})
                self._chunk({"tool_calls": [{"index": 0, "function": {"arguments": arguments}}]})
                self._chunk({}, "tool_calls")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        return Handler


def prompt_text(request):
    """Every system-prompt section in a request.

    dsh's adapter carries the composed system prompt as a `developer` message on a child and as a
    `system` message on the root, so both roles are read; either alone would miss half the claim.
    """
    parts = []
    for message in request.get("messages") or []:
        if message.get("role") in ("system", "developer"):
            content = message.get("content")
            parts.append(content if isinstance(content, str) else json.dumps(content))
    return "\n".join(parts)


def tool_names(request):
    names = set()
    for tool in request.get("tools") or []:
        function = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(function, dict) and function.get("name"):
            names.add(function["name"])
    return names


def is_child(request, marker):
    for message in request.get("messages") or []:
        if message.get("role") == "user" and marker in json.dumps(message.get("content")):
            return True
    return False


def message_text(content):
    """The plain text of one message's content, whether a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") if isinstance(block, dict) else str(block)
                         for block in content)
    return json.dumps(content)


def tool_texts(requests, indices):
    """Every tool-result text an agent's own requests carry, in order — what the model read back."""
    out = []
    for i in indices:
        for message in requests[i].get("messages") or []:
            if message.get("role") == "tool":
                out.append(message_text(message.get("content")))
    return out


def probe(repo, dsh_bin, keep):
    scratch = Path(tempfile.mkdtemp(prefix="devstandard-dsh-probe-"))
    home = scratch / ".dsh"
    profile = "devstandard-probe"
    env = {**os.environ, "DSH_HOME": str(home), "PROBE_KEY": "devstandard-local-fixture"}
    env["DSH_PERMISSION_MODE"] = "danger-full-access"  # no approval channel in a one-shot run
    model = anchor_options()["model"]
    print(f"== live run (scratch {scratch}) ==")
    try:
        code, _, err = run([dsh_bin, profile, "--from-default-profile", "headless", "--dump-config"],
                           env=env)
        require(code == 0, f"profile init failed: {err[-800:]}")

        code, _, err = run([dsh_bin, "plugin", "--profile", profile, "add", str(repo)], env=env)
        require(code == 0, f"composing the bundle failed: {err[-800:]}")

        with FakeOpenAI() as endpoint:
            patch = scratch / "llm.yml"
            # The root runs on `probe-model`; the bundle's anchor must also be a
            # registered route so the children's `agentOptions.model` resolves.
            patch.write_text(
                "- id: llm-pi-ai\n"
                "  config:\n"
                "    providers:\n"
                "      probe-local:\n"
                "        api: openai-completions\n"
                f"        baseURL: {endpoint.base_url}\n"
                "        apiKeyEnv: PROBE_KEY\n"
                "        models:\n"
                "          - id: probe-model\n"
                "            contextWindow: 131072\n"
                "            maxTokens: 4096\n"
                f"          - id: {model}\n"
                "            contextWindow: 131072\n"
                "            maxTokens: 4096\n"
                # The route the bundle anchors on must offer the effort the rows pin.
                "            reasoningEfforts:\n"
                "              max: max\n"
                "- id: agent-default-model\n"
                "  config:\n"
                "    provider: probe-local\n"
                "    model: probe-model\n"
            )
            code, out, err = run([dsh_bin, profile, "--patch", str(patch), "--json", TASK], env=env)
            require(code == 0, f"the dsh run failed: {err[-800:]}")
            print("  run events:")
            events = []
            for line in out.splitlines():
                print("   ", line)
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            requests = list(endpoint.requests)

        return scratch, requests, events
    finally:
        if not keep:
            shutil.rmtree(scratch, ignore_errors=True)


def analyse(requests, events):
    print("== analysis ==")
    orchestrator = ORCHESTRATOR.read_text()
    worker_page = WORKER_PAGE.read_text()
    reviewer_page = REVIEWER_PAGE.read_text()
    anchor = anchor_options()
    anchor_model = anchor["model"]
    anchor_effort = anchor["reasoningEffort"]

    worker_child = [i for i, r in enumerate(requests) if is_child(r, WORKER_MARKER)]
    reviewer_child = [i for i, r in enumerate(requests) if is_child(r, REVIEWER_MARKER)]
    root = [i for i, r in enumerate(requests)
            if not is_child(r, WORKER_MARKER) and not is_child(r, REVIEWER_MARKER) and (r.get("tools") or [])]
    print(f"  captured requests: {len(requests)} (root {len(root)}, worker {len(worker_child)}, "
          f"reviewer {len(reviewer_child)})")
    for i, request in enumerate(requests):
        kind = ("worker" if i in worker_child else "reviewer" if i in reviewer_child
                else "root" if i in root else "title")
        print(f"  req{i}: kind={kind} model={request.get('model')!r} "
              f"tools={sorted(tool_names(request))}")
    require(worker_child, "no worker-child request was captured")
    require(reviewer_child, "no reviewer-child request was captured")
    require(root, "no root request was captured")

    # Role delivery: the root alone carries the orchestrator page.
    carrying = [i for i in root if orchestrator in prompt_text(requests[i])]
    require(carrying, "the root request does not carry reference/orchestrator.md's bytes")
    print(f"  OK: root request(s) {carrying} carry {ORCHESTRATOR.name}'s bytes")

    # Each child carries its own role page, and only its own.
    for name, indices, page, page_label, other, other_label in (
        ("worker", worker_child, worker_page, "worker.md", reviewer_page, "code-review-prompt.md"),
        ("reviewer", reviewer_child, reviewer_page, "code-review-prompt.md", worker_page, "worker.md"),
    ):
        for i in indices:
            text = prompt_text(requests[i])
            require(page in text, f"the {name} child request does not carry {page_label}'s exact bytes")
            require(other not in text, f"the {name} child request also carries {other_label}")
            require(orchestrator not in text, f"the {name} child request carries the orchestrator page")
        print(f"  OK: {name} child request(s) {indices} carry {page_label} alone, never the orchestrator")

    # The root can call both role tools.
    root_tools = set().union(*(tool_names(requests[i]) for i in root))
    require({"worker", "reviewer"} <= root_tools, f"the root cannot call both tools: {sorted(root_tools)}")
    print("  OK: the root's tool catalog holds both `worker` and `reviewer`")

    # The reviewer is denied the write tools the worker keeps.
    reviewer_tools = set().union(*(tool_names(requests[i]) for i in reviewer_child))
    worker_tools = set().union(*(tool_names(requests[i]) for i in worker_child))
    held = reviewer_tools & WRITE_TOOLS
    require(not held, f"the reviewer child holds write tool(s) {sorted(held)}")
    require({"write", "edit"} <= worker_tools,
            f"the worker child does not hold the write tools, so the filter proves nothing: {sorted(worker_tools)}")
    print(f"  OK: the reviewer catalog drops {sorted(WRITE_TOOLS & worker_tools)}; the worker keeps them")

    # Both children run on the bundle's one anchor, at the anchored effort.
    for name, indices in (("worker", worker_child), ("reviewer", reviewer_child)):
        for i in indices:
            require(requests[i].get("model") == anchor_model,
                    f"the {name} child ran on {requests[i].get('model')!r}, not the anchor {anchor_model!r}")
            require(requests[i].get("reasoning_effort") == anchor_effort,
                    f"the {name} child ran at {requests[i].get('reasoning_effort')!r}, "
                    f"not {anchor_effort!r}")
    print(f"  OK: both children ran on {anchor_model!r} at reasoning_effort={anchor_effort!r}")

    # Both role calls the root made completed: the root's own event stream proves the
    # tools are callable, independent of what the children's requests show.
    called = {e.get("callId"): e.get("tool") for e in events if e.get("type") == "tool_call"}
    results = {e.get("callId"): e.get("status") for e in events if e.get("type") == "tool_result"}
    for role in ("worker", "reviewer"):
        call_ids = [cid for cid, tool in called.items() if tool == role]
        require(call_ids and all(results.get(cid) == "completed" for cid in call_ids),
                f"the root's {role} call did not complete: {[(cid, results.get(cid)) for cid in call_ids]}")
    print("  OK: the root called both `worker` and `reviewer`, and both calls completed")

    # The write call the endpoint scripted for the reviewer was rejected. The child's
    # rejection is not in the root's event stream, so read it from the reviewer child's
    # own follow-up request: its tool result must report a failure, not a written file. The
    # reviewer's other tool results — the guard refusals and the allowed `echo`s — are set
    # aside by their markers, leaving the `write` outcome.
    write_results = [text for text in tool_texts(requests, reviewer_child)
                     if "role refuses" not in text and REVIEWER_OK not in text]
    require(write_results, "the reviewer's `write` call produced no tool result to inspect")
    require(all("error" in text.lower() or "unknown" in text.lower() or "denied" in text.lower()
                or "not " in text.lower() for text in write_results),
            f"the reviewer's `write` call was not reported as rejected: {write_results}")
    print(f"  OK: the reviewer's `write` call was rejected: {write_results[0][:200]}")

    # The guard (issue #8). Every role is refused its own word through `tools/pre-execute`
    # and admitted an ordinary command; the refusal is the reminder the model reads back,
    # naming the role and the word and offering what the role does instead. The engine that
    # decides is the one `guard.js` ports, so its reminder is the expected text.
    root_texts = "\n".join(tool_texts(requests, root))
    worker_texts = "\n".join(tool_texts(requests, worker_child))
    reviewer_texts = "\n".join(tool_texts(requests, reviewer_child))
    for label, texts, cases, allowed in (
        ("root", root_texts, [("orchestrator", ROOT_WORD)], ROOT_ALLOWED),
        ("worker", worker_texts, [("worker", WORKER_WORD), ("worker", WORKER_PUSH)], WORKER_ALLOWED),
        ("reviewer", reviewer_texts, [("reviewer", REVIEWER_WRITE)], REVIEWER_ALLOWED),
    ):
        for role, command in cases:
            reason = command_refusal(role, command)
            require(reason, f"the {label} case {command!r} states no refusal to expect")
            require(f"Error: {reason}" in texts,
                    f"the {label} was not refused {command!r}; expected its tool result to read "
                    f"{reason!r}")
            print(f"  OK: {label} refused {command!r} with: {reason}")
        require("role refuses a " in texts and "Instead," in texts and "Read " in texts,
                f"the {label} refusal is a wall, not the reminder ADR 0062 prescribes")
        require(allowed.split()[1] in texts,
                f"the {label}'s ordinary command {allowed!r} was not admitted")
        print(f"  OK: {label} was admitted the ordinary command {allowed!r}")

    # The child tier is the exact per-role list, not the worker-and-reviewer union ADR 0062's
    # amendment named as a fallback: each child ran a command the *other* role's rule would
    # refuse, and it was admitted. Probe 2 item 2 (issue #6) removed the need for the union by
    # yielding the child's own row persona (see the mapping note below).
    worker_split = command_refusal("reviewer", WORKER_SPLIT_PROOF)
    reviewer_split = command_refusal("worker", REVIEWER_SPLIT_PROOF)
    require(worker_split and worker_split not in worker_texts,
            "the worker was refused a reviewer-only word: the child tier is the union, not the worker's list")
    require(f"gh -X POST {WORKER_OK}" in worker_texts,
            "the worker's split-proof command did not run, so it does not prove the split")
    require(reviewer_split and reviewer_split not in reviewer_texts,
            "the reviewer was refused a worker-only word: the child tier is the union, not the reviewer's list")
    require(f"merge {REVIEWER_OK}" in reviewer_texts,
            "the reviewer's split-proof command did not run, so it does not prove the split")
    print("  OK: each child carries its own role's list, not the worker-and-reviewer union")

    # How a child maps to its role (done-check 5). `subagent/start`'s payload is
    # {runId, provider, id, local} — the child id, no persona and no label — so it cannot map
    # a child to its row. The child's own durable `subagent/descriptor` does carry the row's
    # `persona`; the command that shows the field is
    #   sed -n '/ContinuableSubagentDescriptorData/,/^}/p' \
    #     "$(dirname "$(dirname "$(readlink -f "$(which dsh)")")")/node_modules/@deepseek-ai/dsh-subagent/lib/types/descriptor.d.ts"
    # and `index.js` matches that persona against reference/worker.md and
    # reference/code-review-prompt.md. The split proof above is that mapping working live.
    print("  Mapping (probe 2 item 2): the child's own `subagent/descriptor` carries the row "
          "`persona`, so the guard takes the exact per-role rules proved above")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsh", default=shutil.which("dsh"), help="the dsh executable (default: PATH)")
    parser.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = parser.parse_args()
    require(args.dsh, "dsh was not found on PATH; pass --dsh")
    for page in (ORCHESTRATOR, WORKER_PAGE, REVIEWER_PAGE):
        require(page.is_file(), f"missing {page}")

    scratch = Path(tempfile.mkdtemp(prefix="devstandard-dsh-validate-"))
    try:
        profile_dir = scratch / ".dsh" / "profiles" / "devstandard-validate"
        validate(ROOT, profile_dir, args.dsh)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    _, requests, events = probe(ROOT, args.dsh, args.keep)
    analyse(requests, events)

    print("\nRESULT: bundle validates; both role tools are callable, each child carries its own "
          "page and the right tool surface, both run on the one anchor, and the guard refuses "
          "each role's own word while admitting ordinary work")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"\nFAILED: {error}", file=sys.stderr)
        sys.exit(1)
