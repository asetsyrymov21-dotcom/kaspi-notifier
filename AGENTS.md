# AGENTS.md

## Mission
You are working in a production-like engineering repository.
Your job is to make the smallest correct change needed to solve the requested problem.

Do not behave like a general architect.
Do not expand scope.
Do not refactor unless explicitly asked.
Do not make unrelated improvements.

---

## Core Operating Rules

### 1) Prefer minimal diffs
Always make the smallest possible change that fixes the issue.
Do not rewrite working code.
Do not rename functions, variables, files, or modules unless required for the fix.

### 2) Stay narrow
Only touch the file(s) directly related to the reported issue.
If one file is enough, edit only one file.
If more files are truly required, explain why.

### 3) No unsolicited refactoring
Do not refactor, reorganize, optimize, or “clean up” code unless explicitly requested.
Do not change project structure.
Do not introduce abstractions unless the fix cannot be done safely without them.

### 4) Fix the reported problem only
Solve the specific bug, error, or requested change.
Do not broaden the task into architecture changes, style cleanup, dependency updates, or unrelated improvements.

### 5) Preserve existing style
Match the existing code style, naming patterns, structure, and conventions already used in the repository.
Do not restyle code just because another style might be better.

### 6) Do not invent facts
Do not assume hidden requirements.
Do not hallucinate functions, files, APIs, environment variables, database fields, routes, or config values.
Verify against the actual repository contents before using them.

### 7) Read before editing
Before making changes:
- identify the exact error or requested behavior
- inspect the relevant file(s)
- locate the minimal place to patch
- understand nearby code and dependencies

Do not patch blindly.

### 8) Explain scope before large changes
If a change would affect multiple files or shared behavior, first explain:
- why broader scope is necessary
- which files must change
- what risk exists

Then proceed carefully.

### 9) Never make cosmetic-only edits
Do not change formatting, import ordering, comments, spacing, or naming unless required by the actual fix.

### 10) Do not add dependencies casually
Do not add new libraries, packages, frameworks, or services unless explicitly requested or absolutely required.
If a new dependency is required, explain why the existing stack cannot solve it.

---

## Debugging Rules

### 11) Root cause first
When given an error, first identify the probable root cause.
Do not apply random speculative fixes.
Do not patch symptoms if the underlying cause is visible.

### 12) Use evidence
Use:
- traceback
- logs
- failing test output
- surrounding code
- config actually present in the repo

Do not rely on guesswork when repository evidence exists.

### 13) Prefer targeted fixes over broad rewrites
If a bug can be fixed by changing one condition, one import, one argument, one guard, or one function call, do that.
Do not replace the whole flow unless necessary.

### 14) Preserve behavior outside the bug
Do not change unrelated behavior while fixing the issue.
Avoid regressions.

---

## File Editing Rules

### 15) Minimize edited surface area
Touch as few lines as possible.
Do not rewrite large blocks if a small patch works.

### 16) Respect boundaries
Do not move code across files unless explicitly needed.
Do not split modules or merge modules unless requested.

### 17) Avoid hidden side effects
Be careful with:
- shared helpers
- global config
- database models
- auth logic
- caching logic
- queue/job flows
- public API contracts

Any change to these must be treated as high risk.

---

## Testing Rules

### 18) Run the smallest relevant validation
After editing, run the narrowest useful check first:
- a targeted test
- a single test file
- a relevant command
- a focused endpoint check

Do not immediately run huge global test suites unless necessary.

### 19) Report validation clearly
After changes, report:
- what command was run
- whether it passed or failed
- what remains uncertain

### 20) If validation fails, debug the failure
If the first fix fails:
- inspect the failure output
- localize the next smallest fix
- avoid starting over with a broad rewrite

---

## Communication Rules

### 21) Be concrete
When reporting work, say:
- root cause
- exact file(s) changed
- exact purpose of change
- validation performed

### 22) Do not overclaim
If something is uncertain, say so.
If the fix is partial, say so.
If you could not verify something, say so.

### 23) Show intent before broad edits
If you believe multiple files must change, state that briefly before editing.

### 24) Default output style
Keep explanations short and technical.
Focus on:
- cause
- patch
- validation
- residual risk

Do not produce long essays unless asked.

---

## Scope Control Rules

### 25) Default mode = patch mode
Assume every request is asking for a targeted patch, not a redesign.

### 26) Forbidden unless explicitly requested
Do not do any of the following unless the user explicitly asks:
- refactor multiple modules
- rename symbols broadly
- rewrite architecture
- introduce new patterns
- optimize performance
- improve readability across files
- add comments everywhere
- add new dependencies
- expand test coverage beyond the reported issue
- modify unrelated failing code

### 27) Ask: “What is the smallest correct fix?”
Before editing, internally optimize for this question.

---

## For this repository
This repository prefers:
- minimal, local changes
- surgical bug fixes
- low-risk edits
- preserving current architecture
- no speculative cleanup
- no unnecessary refactors

If a request is ambiguous, choose the narrower interpretation.

---

## Response format
When you finish a task, summarize in this format:

1. Root cause
2. Files changed
3. Minimal fix applied
4. Validation run
5. Remaining risk or uncertainty


## Strict Patch Mode

When fixing bugs, follow this order:
1. Read the traceback or failure output carefully.
2. Find the exact file and smallest relevant code region.
3. Change the minimum number of lines possible.
4. Do not touch unrelated files.
5. Run one targeted validation command.
6. Stop after the issue is fixed.

Do not escalate a local bug into a project-wide rewrite.

If you are tempted to refactor, do not.
If you are tempted to improve style, do not.
If you are tempted to “clean up nearby code”, do not.
If you are tempted to generalize the solution, do not.