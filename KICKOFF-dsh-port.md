# KICKOFF — This repo: DevStandard for DeepSeek Harness (dsh)

*Handoff from the llm-gateway operator session, 2026-10-05. Scratch file — delete once this repo's own records (issue/ADR/spec) carry everything.*

## What the owner wants

**This is a new project.** It begins as a full copy (content + git history) of `github.com/LeonJoeeee/devstandard` — the Claude Code version of DevStandard — and it must be adapted into the method delivered natively for **DeepSeek Harness (dsh)** as the main session. The Claude Code project stays as-is; the two are separate siblings, not a fork.

Owner's words (2026-10-05):

- "我是要新的库,不是那一个库...这是两个不同的项目。" — new project; do not push changes back to `LeonJoeeee/devstandard`.
- "里面涉及一些关于 subagent 的发 codex 的 subagent,那个就不需要了,让他完全用内置的就行。" — **remove all Codex-dispatch machinery**; subagent dispatch uses **the harness's own built-in mechanism** only (for dsh: dsh's native subagents).
- "反正都用 DeepSeek V4.1 Flash Max 就可以。" — everything runs on **DeepSeek V4.1 Flash at max effort** (already provisioned on this machine).

**Read the founding issue in THIS repo (the ["Founding" issue](https://github.com/LeonJoeeee/devstandard-dsh/issues) — #1 unless titled otherwise) FIRST — it is the full mission brief** (goal, bounds, done-check, environment facts). Then run your normal orchestrator flow: restate the mission to the owner, research dsh's extension surfaces, produce a design spec + ADRs, and get the owner's explicit approval **before writing implementation code**.

## This machine differs from a stock machine (operator-verified 2026-10-05)

1. **dsh 0.2.0-rc.2 is installed and wired**: `dsh` on PATH (profiles: headless/tui/web). Config patch `~/.dsh/cordis.patch.yml` → provider `our-gateway` → `http://127.0.0.1:4000/v1`, model `deepseek-v4.1-flash`. Env key `DSH_GATEWAY_KEY` via `~/.bashrc` (reads `~/.config/llm-gw-keys/dsh-ds.key`, 0600). Verified end-to-end: a real file task ran in 7s.
2. **Local LLM gateway** (LiteLLM 1.103.2, `127.0.0.1:4000`) → relay → DS V4.1 Flash at ~220 tok/s; bare calls default to **max** effort; it also serves `/v1/responses`.
3. **Subagent rule for YOUR sessions here (owner, 2026-10-05)**: dispatched subagents use **the built-in Agent tool only** — never Codex CLI. Built-in subagents run on the session model: **DeepSeek V4.1 Flash at max** through the gateway. (The Codex CLI on this machine rides the slow ChatGPT subscription — out of favor.)
4. **WebSearch tool is broken on this machine** (custom-model host, no Anthropic search backend). Use **firecrawl** (`firecrawl search ... --json` / `firecrawl scrape ...`); WebFetch works. See `~/.claude/CLAUDE.md`.
5. Read-only context about the machine's model wiring: `~/.claude/projects/-home-leon-projects-prod-llm-gateway/memory/` (e.g. `codex-dsh-relay-ds-deployed.md`, `tps-landscape-20261005.md`).
6. **Secrets discipline**: never print key files or raw provider errors. Gateway keys: `~/.config/llm-gw-keys/` (0600). Do not modify the gateway config/keys or the llm-gateway repo from this project — consume the gateway as an external service.
7. **The original project (reference, read-only)**: `github.com/LeonJoeeee/devstandard` and its checkout at `/home/leon/projects/prod/devstandard`. Read its method, ADRs, references and scripts as porting material. Note from its own ADR lineage (0006/0039/0047): the native harness owns sessions/tools/agents; DevStandard ships protocol, not machinery — the dsh port should carry that philosophy.

## First message the owner will paste

> 读 KICKOFF-dsh-port.md 和本仓库的 Founding issue,然后按你的编排流程开工:把本项目改造成 DeepSeek Harness 原生的 DevStandard。先跟我讨论确认设计,再动手。你这条会话的 subagent 一律用内置的(跑在 DeepSeek V4.1 Flash Max 上),全程不要用 Codex。
