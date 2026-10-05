#!/usr/bin/env python3
"""Check the shipped dsh bundle's role rows, model anchor, and generated personas (issue #6).

The bundle's two delegation rows carry each role page's text as an inline `persona`, because
dsh's `@deepseek-ai/dsh-tool-subagent` accepts inline text only — a plain string, not a file path.
That duplication is exactly what this gate polices: `reference/worker.md` and
`reference/code-review-prompt.md` remain the one operative source per role (ADR 0060's rule), and
each row's embedded `persona` must be their **byte-for-byte** contents. Run with `--write` to
regenerate the persona regions in place; without it the gate only checks, so CI fails on a persona
that has drifted from its source page.

The same gate holds the port's single model anchor (ADR 0066) to one site: the model id must appear
**exactly once** in the shipped bundle, inside `cordis.patch.yml`, where a YAML anchor lets both
rows alias the one route. It also holds the reviewer row's write denial and the row shape.

It is deliberately independent of `dsh`: the ordinary suite job runs on a runner without dsh
installed, so nothing here shells out to the harness. Package-name *resolution* against an installed
dsh is checked separately, by `.github/test-dsh-bundle.py`, where a composed profile exists.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "cordis.patch.yml"

# The port's one model anchor (ADR 0066) and the effort it runs at.
ANCHOR_MODEL = "deepseek-v4.1-flash"
ANCHOR_EFFORT = "max"

SUBAGENT = "@deepseek-ai/dsh-tool-subagent"
# Role rows: id -> (toolName, persona source page, denies the write tools?).
ROLES = {
    "devstandard-worker": ("worker", Path("reference/worker.md"), False),
    "devstandard-reviewer": ("reviewer", Path("reference/code-review-prompt.md"), True),
}
# The write tools the reviewer must not hold. `str_replace_editor` is a shipped-but-unmounted
# optional tool in this dsh build, and `tools.restrict()` rejects an unknown global name at child
# creation, so naming it would break the reviewer tool; the mounted write tools here are these two.
REVIEWER_DENY = ["write", "edit"]
DELIVERY_ROW = ("devstandard-role-delivery", "devstandard-dsh")

# Every field a `cordis.patch.yml` entry may declare, and the fields the tool-subagent config accepts.
ENTRY_FIELDS = {"id", "name", "config", "group", "disabled", "inject", "intercept", "isolate"}
PATCH_FIELDS = ENTRY_FIELDS | {"insert"}
CONFIG_FIELDS = {
    "provider", "toolName", "modelSelectionSettings", "enableRunInBackground",
    "backgroundMode", "agentOptions", "persona", "toolFilter", "maxDepth",
}
AGENT_OPTION_FIELDS = {"provider", "model", "reasoningEffort", "maxTokens"}

BEGIN = "# BEGIN GENERATED PERSONA ({rel}) — regenerate: .github/check-dsh-bundle.py --write"
END = "# END GENERATED PERSONA"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def persona_lines(indent: str, data: bytes) -> list[bytes]:
    """The exact `persona: |` line plus its indented body, reproducing `data` byte for byte.

    A literal block scalar with the default clip chomping parses back to the body's lines joined by
    `\\n` plus exactly one trailing newline, so the source must end in a single `\\n` with no blank
    trailing line and no trailing whitespace — the invariants this gate asserts on the source page.
    """
    require(data.endswith(b"\n") and not data.endswith(b"\n\n"),
            f"{'source'}: source page must end in exactly one newline")
    body = data[:-1].split(b"\n")
    out = [f"{indent}persona: |\n".encode()]
    for line in body:
        require(line.rstrip() == line, "source page line has trailing whitespace")
        out.append((indent + "  ").encode() + line + b"\n" if line else b"\n")
    return out


def persona_region(lines: list[bytes], rel: str) -> int:
    """The index of the BEGIN marker line for `rel`, which fixes the persona key's indentation."""
    wanted = BEGIN.format(rel=rel).encode()
    hits = [i for i, line in enumerate(lines) if line.strip() == wanted]
    require(len(hits) == 1, f"{PATCH.name}: expected exactly one persona marker for {rel}, found {len(hits)}")
    return hits[0]


def write_personas() -> None:
    lines = PATCH.read_bytes().splitlines(keepends=True)
    edits = []
    for _, (_, rel, _) in ROLES.items():
        begin = persona_region(lines, rel.as_posix())
        indent = lines[begin][: len(lines[begin]) - len(lines[begin].lstrip(b" "))].decode()
        ends = [i for i in range(begin + 1, len(lines)) if lines[i].strip().decode() == END]
        require(ends, f"{PATCH.name}: missing {END!r} after {rel}")
        edits.append((begin + 1, ends[0], persona_lines(indent, (ROOT / rel).read_bytes()), rel))
        print(f"{rel}: persona region regenerated")
    for start, stop, body, _ in sorted(edits, reverse=True):
        lines[start:stop] = body
    PATCH.write_bytes(b"".join(lines))


def shipped_files(manifest: dict) -> list[Path]:
    """Expand package.json's `files` list to real files, dropping the `docs/` history.

    Every entry must exist; `docs/` (the ADR log and specs) is validated but then left out of the
    return, because a historical record is not a live site for the single-model-anchor sweep.
    """
    out = []
    for entry in manifest.get("files", []):
        path = ROOT / entry.rstrip("/")
        require(path.exists(), f"package.json files names a missing path: {entry}")
        if entry == "docs" or entry.startswith("docs/"):
            continue
        if path.is_dir():
            out.extend(p for p in path.rglob("*") if p.is_file())
        else:
            out.append(path)
    return out


