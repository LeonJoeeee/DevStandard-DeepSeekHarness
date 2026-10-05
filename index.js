/**
 * The DevStandard dsh bundle's plugin: it delivers the orchestrator's role text to the
 * root agent alone, and guards the role word list at the harness's own tool-interception
 * point.
 *
 * Role delivery. `agent/created` fires before an agent's first turn, and registering a
 * system-prompt section through `agent.ctx` scopes it to that one agent (dsh-scope). A
 * spawned child's scope is a sibling of its parent's — both hang under the shared preset
 * generation — never a descendant, so a section registered here on the root reaches the
 * root and nobody else (Probe 2 item 1, issue #4). The page is read from the bundle at
 * load, so a page edit is a package edit and the role has one source.
 *
 * The guard. `tools/pre-execute` fires before a tool body and its listener may deny with a
 * reason; `guard.js` carries the word engine (`scripts/hard_edges.py`'s policy, ported and
 * pinned by `.github/check-dsh-guard.py`), and this module resolves the caller's role and
 * denies the one call, or admits it. A shell command's text is `exec.arguments.command` and
 * the shell tool is named `bash`. Whether a call is the root's or a child's comes from the
 * session header (`isRoot`); a child's own role comes from its durable `subagent/descriptor`
 * persona — Probe 2 item 2, answered in #6 — whose text is the role page's exact bytes, so
 * it is matched against the bundle's own pages rather than the free-text `label`. Both rows
 * are `continuable`, so a background delegation always carries the composition; a child
 * that has none — a foreground one-shot child, or any future row without a persona — takes
 * the worker-and-reviewer union, ADR 0062's amendment's fallback.
 *
 * @module devstandard-dsh
 */
import { readFileSync } from 'node:fs'
import { decide } from './guard.js'

/** The section's name, unique within the root agent's prompt scope. */
const SECTION = 'devstandard:orchestrator'

/**
 * The role's placement, measured from the deployment persona prefix (order 0): after the
 * harness identity (-1000) and the deployment persona (0) have opened the prompt, and
 * before the first first-party policy section (plan policy, 500). The offset resolves
 * against the host's own constant, so a host that moves the prefix moves this with it.
 */
const ORDER_OFFSET = 100

/** The page each role's own subagent carries as its persona; the guard matches these bytes. */
const ROLE_PAGES = {
  worker: 'worker.md',
  reviewer: 'code-review-prompt.md',
}

/** Read one of the bundle's own `reference/` pages, resolved next to this module. */
function readPage(file) {
  return readFileSync(new URL(`./reference/${file}`, import.meta.url), 'utf8')
}

/**
 * Whether a created agent is a top-level session rather than a dispatched child.
 *
 * Root and child are read from the session header: a top-level session records no parent
 * and no delegation depth and is not `origin: 'subagent'`; a spawned child records all
 * three. A forked child keeps `origin` unset but still names its parent, so testing
 * `parentSession` as well keeps a fork out of the root branch.
 *
 * @param agent - the agent payload of `agent/created`, or the live `exec.agent`.
 * @returns whether this agent is the session's root.
 */
function isRoot(agent) {
  const header = agent?.session?.header
  if (header === undefined) return false
  return header.parentSession === undefined
    && header.delegationDepth === undefined
    && header.origin !== 'subagent'
}

/**
 * A child's own durable `subagent/descriptor` persona, or `undefined` when its log carries
 * none (a one-shot child persists only `{mode, provider, label}`).
 *
 * The descriptor is appended inside the child's initial turn, before its first request, so
 * it is present by the time any guarded call runs. It is read from the child's own events,
 * which is what `ownEvents()` returns.
 *
 * @param agent - the live `exec.agent`.
 * @returns the persona text, or `undefined`.
 */
function descriptorPersona(agent) {
  try {
    const events = agent?.session?.ownEvents?.()
    if (!Array.isArray(events)) return undefined
    const descriptor = events.find((event) => event?.type === 'subagent/descriptor')
    const persona = descriptor?.data?.persona
    return typeof persona === 'string' ? persona : undefined
  } catch {
    return undefined
  }
}

/**
 * Register the role-delivery listener and the guard.
 *
 * @param ctx - the plugin's context.
 */
export function apply(ctx) {
  const text = readPage('orchestrator.md')
  const personas = new Map(
    Object.entries(ROLE_PAGES).map(([role, file]) => [readPage(file), role]))

  // One resolution per agent. A descriptor is immutable, so a child's role never changes;
  // caching also keeps the persona byte-compare off every call.
  const roles = new WeakMap()

  const roleOf = (agent) => {
    if (roles.has(agent)) return roles.get(agent)
    let role
    if (isRoot(agent)) {
      role = 'orchestrator'
    } else {
      role = personas.get(descriptorPersona(agent)) ?? 'child'
    }
    roles.set(agent, role)
    return role
  }

  ctx.on('agent/created', ({ agent }) => {
    if (!isRoot(agent)) return
    agent.ctx.systemPrompt.section({
      name: SECTION,
      order: agent.ctx.systemPrompt.getSectionOrder('DEPLOYMENT_PERSONA_PREFIX') + ORDER_OFFSET,
      text,
      interpolate: false,
    })
  })

  ctx.on('tools/pre-execute', (exec, next) => {
    if (exec.agent === undefined) return next()
    try {
      const reason = decide(roleOf(exec.agent), exec.name, exec.arguments)
      if (reason !== undefined) return { kind: 'deny', reason }
    } catch (error) {
      // Fail open (#437). A bug in the guard must not deny every tool call in every lane at
      // once; the call is admitted and one line names the error. The word rules above still
      // refuse on their own path, and nothing here reads a file, a ref or the network.
      process.stderr.write('devstandard guard admitted this call without deciding: '
        + ' '.join(String(error).split()) + '\n')
    }
    return next()
  })
}
