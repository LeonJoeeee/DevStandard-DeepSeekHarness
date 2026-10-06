# DevStandard in DeepSeek Harness

This page maps the dsh harness for a dispatched worker; `reference/worker.md`, delivered with
it, carries the contract — including what a worker does when the packet cannot be recovered.

## The role subagent

A dispatched worker receives this page and `reference/worker.md` as the `worker` delegation row's
`persona`, read from the bundle when the child is created: the role arrives without a read, is not
injected by a hook, and both pages survive compaction. The orchestrator spawns you by calling the
`worker` tool, which hands you a pointer to the assembled brief; a review runs on the `reviewer` row instead. The row fixes
the model and effort — one anchor in the bundle's `cordis.patch.yml` — so the route is not the
worker's to choose. A child's role stays recoverable from its own durable `subagent/descriptor`,
which carries that `persona` byte for byte, so the role hook resolves a worker exactly and not a
widened set.

An in-process child inherits the session's permissions and cwd, and dsh adds no per-worker OS
sandbox: a lane's isolation is the worktree, the role hook, and independent review. The row's
depth default stops a child spawning another, so the task-local work a worker does — research,
checking a diff — happens in this lane directly.

## Recovering the binding

The dsh host keeps a durable session log per session under `$DSH_HOME/sessions`, keyed by the
session's working directory, and the child's own conversation is one of them. A model-written
compaction summary, the caller's current directory and another lane's log each describe something
other than this lane, so none of them identifies the packet. The log does: emit a nonce through any
tool call, then search the lane's session logs for it — exactly one session carries it, and the
delegation recorded there is the packet as delivered. (This host stores each log compressed, as
`session.v4.jsonl.zstd`; decompress before searching.) More than one match means the nonce no
longer picks out a single lane, and the packet is not recovered.

## Where the role hook sits

The role hook rides dsh's `tools/pre-execute` and reads the shell tool's own command text —
`exec.arguments.command` on the shell tool dsh names `bash`. It matches whole words and never reads
a file, a ref or the network. Which words it refuses is the contract page's, not this one's.
