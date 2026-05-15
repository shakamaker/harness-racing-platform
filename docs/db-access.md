# Database Access

Local PostgreSQL 16 runs in Docker via `compose.yaml`. This doc covers everything you need to query, inspect, and reset it.

> **Host port note.** The container's internal port is still `5432`, but the host-side mapping in `compose.yaml` is now `55432:5432` to dodge a second Postgres already listening on host `5432` (which was silently answering auth challenges with auth failure). Inside the container nothing changed; from the host, always use `55432`.

## Connection facts

| Field    | Value                                              |
|----------|----------------------------------------------------|
| Host     | `localhost`                                        |
| Port     | `55432` (host) → `5432` (container)                |
| User     | `harness`                                          |
| Password | `harness_dev` (dev only)                           |
| Database | `harness`                                          |
| DSN (sync, psycopg)  | `postgresql+psycopg://harness:harness_dev@localhost:55432/harness` |
| DSN (async, asyncpg) | `postgresql+asyncpg://harness:harness_dev@localhost:55432/harness` |
| Container| `harness-racing-platform-postgres-1`               |
| Volume   | `pgdata` (Docker-managed; survives container restarts) |

Schema source of truth: `sql/schema.sql` (mirrored to `sql/migrations/0001_initial.sql`). ERD: `docs/erd/erd.dbml`.

---

## 1. Bring the DB up / verify health

```powershell
docker compose up -d postgres
docker compose ps
docker compose logs postgres --tail 50
```

The compose healthcheck shells out to `pg_isready -U harness -d harness` every 5s. Status column in `docker compose ps` should read `healthy`. If it sits on `starting` for more than ~30s, check the logs.

Manual healthcheck from the host:

```powershell
docker exec harness-racing-platform-postgres-1 pg_isready -U harness -d harness
```

---

## 2. Interactive psql shell inside the container

```powershell
docker exec -it harness-racing-platform-postgres-1 psql -U harness -d harness
```

Useful meta-commands once you're in:

| Command           | What it does                                            |
|-------------------|---------------------------------------------------------|
| `\dt`             | List tables (23 currently)                              |
| `\d <table>`      | Describe a table (columns, types, indexes, FKs)         |
| `\d+ races`       | Verbose describe — adds storage, comments, NULL stats   |
| `\dT`             | List user-defined types (the workflow ENUMs live here)  |
| `\dv`             | List views                                              |
| `\dm`             | List materialized views (`mv_par_times`)                |
| `\di`             | List indexes                                            |
| `\df`             | List functions                                          |
| `\l`              | List databases                                          |
| `\x auto`         | Auto-toggle expanded display for wide rows              |
| `\timing on`      | Show per-query elapsed time                             |
| `\e`              | Open last query in `$EDITOR`                            |
| `\q`              | Quit                                                    |

---

## 3. One-shot SQL from PowerShell

```powershell
docker exec harness-racing-platform-postgres-1 psql -U harness -d harness -c "SELECT count(*) FROM races;"
```

Script-friendly output (no headers, no padding) — useful when piping into other tools:

```powershell
docker exec harness-racing-platform-postgres-1 psql -U harness -d harness -Atc "SELECT count(*) FROM races;"
```

Run a SQL file. Two options:

```powershell
# Option A: pipe the file in via stdin (no mount needed)
Get-Content sql\queries\exploration.sql -Raw | docker exec -i harness-racing-platform-postgres-1 psql -U harness -d harness

# Option B: mount the repo into the container ad-hoc, then -f
docker run --rm -i `
  --network harness-racing-platform_default `
  -v ${PWD}:/work `
  -e PGPASSWORD=harness_dev `
  postgres:16 `
  psql -h harness-racing-platform-postgres-1 -U harness -d harness -f /work/sql/queries/exploration.sql
