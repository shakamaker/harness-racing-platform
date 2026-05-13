# harness-racing-platform

Australian harness racing data platform: scraper, parser, normalised DB, FastAPI backend, React frontend.

## Repository layout

```
packages/models/    SQLAlchemy 2.x ORM + Pydantic schemas        owner: Agent 3 (db)
services/scraper/   Playwright async crawler (anti-bot)           owner: Agent 1 (scraper)
services/parser/    HTML -> dataclasses -> ORM upsert             owner: Agent 2 (parser)
services/api/       FastAPI + par-times engine                    owner: Agent 4 (api)
apps/web/           React 18 + Vite + TanStack Query              owner: Agent 5 (web)
sql/                Hand-written queries, migrations, views       owner: Agents 3 & 4
docs/               ADRs, ERD, decomposition plan
.github/            CI workflows + PR template
```

Full spec: [CLAUDE.md](./CLAUDE.md). Parallel decomposition: [docs/decomposition-plan.md](./docs/decomposition-plan.md). File ownership matrix: [docs/file-ownership.md](./docs/file-ownership.md).

## Quickstart (dev)

```bash
docker compose up -d postgres            # PostgreSQL 16 on :5432
uv sync                                  # Python deps (workspace)
pnpm -C apps/web install                 # Frontend deps
```

## Branching

- `main` — protected, squash-merge only, requires pr-review-toolkit approval
- `develop` — integration branch, all feature PRs target this
- `feat/<domain>/<slug>` — per-agent feature branches (see file-ownership.md)
- `fix/debug/<id>` — debugger-agent auto-generated fix branches

## CI

Every PR runs lint (ruff, eslint), type-check (mypy, tsc), tests (pytest, vitest), build, security scan. All green required before pr-review-toolkit final approval. See `.github/workflows/ci.yml`.
