# File Ownership Matrix

**Cardinal rule:** one owner per file. PRs that modify paths outside their owner's lane will be blocked by pr-review-toolkit.

## Lanes

### Agent 1 — Scraper Engineer
**Branch prefix:** `feat/scraper/`
**Owns:**
- `services/scraper/**`
- `services/scraper/playwright.config.ts`
- `services/scraper/pyproject.toml`

**Imports (read-only):**
- `packages/models` (RaceTrack, RaceMeeting ORM, RawHtmlPath helper)

### Agent 2 — Parser / Transformer Engineer
**Branch prefix:** `feat/parser/`
**Owns:**
- `services/parser/**`
- `services/parser/pyproject.toml`

**Imports (read-only):**
- `packages/models` (Race, Runner, RaceTime, StewardsComment ORM + Pydantic)

### Agent 3 — Database Architect
**Branch prefix:** `feat/db/`
**Owns (exclusive):**
- `packages/models/**`
- `sql/migrations/**`
- `docs/erd/**`

**No imports from other agents' code.** Pure schema authority.

### Agent 4 — Backend / SQL-Pro
**Branch prefix:** `feat/api/`
**Owns:**
- `services/api/**`
- `sql/queries/**`
- `sql/views/**` (materialised view DDL)

**Imports (read-only):**
- `packages/models`

### Agent 5 — Frontend Engineer
**Branch prefix:** `feat/web/`
**Owns:**
- `apps/web/**`

**Imports (read-only):**
- The API OpenAPI schema published by Agent 4 (generated TS client)

## Workspace-level (team-lead only)

- `README.md`
- `CLAUDE.md`
- `compose.yaml`
- `pyproject.toml` (root, workspace config)
- `pnpm-workspace.yaml`
- `.github/workflows/**`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.gitignore`
- `docs/decomposition-plan.md`
- `docs/file-ownership.md` (this file)

Changes to workspace-level files require a broadcast and team-lead approval before merge.

## Adding a new lane / file

If a new shared file is needed, the proposing agent must:
1. Open an issue tagged `ownership-add`
2. Team-lead assigns owner
3. Update this matrix in the same PR that introduces the file
4. Broadcast the change

No file gets two owners. If a file genuinely needs writes from two agents, extract a single-owner interface they both depend on (see `docs/decomposition-plan.md` § "Shared boundary files").
