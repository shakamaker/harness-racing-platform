-- ============================================================================
-- exploration.sql
-- ============================================================================
-- Interactive exploration queries for the harness racing schema.
--
-- NOT production endpoint SQL. Endpoint queries will be hand-tuned per route
-- under sql/queries/<endpoint>.sql once Agent 4 (sql-pro) starts on the API.
--
-- HOW TO RUN
-- ----------
--   These queries use psql variables (\set foo 'bar'). Running the whole file
--   with `psql -f sql/queries/exploration.sql` will execute every query with
--   placeholder values and most will return 0 rows. Recommended workflow:
--
--     1. Open a psql shell:
--          docker exec -it harness-racing-platform-postgres-1 \
--              psql -U harness -d harness
--     2. Set the variables you care about for the next query, e.g.:
--          \set meeting_code 'C12345'
--          \set race_id 42
--          \set horse_id 123456
--          \set track_id 1
--          \set from_date '2024-01-01'
--          \set to_date   '2024-12-31'
--     3. Copy-paste a single query block (between the banners) and run it.
--
-- Conventions
-- -----------
--   * Uppercase SQL keywords (matches sql/schema.sql).
--   * Explicit INNER JOIN / LEFT JOIN — no comma joins.
--   * Each block is self-contained and ends with a semicolon.
--   * Queries on empty tables return 0 rows cleanly; nothing here errors on
--     an unpopulated DB (current state: 1 meeting, 11 races, no runners).
-- ============================================================================


-- ============================================================================
-- 1. Meetings overview
-- ============================================================================
-- intent: every meeting joined to track/state/country with a race count.
-- Useful first sanity check after the scraper drops new rows.
SELECT
    m.meeting_code,
    m.meeting_date,
    m.day_night,
    m.status,
    t.track_name,
    s.code               AS state_code,
    c.code               AS country_code,
    COUNT(r.id)          AS races_count
FROM race_meetings        m
INNER JOIN race_tracks    t ON t.id = m.track_id
INNER JOIN states         s ON s.id = t.state_id
INNER JOIN countries      c ON c.id = s.country_id
LEFT  JOIN races          r ON r.meeting_id = m.id
GROUP BY
    m.id,
    m.meeting_code,
    m.meeting_date,
    m.day_night,
    m.status,
    t.track_name,
    s.code,
    c.code
ORDER BY m.meeting_date DESC, t.track_name;


-- ============================================================================
-- 2. Race card for a meeting
-- ============================================================================
-- intent: list every race for one meeting with all categorical labels resolved.
-- Set: \set meeting_code 'XXXXXXX'
SELECT
    r.race_number,
    r.race_name,
    r.distance_m,
    rg.name              AS gait,
    st.name              AS start_type,
    rc.name              AS race_class,
    ac.name              AS age_class,
    rt.name              AS race_type,
    tc.name              AS track_condition,
    r.race_purse,
    r.race_time_str,
    r.is_final
FROM race_meetings        m
INNER JOIN races          r  ON r.meeting_id        = m.id
LEFT  JOIN race_gaits     rg ON rg.id               = r.race_gait_id
LEFT  JOIN start_types    st ON st.id               = r.start_type_id
LEFT  JOIN race_classes   rc ON rc.id               = r.race_class_id
LEFT  JOIN age_classes    ac ON ac.id               = r.age_class_id
LEFT  JOIN race_types     rt ON rt.id               = r.race_type_id
LEFT  JOIN track_conditions tc ON tc.id             = r.track_condition_id
WHERE m.meeting_code = :'meeting_code'
ORDER BY r.race_number;


-- ============================================================================
-- 3. Race result lines
-- ============================================================================
-- intent: final field for one race with finish order, trainer, driver, margin,
-- stake, price. Scratched runners are surfaced via a flag column and pushed
-- to the bottom of the ordering so they remain visible.
-- Set: \set race_id 42
SELECT
    r.finish_position,
    r.scratched,
    r.runner_number,
    h.horse_name,
    r.barrier_raw,
    trainer.name         AS trainer,
    driver.name          AS driver,
    r.raw_margin,
    r.adjusted_margin,
    r.stake,
    r.raw_price,
    r.starting_price,
    r.null_run
FROM runners              r
INNER JOIN horses         h       ON h.horse_id = r.horse_id
LEFT  JOIN persons        trainer ON trainer.id = r.trainer_id
LEFT  JOIN persons        driver  ON driver.id  = r.driver_id
WHERE r.race_id = :race_id
ORDER BY
    r.scratched ASC,            -- false (active) before true (scratched)
    r.finish_position ASC NULLS LAST,
    r.runner_number ASC;


-- ============================================================================
-- 4. Horse form lines (recent starts)
-- ============================================================================
-- intent: last 20 starts for a horse across all meetings. Foundation for the
-- /horses/{horse_id}/form endpoint and for eyeballing a horse's recent record.
-- Set: \set horse_id 123456
SELECT
    m.meeting_date,
    t.track_name,
    r.race_number,
    r.distance_m,
    rg.name              AS gait,
    st.name              AS start_type,
    run.finish_position,
    run.raw_margin,
    run.stake,
    run.starting_price,
    rt.gross_time_s,
    rt.mile_rate_s
FROM runners              run
INNER JOIN races          r  ON r.id           = run.race_id
INNER JOIN race_meetings  m  ON m.id           = r.meeting_id
INNER JOIN race_tracks    t  ON t.id           = m.track_id
LEFT  JOIN race_gaits     rg ON rg.id          = r.race_gait_id
LEFT  JOIN start_types    st ON st.id          = r.start_type_id
LEFT  JOIN race_times     rt ON rt.race_id     = r.id
WHERE run.horse_id  = :horse_id
  AND run.scratched = false
