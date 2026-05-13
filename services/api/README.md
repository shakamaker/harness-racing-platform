# api

FastAPI backend + par-times engine + SQL queries (CLAUDE.md §4.4). **Owner: Agent 4 (sql-pro).**

Sprint 0 stub:
- `GET /healthz` returns `{ok: true}` + DB ping
- `GET /meetings` returns paginated list (empty array OK)
- Settings via pydantic-settings
- OpenAPI exposed at `/openapi.json` for Agent 5's TS client generation