```

Files mounted into the long-running container directly via `-v` require a compose change, so stdin is usually faster for ad-hoc work.

---

## 4. Connect from the host

If you have native `psql` installed (e.g., via the Postgres client tools or `scoop install postgresql`):

```powershell
$env:PGPASSWORD = 'harness_dev'
psql -h localhost -p 55432 -U harness -d harness
```

If the host-port mapping is giving you trouble (e.g., another Postgres is squatting on the host), bypass it entirely by execing into the container:

```powershell
docker exec -it harness-racing-platform-postgres-1 psql -U harness -d harness
```

GUIs (TablePlus / DBeaver / pgAdmin / DataGrip) — paste the DSN:

```
postgresql://harness:harness_dev@localhost:55432/harness
```

or fill in the fields from the table at the top of this doc.

`PGPASSWORD` survives the PowerShell session; clear it with `Remove-Item Env:PGPASSWORD` when done.

---

## 5. Connect from Python (SQLAlchemy 2.x)

The project uses SQLAlchemy 2.x with `psycopg` (v3). Use the `postgresql+psycopg://` driver prefix:

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DSN = "postgresql+psycopg://harness:harness_dev@localhost:55432/harness"
engine = create_engine(DSN, echo=False, pool_pre_ping=True)

with Session(engine) as session:
    rows = session.execute(text("SELECT meeting_code, meeting_date FROM race_meetings ORDER BY meeting_date DESC LIMIT 5")).all()
    for r in rows:
        print(r)
```

ORM models live under `packages/models/src/harness_models/` — import them directly:

```python
from harness_models.meetings import RaceMeeting
from harness_models.races import Race

with Session(engine) as session:
    meeting = session.get(RaceMeeting, 1)
```

---

## 6. Calendar → DB ingest (`harness_scraper.db_ingest`)

The calendar→DB handshake lives in `services/scraper/src/harness_scraper/db_ingest.py`. It reads the per-year manifests written by the calendar scraper at `data/calendar/{state}/{year}.json` and upserts:

- `race_tracks` — keyed on `(track_name, state_id)`, cached per process so it's idempotent within a run.
- `race_meetings` — keyed on `meeting_code`, via PG `ON CONFLICT DO UPDATE`. `status` is set to `DOWNLOADED` when the per-meeting HTML already exists at `raw_html/{state}/{year}/{mc}.html`, otherwise `PENDING_DOWNLOAD`.

Invocation (PowerShell, from the repo root):

```powershell
$env:PYTHONPATH = "C:\Users\franc\git\Chandon\services\scraper\src;C:\Users\franc\git\Chandon\packages\models\src"
$env:DATABASE_URL = "postgresql+psycopg://harness:harness_dev@localhost:55432/harness"
& python -m harness_scraper.db_ingest --state vic --year-start 1986 --year-end 1990 `
    --data-dir "C:\Users\franc\git\Chandon\data" `
    --raw-dir "C:\Users\franc\git\Chandon\raw_html"
```

Proof-of-life from today: pumping VIC 1986–1990 produced **54 `race_tracks`** + **3,261 `race_meetings`** rows (Moonee Valley top track at 455 meetings across 5 years), with FKs linking cleanly through to `states` / `countries`. The 3NF schema + ORM handle real ingested data without modification.

---

## 7. Resetting / re-applying the schema

`sql/schema.sql` wraps everything in a `BEGIN; ... COMMIT;` block, so a re-apply is atomic.

### Soft reset — drop + recreate the database (keeps the container + volume)

Destroys all data. Use when you want a clean slate but don't want to lose the Docker volume.

```powershell
docker exec harness-racing-platform-postgres-1 psql -U harness -d postgres -c "DROP DATABASE harness;"
docker exec harness-racing-platform-postgres-1 psql -U harness -d postgres -c "CREATE DATABASE harness OWNER harness;"
Get-Content sql\schema.sql -Raw | docker exec -i harness-racing-platform-postgres-1 psql -U harness -d harness
```

### Hard reset — destroy the container *and* the volume

```powershell
docker compose down -v       # WARNING: removes the pgdata volume. All data gone.
docker compose up -d postgres
Get-Content sql\schema.sql -Raw | docker exec -i harness-racing-platform-postgres-1 psql -U harness -d harness
```

### Stop without losing data

```powershell
docker compose down          # preserves the pgdata volume; data survives a re-up
```

---

## 8. Refreshing the materialized view

`mv_par_times` is created `WITH NO DATA`, so the **first refresh must be non-concurrent** to populate it. After that you can use `CONCURRENTLY` (the required unique index `uq_mv_par_times_group` already exists).

```sql
-- First time only:
REFRESH MATERIALIZED VIEW mv_par_times;

