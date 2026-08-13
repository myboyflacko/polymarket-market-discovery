# Project

`polymarket-market-discovery` is a Python 3.12 service that discovers Polymarket markets, maintains a canonical market universe, and collects order book history. The service uses public read-only endpoints exclusively.

## Project Index

Use `INDEX.md` in the repository root for initial orientation.
When an entry point, top-level domain, or its responsibility changes, update `INDEX.md` in the same change.

## Additional Project Context

Code and configuration are authoritative for current behavior. When non-standard project knowledge or prior project-specific decisions, systems, or procedures could affect the task, start at `wiki/index.md` and read only relevant active pages. Treat `wiki/raw/` as evidence. Modify the wiki only when explicitly requested, and read `wiki/SCHEMA.md` first.

## Issue Tracker

Use Linear through the Linear MCP. Use project `Polymarket Market Discovery` and team `Engineer`.

## Working Standards

- Change only what directly belongs to the task; avoid incidental refactors and speculative features.
- Package manager: `uv`; run project commands with `uv run`.
- Tests: `pytest`. Write new tests only when explicitly requested, then run them. Run the complete test suite only when explicitly requested.
- Linter: `ruff`. Check only changed Python files with `uv run ruff check <files>`.
- Automatically run the smallest task-appropriate verification: relevant existing `pytest` tests for behavior changes, otherwise a safe task-specific check. If no executable check exists, inspect the diff carefully, report the risk, and still commit locally.
- Run builds such as `uv build` or Docker only when explicitly requested or when the task directly changes build or packaging behavior.
- Keep output short and limited to relevant results.

## Workflow

Implement → verify → lint → inspect the diff → commit. Fix failures and repeat from the affected check.

## Final Response

Begin with a short outcome statement. Then use these labels, separated by blank lines, without Markdown headings:

- `**Changed**`: changed files and what changed
- `**Verification**`: checks performed
- `**Open / Risks**`: only when work remains or risks exist
- `**Git**`: branch, commit, and PR status compactly on one line

## Gitflow

When the working directory is a Git repository:

- Never work on or push directly to `main`. `dev` is the clean starting point, not a working branch.
- Check status and branches at the start. If an existing clean working branch clearly matches the task, continue there directly.
- Otherwise, create a branch from `dev` with exactly one purpose: `feature/*`, `fix/*`, `refactor/*`, or `docs/*`. Use the normal working directory for sequential and small tasks.
- Use separate worktrees only when multiple tasks or agents are working in parallel.
- If the working branch to be used is not clean, or `dev` is not clean when creating a new branch, ask Flacko what should happen to those changes before editing.
- Commit only task-related changes; report unrelated findings only as open work. By default, commit completed changes locally with a functional commit message.
- Push the working branch and create or update a PR only when explicitly requested and after relevant checks pass.

## Safety

Do not place live trades or real orders, or move funds, without explicit approval from Flacko.
