# ADR 0001: PostgreSQL 16 as primary datastore

Date: 2026-05-13
Status: Accepted

## Context

The spec (§4.3.3) references INTERVAL types, NUMERIC(8,3) seconds with computed display columns, and a materialised view `mv_par_times` refreshed nightly. These are Postgres-flavoured features.

The system stores ~40 years × 12 months × 8 states of meetings (~40,000 meetings, ~400,000 races, ~4M runners). Workload is mixed OLTP (scraper/parser writes) + analytical (par-times computation, joins for form lines). A single Postgres instance handles this well into the future.

## Decision

PostgreSQL 16 is the canonical DB engine for all environments — dev, test, production. No SQLite fallback for dev (would split migration paths between INTERVAL and TEXT).

Local dev runs Postgres 16 in `compose.yaml`. CI spins up `postgres:16` as a service container.

## Consequences

- All `_ss_ms` columns: `NUMERIC(8,3)` storing seconds with millisecond precision, plus generated column for `SS:mmm` display string.
- `mv_par_times` materialised view, refreshed via cron + manual trigger from `/admin/refresh-pars`.
- Alembic migrations may use Postgres-only DDL (no SQLAlchemy generic-DB constraint).
- Developers must have Docker available locally.

## Rejected alternatives

- **SQLite for dev, Postgres prod:** rejected — materialised views and INTERVAL absent in SQLite, would require conditional migrations and divergent schemas. Confidence in CI/prod parity would suffer.
- **PostgreSQL 15:** functionally equivalent for our needs but 16 is current stable with better JSON path performance, useful for stewards-comment full-text and structured-data columns later.
