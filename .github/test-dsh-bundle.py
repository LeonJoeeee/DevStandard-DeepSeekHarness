#!/usr/bin/env python3
"""Validate the DevStandard dsh bundle and prove its role delivery end to end.

Issue #4's done-check, in two parts:

  1. Static validation of the bundle. `package.json`'s `dsh.bundle.patch`
     resolves to a real file, its `files` list names only existing paths, and
     every row in `cordis.patch.yml` declares only known patch fields and names
     a package that resolves from the dsh installation or the composed profile.

  2. A live run. A throwaway `$DSH_HOME` gets a `headless`-derived profile with
     the bundle composed in; a local deterministic OpenAI-compatible endpoint
     scripts one subagent spawn; `dsh --profile <p> --json <task>` runs. The
     root agent's request must carry `reference/orchestrator.md`'s exact bytes,
     and the spawned child's request must not.

Probe 2 item 1 is answered by (2): a system-prompt section registered through
the root `agent.ctx` does not reach a spawned child, so no shadowing fallback is
needed.

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

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "reference" / "orchestrator.md"

# A marker the endpoint plants in the child's task; any request whose user
# message carries it is a child request, whatever the child inherited.
CHILD_MARKER = "DEVSTANDARD-CHILD-TASK-5c1f9a"
TASK = "Delegate a short task to a subagent, then answer."

# Every field a `cordis.patch.yml` entry may declare (the loader's entry
# metadata plus the patch-only `insert`).
PATCH_FIELDS = {"id", "name", "config", "group", "disabled", "inject", "intercept", "isolate", "insert"}
ENTRY_FIELDS = {"id", "name", "config", "group", "disabled", "inject", "intercept", "isolate"}


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


# --------------------------------------------------------------------------- #
# Part 1: static bundle validation


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
    manifest = json.loads((repo / "package.json").read_text())
    bundle = manifest.get("dsh", {}).get("bundle", {})
    patch = bundle.get("patch")
    require(patch is not None, "package.json declares no dsh.bundle.patch")
    patch_files = [patch] if isinstance(patch, str) else patch
    require(isinstance(patch_files, list) and patch_files, "dsh.bundle.patch must be a path or a list of paths")
    for rel in patch_files:
        require((repo / rel).is_file(), f"dsh.bundle.patch names a missing file: {rel}")
    print(f"  dsh.bundle.patch -> {', '.join(patch_files)} (all exist)")

    missing = [rel for rel in manifest.get("files", []) if not (repo / rel.rstrip("/")).exists()]
    require(not missing, f"package.json files names missing paths: {missing}")
    print(f"  files -> {len(manifest.get('files', []))} entries, all exist")

    raw = (repo / patch_files[0]).read_text()
    try:
        import yaml
    except ImportError:  # pragma: no cover - the suite already requires PyYAML
        raise AssertionError("PyYAML is required for the bundle validation")
    rows = yaml.safe_load(raw)
    require(isinstance(rows, list) and rows, "cordis.patch.yml must be a non-empty list")

    anchors = [repo, profile_dir, dsh_package_dir(dsh_bin)]
    declared = 0
    for row in rows:
        require(isinstance(row, dict), f"patch row is not a mapping: {row!r}")
        unknown = set(row) - PATCH_FIELDS
        require(not unknown, f"patch row declares unknown field(s): {sorted(unknown)}")
        entries = row.get("insert", [])
        require(isinstance(entries, list), "patch row `insert` must be a list")
        for entry in entries:
            require(isinstance(entry, dict), f"inserted entry is not a mapping: {entry!r}")
            unknown = set(entry) - ENTRY_FIELDS
            require(not unknown, f"inserted entry declares unknown field(s): {sorted(unknown)}")
            require(isinstance(entry.get("id"), str) and entry["id"], "inserted entry needs a string id")
            name = entry.get("name")
            require(isinstance(name, str) and name, "inserted entry needs a string name")
            resolved = resolve_package(name, anchors)
            require(resolved is not None, f"inserted entry names an unresolvable package: {name}")
            declared += 1
            print(f"  row {entry['id']} -> {name} resolves to {resolved}")
    require(declared, "cordis.patch.yml inserts no plugin rows")
    print("  cordis.patch.yml: every row names a real package and only known fields")


# --------------------------------------------------------------------------- #
# Part 2: the live run


class FakeOpenAI:
    """A deterministic OpenAI-compatible endpoint that scripts exactly one subagent spawn."""

    def __init__(self):
        self.requests = []
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

                def user_marker():
                    for message in messages:
                        if message.get("role") == "user" and CHILD_MARKER in json.dumps(message.get("content")):
                            return True
                    return False

                if not tools:
                    return self._text("probe title")
                if user_marker():
                    return self._text("child-final")
                if any(message.get("role") == "tool" for message in messages):
                    return self._text("root-final")
                return self._tool_call("subagent", json.dumps({
                    "description": "spawn a child",
                    "prompt": f"do the child task {CHILD_MARKER}",
                    "run_in_background": False,
                }))

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
                self._start()
                self._chunk({"role": "assistant", "tool_calls": [
                    {"index": 0, "id": "call_probe_1", "type": "function",
                     "function": {"name": name, "arguments": ""}}]})
                self._chunk({"tool_calls": [{"index": 0, "function": {"arguments": arguments}}]})
                self._chunk({}, "tool_calls")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        return Handler


def system_text(request):
    parts = []
    for message in request.get("messages") or []:
        if message.get("role") == "system":
            content = message.get("content")
            parts.append(content if isinstance(content, str) else json.dumps(content))
    return "\n".join(parts)


def is_child(request):
    for message in request.get("messages") or []:
        if message.get("role") == "user" and CHILD_MARKER in json.dumps(message.get("content")):
            return True
    return False


def probe(repo, dsh_bin, keep):
    scratch = Path(tempfile.mkdtemp(prefix="devstandard-dsh-probe-"))
    home = scratch / ".dsh"
    profile = "devstandard-probe"
    env = {**os.environ, "DSH_HOME": str(home), "PROBE_KEY": "devstandard-local-fixture"}
    env["DSH_PERMISSION_MODE"] = "danger-full-access"  # no approval channel in a one-shot run
    print(f"== live run (scratch {scratch}) ==")
    try:
        code, _, err = run([dsh_bin, profile, "--from-default-profile", "headless", "--dump-config"],
                           env=env)
        require(code == 0, f"profile init failed: {err[-800:]}")

        code, _, err = run([dsh_bin, "plugin", "--profile", profile, "add", str(repo)], env=env)
        require(code == 0, f"composing the bundle failed: {err[-800:]}")

        with FakeOpenAI() as endpoint:
            patch = scratch / "llm.yml"
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
                "- id: agent-default-model\n"
                "  config:\n"
                "    provider: probe-local\n"
                "    model: probe-model\n"
            )
            code, out, err = run([dsh_bin, profile, "--patch", str(patch), "--json", TASK], env=env)
            require(code == 0, f"the dsh run failed: {err[-800:]}")
            print("  run events:")
            for line in out.splitlines():
                print("   ", line)
            requests = list(endpoint.requests)

        return scratch, requests
    finally:
        if not keep:
            shutil.rmtree(scratch, ignore_errors=True)


def analyse(requests):
    print("== analysis ==")
    child = [i for i, request in enumerate(requests) if is_child(request)]
    root = [i for i, request in enumerate(requests) if not is_child(request) and (request.get("tools") or [])]
    page = ORCHESTRATOR.read_text()
    print(f"  captured requests: {len(requests)} (root {len(root)}, child {len(child)})")
    require(child, "no spawned-child request was captured")
    require(root, "no root request was captured")
    for i, request in enumerate(requests):
        kind = "child" if i in child else ("root" if i in root else "title")
        print(f"  req{i}: kind={kind} system_bytes={len(system_text(request))} "
              f"carries_orchestrator={page in system_text(request)}")

    carrying = [i for i in root if page in system_text(requests[i])]
    require(carrying, "the root request does not carry reference/orchestrator.md's bytes")
    print(f"  OK: root request(s) {carrying} carry {ORCHESTRATOR.name}'s exact bytes")

    leaked = [i for i in child if page in system_text(requests[i])]
    require(not leaked, f"a spawned child request carries the orchestrator page: {leaked}")
    print("  OK: no spawned-child request carries reference/orchestrator.md")
    print("  Probe 2 item 1: a section on the root agent.ctx does NOT reach a spawned child; "
          "no shadowing fallback is required.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsh", default=shutil.which("dsh"), help="the dsh executable (default: PATH)")
    parser.add_argument("--keep", action="store_true", help="keep the scratch directory")
    args = parser.parse_args()
    require(args.dsh, "dsh was not found on PATH; pass --dsh")
    require(ORCHESTRATOR.is_file(), f"missing {ORCHESTRATOR}")

    scratch = Path(tempfile.mkdtemp(prefix="devstandard-dsh-validate-"))
    try:
        profile_dir = scratch / ".dsh" / "profiles" / "devstandard-validate"
        validate(ROOT, profile_dir, args.dsh)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    _, requests = probe(ROOT, args.dsh, args.keep)
    analyse(requests)

    print("\nRESULT: bundle validates and role delivery holds (root has the page, child does not)")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"\nFAILED: {error}", file=sys.stderr)
        sys.exit(1)