def check() -> None:
    manifest = json.loads((ROOT / "package.json").read_text())
    patch = manifest.get("dsh", {}).get("bundle", {}).get("patch")
    require(isinstance(patch, str) and (ROOT / patch).is_file(),
            "package.json declares no resolving dsh.bundle.patch")
    shipped = shipped_files(manifest)
    print(f"package.json: dsh.bundle.patch -> {patch}; every files entry exists ({len(shipped)} files)")

    raw = PATCH.read_bytes()
    text = raw.decode()
    rows = yaml.safe_load(text)
    require(isinstance(rows, list) and rows, "cordis.patch.yml must be a non-empty list")

    entries: dict[str, dict] = {}
    for row in rows:
        require(isinstance(row, dict), f"patch row is not a mapping: {row!r}")
        require(not (set(row) - PATCH_FIELDS), f"patch row declares unknown field(s): {sorted(set(row) - PATCH_FIELDS)}")
        for entry in row.get("insert", []):
            require(isinstance(entry, dict), f"inserted entry is not a mapping: {entry!r}")
            require(not (set(entry) - ENTRY_FIELDS),
                    f"inserted entry declares unknown field(s): {sorted(set(entry) - ENTRY_FIELDS)}")
            require(isinstance(entry.get("id"), str) and entry["id"], "inserted entry needs a string id")
            require(entry["id"] not in entries, f"duplicate row id {entry['id']!r}")
            entries[entry["id"]] = entry

    require(entries.get("devstandard-role-delivery", {}).get("name") == DELIVERY_ROW[1],
            f"missing {DELIVERY_ROW[0]} -> {DELIVERY_ROW[1]}")

    tool_names = []
    for row_id, (tool_name, source, denies_write) in ROLES.items():
        entry = entries.get(row_id)
        require(entry is not None, f"missing role row {row_id}")
        require(entry.get("name") == SUBAGENT, f"{row_id}: name must be {SUBAGENT}")
        config = entry.get("config")
        require(isinstance(config, dict), f"{row_id}: config must be a mapping")
        require(not (set(config) - CONFIG_FIELDS),
                f"{row_id}: unknown config key(s): {sorted(set(config) - CONFIG_FIELDS)}")
        require(config.get("provider") == "spawn", f"{row_id}: provider must be spawn")
        require(config.get("backgroundMode") == "continuable", f"{row_id}: backgroundMode must be continuable")
        require(config.get("toolName") == tool_name, f"{row_id}: toolName must be {tool_name!r}")
        require("modelSelectionSettings" not in config,
                f"{row_id}: the anchor is fixed per row, so modelSelectionSettings must be absent")
        tool_names.append(config.get("toolName"))

        options = config.get("agentOptions")
        require(isinstance(options, dict) and not (set(options) - AGENT_OPTION_FIELDS),
                f"{row_id}: agentOptions must be a mapping of known fields")
        require(options == {"model": ANCHOR_MODEL, "reasoningEffort": ANCHOR_EFFORT},
                f"{row_id}: agentOptions must resolve to the one anchor "
                f"{{model: {ANCHOR_MODEL}, reasoningEffort: {ANCHOR_EFFORT}}}, got {options!r}")

        if denies_write:
            require(config.get("toolFilter") == {"deny": REVIEWER_DENY},
                    f"{row_id}: toolFilter must deny the write tools {REVIEWER_DENY}")
        else:
            require("toolFilter" not in config, f"{row_id}: a worker holds the write tools, so no toolFilter")

        require((ROOT / source).is_file(), f"{row_id}: missing persona source {source}")
        persona = config.get("persona")
        require(isinstance(persona, str), f"{row_id}: persona must be an inline string")
        expected = (ROOT / source).read_bytes()
        require(persona.encode() == expected,
                f"{row_id}: persona is not the byte-for-byte contents of {source}; "
                "regenerate with .github/check-dsh-bundle.py --write")
        print(f"{row_id}: toolName={tool_name} provider=spawn continuable, anchor OK, "
              f"persona == {source} ({len(expected)} bytes)")

    require(len(set(tool_names)) == len(tool_names), f"role toolNames collide: {tool_names}")

    sites = [path for path in shipped if ANCHOR_MODEL.encode() in path.read_bytes()]
    require(text.count(ANCHOR_MODEL) == 1,
            f"the model anchor must be stated exactly once in {PATCH.name}, "
            f"found {text.count(ANCHOR_MODEL)}")
    require(sites == [PATCH],
            f"the model anchor must appear only in {PATCH.name}, found also in "
            f"{[str(p.relative_to(ROOT)) for p in sites]}")
    print(f"model anchor: {ANCHOR_MODEL} at {ANCHOR_EFFORT}, exactly once, in {PATCH.name}")

    print("RESULT: bundle rows, model anchor, and generated personas hold")


def main() -> None:
    args = sys.argv[1:]
    require(set(args) <= {"--write"}, f"usage: check-dsh-bundle.py [--write], got {args}")
    for _, (_, source, _) in ROLES.items():
        require((ROOT / source).is_file(), f"missing persona source {source}")
    if "--write" in args:
        write_personas()
    else:
        check()


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"\nFAILED: {error}", file=sys.stderr)
        sys.exit(1)