ORDER BY m.meeting_date DESC, r.race_number DESC
LIMIT 20;


-- ============================================================================
-- 5. Driver leaderboard for a date range
-- ============================================================================
-- intent: top 20 drivers by wins inside a date window with placings and rates.
-- Win/place rates rendered as percentages rounded to 1 dp.
-- Set: \set from_date '2024-01-01'
--      \set to_date   '2024-12-31'
SELECT
    p.id                                                       AS driver_id,
    p.name                                                     AS driver,
    COUNT(*)                                                   AS drives,
    COUNT(*) FILTER (WHERE run.finish_position = 1)            AS wins,
    COUNT(*) FILTER (WHERE run.finish_position BETWEEN 1 AND 3) AS placings,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE run.finish_position = 1)
              / NULLIF(COUNT(*), 0),
        1
    )                                                          AS win_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE run.finish_position BETWEEN 1 AND 3)
              / NULLIF(COUNT(*), 0),
        1
    )                                                          AS place_pct
FROM runners              run
INNER JOIN persons        p ON p.id = run.driver_id
INNER JOIN races          r ON r.id = run.race_id
INNER JOIN race_meetings  m ON m.id = r.meeting_id
WHERE m.meeting_date BETWEEN :'from_date'::date AND :'to_date'::date
  AND run.scratched = false
GROUP BY p.id, p.name
HAVING COUNT(*) FILTER (WHERE run.finish_position = 1) > 0
ORDER BY wins DESC, win_pct DESC
LIMIT 20;


-- ============================================================================
-- 6. Trainer leaderboard for a date range
-- ============================================================================
-- intent: same shape as #5 but aggregated on trainer_id.
-- Set: \set from_date '2024-01-01'
--      \set to_date   '2024-12-31'
SELECT
    p.id                                                       AS trainer_id,
    p.name                                                     AS trainer,
    COUNT(*)                                                   AS starters,
    COUNT(*) FILTER (WHERE run.finish_position = 1)            AS wins,
    COUNT(*) FILTER (WHERE run.finish_position BETWEEN 1 AND 3) AS placings,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE run.finish_position = 1)
              / NULLIF(COUNT(*), 0),
        1
    )                                                          AS win_pct,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE run.finish_position BETWEEN 1 AND 3)
              / NULLIF(COUNT(*), 0),
        1
    )                                                          AS place_pct
FROM runners              run
INNER JOIN persons        p ON p.id = run.trainer_id
INNER JOIN races          r ON r.id = run.race_id
INNER JOIN race_meetings  m ON m.id = r.meeting_id
WHERE m.meeting_date BETWEEN :'from_date'::date AND :'to_date'::date
  AND run.scratched = false
GROUP BY p.id, p.name
HAVING COUNT(*) FILTER (WHERE run.finish_position = 1) > 0
ORDER BY wins DESC, win_pct DESC
LIMIT 20;


-- ============================================================================
-- 7. Times analytics per track + distance + gait + start_type
-- ============================================================================
-- intent: sanity-check distribution of race times before mv_par_times has data.
-- Useful for picking groupings with enough samples to trust the trimmed mean.
-- Set: \set track_id 1
SELECT
    r.distance_m,
    rg.name              AS gait,
    st.name              AS start_type,
    COUNT(*)             AS races,
    ROUND(AVG(rt.gross_time_s),  3) AS avg_gross_s,
    ROUND(MIN(rt.gross_time_s),  3) AS min_gross_s,
    ROUND(MAX(rt.gross_time_s),  3) AS max_gross_s,
    ROUND(AVG(rt.mile_rate_s),   3) AS avg_mile_rate_s,
    ROUND(MIN(rt.mile_rate_s),   3) AS min_mile_rate_s,
    ROUND(MAX(rt.mile_rate_s),   3) AS max_mile_rate_s
FROM races                r
INNER JOIN race_meetings  m  ON m.id           = r.meeting_id
INNER JOIN race_times     rt ON rt.race_id     = r.id
LEFT  JOIN race_gaits     rg ON rg.id          = r.race_gait_id
LEFT  JOIN start_types    st ON st.id          = r.start_type_id
WHERE m.track_id = :track_id
  AND r.distance_m IS NOT NULL
GROUP BY r.distance_m, rg.name, st.name
ORDER BY r.distance_m, rg.name, st.name;


-- ============================================================================
-- 8. Stewards comments with codes for a race
-- ============================================================================
-- intent: runners that earned any stewards comment for one race, with the
-- code list flattened to a comma-separated string and the free-text body.
-- Set: \set race_id 42
SELECT
    run.finish_position,
    h.horse_name,
    string_agg(sc.code, ', ' ORDER BY sc.code) AS code_list,
    cmt.full_text
FROM stewards_comments    cmt
INNER JOIN runners        run ON run.id        = cmt.runner_id
INNER JOIN horses         h   ON h.horse_id    = run.horse_id
LEFT  JOIN stewards_comment_codes scc ON scc.runner_id = cmt.runner_id
LEFT  JOIN stewards_codes sc  ON sc.id         = scc.code_id
WHERE run.race_id = :race_id
GROUP BY
    run.finish_position,
    h.horse_name,
    cmt.full_text,
    run.id
ORDER BY run.finish_position NULLS LAST, h.horse_name;
