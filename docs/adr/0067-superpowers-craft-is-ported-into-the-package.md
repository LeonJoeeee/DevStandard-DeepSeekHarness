# 0067 — The bound superpowers craft is ported into the package

Status: Accepted (2026-10-05). Supersedes 0016.

## Context

ADR 0016 made superpowers a dependency rather than a quarry: the method points at its skills instead
of copying them, and the host running a worker must have it installed. Four bindings are live — the
worker's `writing-plans`, `test-driven-development` and `systematic-debugging`, and the
orchestrator's `brainstorming` trigger — and a CI gate asserts the worker's three appear in the
shipped role page.

superpowers is a Claude Code plugin. Under dsh it does not exist, and this repository cannot depend
on it: the port's whole premise is that the host supplies mechanics and the package supplies the
method, with nothing else installed. The issue requires an explicit disposition for the dependency
and its ADR.

## Decision

**Port, not depend.** The four bound skills are converted into dsh `SKILL.md` files carried by the
bundle, with their MIT attribution and the upstream notice kept, and `reference/worker.md`'s bindings
are reconciled to the package's own skill names. Nothing else from the library is ported: the
dependency's value here was always the craft at four named steps, and the rest of it was never bound.

Rejected: **dropping the bindings** — the worker would lose the execution craft the method has
depended on since 0016, and nothing in dsh replaces it. Rejected: **depending on an external dsh skill
package** — none exists, and it would reintroduce exactly the uncontrolled external dependency this
decision removes.

## Consequences

The method becomes self-contained: a worker's craft arrives with the package that gives it its role,
so a project needs one install rather than two, and the citations in the role pages name skills the
package itself ships.

The cost is upkeep. Upstream improvements no longer arrive by installing a newer superpowers; they
arrive when someone ports them, and the four files are ours to keep true. That is the same trade
ADR 0016 made in the other direction, chosen here because the sibling's host is not available.
