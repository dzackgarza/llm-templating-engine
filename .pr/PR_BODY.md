## Milestone Goal

Keep `llm-templating-engine` centered on one explicit CLI/rendering contract while removing cleanup residue that does not belong in the reusable template engine boundary.

Milestone: `Template CLI and Quality Cleanup` (#1)

## Milestone Tree

- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1)
  Closes #1
- [ ] [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2)
  Closes #2

## Explicit Exclusions / Deferred Work

- New OpenCode-specific adapters, MCP wrappers, or consumer-specific behavior in this repository.
- Consumer-repo migrations beyond the evidence needed to prove they consume this CLI/library instead of embedding rendering logic.
- Unrelated packaging/version bumps or new command surfaces outside `llm-template-render`, `llm-template-inspect`, `llm-template-validate`, and the existing `llm-templating-engine list` inventory command.

## Dependency Order

1. Lock the public CLI boundary first: the canonical product surfaces remain `llm-template-render`, `llm-template-inspect`, and `llm-template-validate`, with README examples staying `uvx`-first.
2. Decide which helpers truly belong inside the reusable engine versus downstream consumers, so cleanup does not delete behavior that is still part of the library/CLI contract.
3. Remove or replace the bespoke frontmatter split/reconstruct path and the regex-based undefined-variable extraction in `src/llm_templating_engine/core.py` without weakening render/inspect/validate behavior.
4. Collapse overlapping cleanup residue into one canonical ledger before the PR can leave draft.

## Implementation Checklist

- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1): audit `README.md`, `pyproject.toml`, and `src/llm_templating_engine/cli.py` so the canonical command surface is explicit and unchanged where promised.
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1): verify downstream callers consume this CLI/library instead of re-embedding template parsing/rendering, and document any explicit exception that must remain.
- [ ] [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): replace `_split_frontmatter` / `_reconstruct_frontmatter` with a smaller owned boundary or an established dependency that preserves round-trip behavior for frontmatter-bearing templates.
- [ ] [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): eliminate regex-based undefined-variable extraction by moving the missing-binding path onto a structural Jinja surface such as AST prevalidation or a custom `Undefined` contract.
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1) and [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): merge, delete, or justify duplicated helper surfaces so one cleanup ledger remains.

## Validation / Proof Checklist

- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1): `README.md` examples still match the shipped CLI entrypoints and `uvx` usage.
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1): fixture-backed CLI evidence covers `llm-template-render`, `llm-template-inspect`, and `llm-template-validate`.
- [ ] [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): targeted tests prove frontmatter parsing/rendering and undefined-binding behavior remain correct after cleanup.
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1) and [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): `just test`
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1) and [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): `just check`
- [ ] [#1 Track CLI-first policy alignment for templating backend](https://github.com/dzackgarza/llm-templating-engine/issues/1) and [#2 Audit: Reinvention Slop identified in codebase](https://github.com/dzackgarza/llm-templating-engine/issues/2): `just build` when packaging or release surfaces change.

## Evidence Slots

- [ ] CLI contract evidence:
- [ ] README / `uvx` parity evidence:
- [ ] Frontmatter-boundary evidence:
- [ ] Undefined-binding evidence:
- [ ] QC / build evidence:

## Blocked / Open Questions

- Which helpers belong in the reusable engine, and which should move to downstream consumers such as `llm-runner` instead of surviving here?
- Should missing-variable reporting move to AST prevalidation, a custom `Undefined` implementation, or another structural Jinja surface?
- Does the chosen frontmatter boundary preserve the current document round-trip contract for `inspect` and `render` responses?
- Fresh-clone note from this planning run: `just test` currently failed in this environment because `ruff` was not found after `uv sync --extra dev`; verify whether the lock/bootstrap path or local tool installation owns that gap before claiming proof completion.

## Review-Readiness Gate

- Keep this PR in draft until every in-scope checklist item above is complete or explicitly re-scoped.
- Do not mark ready while deferred work remains hidden inside checked boxes.
- Attach concrete evidence for README parity, targeted CLI behavior, and the declared `just` proof commands.
- If consumer-boundary research changes issue ownership, update the linked issue tree before leaving draft instead of laundering the scope change into implementation notes.
