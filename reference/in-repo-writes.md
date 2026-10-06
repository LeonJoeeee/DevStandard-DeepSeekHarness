# What documentation may be added to a repository

Read this before adding documentation. It decides whether the document belongs in the repository at
all; editing an already tracked document at that exact path is ordinary work except where the rule
below says otherwise. Apply the whole predicate, then write only when it admits the document.

<!-- BEGIN IN-REPO-WRITES PREDICATE -->
This predicate governs documentation: prose a person or agent reads, including generated prose. It
does not govern non-document build output, code, genuine product or runtime configuration, fixtures,
lockfiles, or `.gitignore`. A handoff or session-state artifact is governed whatever its syntax or
extension; calling `session-state.json` configuration does not change what it is.

Adding a document requires one of the three admissions below. Editing a document already tracked at
that exact path is ordinary work: the existing file licenses that path, never another document
elsewhere. The exception is a handoff or session-state document, which must qualify on every edit;
inheriting one is the defect, not permission to entrench it.

1. **A method kind whose own trigger fired.** The kinds and triggers are:
   - `docs/PRD.md` and `docs/architecture.md`: founding or task-scoped architectural redefinition;
   - `docs/architecture/<subsystem>.md`: the overview can no longer explain that subsystem legibly;
   - `docs/adr/NNNN-*.md`: the ADR admission test fired;
   - `docs/specs/YYYY-MM-DD-*.md`: the change is substantial;
   - the repo-root instructions file: there is a command, environment gotcha, worktree copy-list entry, or
     record-language declaration to put in it.

   The trigger is always required. Arms 2 and 3 cannot admit an ADR whose admission test failed, a
   spec no change earned, or content outside the instructions file's fence. Trigger gating is separate from path
   selection: the paths above are canonical relative to the scope whose lifecycle ran, while arm 2
   may supply an adopted repository's established location. `docs/architecture.md`, the repo-root
   instructions file, and its content fence are reserved: the first two remain the entry points a
   session can find without another pointer, and the content fence admits no substitute.
   `README.md` is admitted only as founding-scaffolder output named by the accepted setup design; a
   scaffolder introduced later licenses nothing.

2. **A kind an established convention of the base tree keeps, whose own creation condition fired.**
   Pin the pre-work base as `{CONVENTION_BASE_SHA}`: `origin/main`, local `main` or `HEAD` when there is
   no remote, and the empty tree for founding setup. The base must show files sharing the purpose,
   location, and naming, or a tool already in that base must maintain the kind; its real creation
   condition must also have occurred, such as a release happening or its generator running. One
   incidental file and shape alone are not a convention. A convention whose condition is “a session
   ended” is the forbidden pattern, not an exception: put the state on the issue instead.

3. **It was requested in writing by an authority.** Authority is the human, the main session, or the
   pre-work record: the issue as the dispatcher wrote it; the accepted spec at the version accepted,
   whose reachable blob SHA was published to the issue before dispatch; or a pre-existing document.
   A handoff or session-state artifact is never authority. A doer editing or commenting on its own
   issue, or adding authorization to the spec it is implementing, is escalation until the main session
   approves it there. For work with neither issue nor remote, the human's instruction in that
   session may authorize a document only when disclosed with the handback.

Never create two competing authorities at the same scope. A marked translation naming its canonical
document and a split-on-zoom child linked from its overview do not compete. Check collisions against
what the merge will contain, including `{REVIEW_BASE_SHA}`, the head, and the other candidate
documents; use `{CONVENTION_BASE_SHA}` only to decide whether a convention licensed the addition.

Anything passing no arm is invented. “A session ended” or “work changed hands” is never sufficient
under any arm or file format. An invented document is usually a message wearing a filename: put the
handoff, summary, or status on the issue, in the PR description, or in a comment instead.
<!-- END IN-REPO-WRITES PREDICATE (51 payload lines) -->

This page governs what may be added *inside* the repo. For a write outside it, use
`reference/out-of-repo-writes.md`; for the final working-tree inventory, use
your role page's The tree you hand back section.
