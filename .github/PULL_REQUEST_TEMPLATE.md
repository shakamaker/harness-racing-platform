## What

<!-- One-paragraph summary of the change. -->

## Why

<!-- Link to issue / spec section. e.g., CLAUDE.md §4.2.3 -->

## Lane

<!-- Tick one. PR must only modify paths in the owned lane (see docs/file-ownership.md). -->

- [ ] Agent 1 — scraper (`services/scraper/**`)
- [ ] Agent 2 — parser (`services/parser/**`)
- [ ] Agent 3 — db (`packages/models/**`, `sql/migrations/**`, `docs/erd/**`)
- [ ] Agent 4 — api (`services/api/**`, `sql/queries/**`, `sql/views/**`)
- [ ] Agent 5 — web (`apps/web/**`)
- [ ] team-lead (workspace files — requires broadcast)
- [ ] debugger fix (`fix/debug/<id>`)

## Tests

<!-- Coverage on changed files must be >=80%. Paste pytest/vitest summary. -->

```
$ pytest services/<lane> --cov
...
```

## Logs

<!-- Per spec §5.1: paste success + failure log samples showing structured JSON output. -->

```json
{"timestamp": "...", "level": "INFO", "agent": "...", "module": "...", "action": "...", "outcome": "ok"}
```

## ADR

<!-- If architectural, link to docs/adr/NNNN-*.md. -->

## pr-review-toolkit sign-off

- [ ] pr-review-toolkit has commented an approval on this PR
- [ ] All CI checks green
- [ ] Squash-merge only (no merge commits)