-- Subsequent refreshes (does not block readers):
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_par_times;
```

From PowerShell:

```powershell
docker exec harness-racing-platform-postgres-1 psql -U harness -d harness -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_par_times;"
```

Querying the view before the first refresh raises `permission denied for materialized view mv_par_times` (Postgres's error for an unpopulated matview). Refresh once and the message goes away.

---

## 9. Backup / restore

Plain SQL dump (portable, slow, human-readable):

```powershell
docker exec harness-racing-platform-postgres-1 pg_dump -U harness -d harness -F p > backup.sql
```

Custom format (compressed, parallel-restorable):

```powershell
docker exec harness-racing-platform-postgres-1 pg_dump -U harness -d harness -F c -f /tmp/harness.dump
docker cp harness-racing-platform-postgres-1:/tmp/harness.dump .\harness.dump
```

Restore custom-format dump into a fresh DB:

```powershell
docker cp .\harness.dump harness-racing-platform-postgres-1:/tmp/harness.dump
docker exec harness-racing-platform-postgres-1 pg_restore -U harness -d harness --clean --if-exists /tmp/harness.dump
```

Plain SQL restore:

```powershell
Get-Content backup.sql -Raw | docker exec -i harness-racing-platform-postgres-1 psql -U harness -d harness
```

---

## 10. Troubleshooting

**Container isn't running.**

```powershell
docker compose ps
docker compose up -d postgres
docker compose logs postgres --tail 100
```

**Port 55432 already taken on the host.** Find the conflicting process and either stop it or change the host-side port in `compose.yaml` (e.g., `"55433:5432"`). The original `5432:5432` mapping was abandoned because a second Postgres on the host was intercepting connections and returning auth failures — if you're seeing mysterious auth errors, double-check nothing else is listening on `55432` either.

```powershell
Get-NetTCPConnection -LocalPort 55432 -ErrorAction SilentlyContinue | Select-Object -Property State, OwningProcess
Get-Process -Id <PID>
```

**`permission denied for materialized view mv_par_times`** — `mv_par_times` was created `WITH NO DATA` and has never been refreshed. Run `REFRESH MATERIALIZED VIEW mv_par_times;` (non-concurrent) once. See §8.

**Single quotes inside `-c "..."` get mangled on Windows.** PowerShell parses the double-quoted string before Docker sees it. Three workarounds:

```powershell
# 1. Use a here-string and stdin:
@"
SELECT meeting_code FROM race_meetings WHERE state_id = 1;
"@ | docker exec -i harness-racing-platform-postgres-1 psql -U harness -d harness

# 2. Escape with backtick-quoting:
docker exec harness-racing-platform-postgres-1 psql -U harness -d harness -c "SELECT 'hello' AS msg;"

# 3. Drop into the interactive shell (§2).
```

**Connection refused from the host.** The container reports healthy but `psql -h localhost -p 55432` hangs or refuses — check that the port mapping line in `compose.yaml` is intact (`- "55432:5432"`) and that Docker Desktop is forwarding the port. `docker compose ps` shows the binding.

**`role "harness" does not exist` after a `down -v`.** The volume was destroyed but the container started before the env vars were re-applied. `docker compose down` then `docker compose up -d postgres` to re-init from `POSTGRES_USER`/`POSTGRES_DB`.
