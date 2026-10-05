/**
 * The DevStandard dsh bundle's plugin: it delivers the orchestrator's role text to the
 * root agent alone.
 *
 * `agent/created` fires before an agent's first turn, and registering a system-prompt
 * section through `agent.ctx` scopes it to that one agent (dsh-scope). A spawned child's
 * scope is a sibling of its parent's — both hang under the shared preset generation —
 * never a descendant, so a section registered here on the root reaches the root and
 * nobody else (Probe 2 item 1, issue #4). The page is read from the bundle at load, so a
 * page edit is a package edit and the role has one source.
 *
 * @module devstandard-dsh
 */
import { readFileSync } from 'node:fs'

/** The section's name, unique within the root agent's prompt scope. */
const SECTION = 'devstandard:orchestrator'

/**
 * The role's placement, measured from the deployment persona prefix (order 0): after the
 * harness identity (-1000) and the deployment persona (0) have opened the prompt, and
 * before the first first-party policy section (plan policy, 500). The offset resolves
 * against the host's own constant, so a host that moves the prefix moves this with it.
 */
const ORDER_OFFSET = 100

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
 * @param agent - the agent payload of `agent/created`.
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
 * Register the role-delivery listener.
 *
 * @param ctx - the plugin's context.
 */
export function apply(ctx) {
  const text = readPage('orchestrator.md')
  ctx.on('agent/created', ({ agent }) => {
    if (!isRoot(agent)) return
    agent.ctx.systemPrompt.section({
      name: SECTION,
      order: agent.ctx.systemPrompt.getSectionOrder('DEPLOYMENT_PERSONA_PREFIX') + ORDER_OFFSET,
      text,
      interpolate: false,
    })
  })
}
