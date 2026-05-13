# harness_models

SQLAlchemy 2.x ORM + Pydantic schemas + Alembic migrations. **Owner: Agent 3 (database-architect).**

Other agents import from `harness_models` but **do not modify this package**. Contract changes require an issue tagged `contract-change` and Agent 3 approval.

Sprint 0 deliverables:
- All tables from CLAUDE.md §4.3.2 declared as typed SQLAlchemy 2.x models
- Alembic baseline migration that applies clean to empty Postgres 16
- Pydantic models for API/parser DTOs
- ERD published to `docs/erd/erd.png` + `docs/erd/erd.dbml`
- Public API exposed via `__init__.py` (this file is owner-only)
