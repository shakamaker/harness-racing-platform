param(
    [string]$State = "vic",
    [int]$YearStart = 1990,
    [int]$YearEnd = 2026,
    [int]$SleepSeconds = 300,
    [string]$Root = "C:\Users\franc\git\Chandon"
)

$py = "$Root\services\scraper\.venv\Scripts\python.exe"
$env:PYTHONPATH = "$Root\services\scraper\src;$Root\services\parser\src;$Root\packages\models\src"
$env:DATABASE_URL = "postgresql+psycopg://harness:harness_dev@localhost:55432/harness"

$cycle = 0
while ($true) {
    $cycle++
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$stamp] === cycle ${cycle}: db_ingest ==="
    & $py -m harness_scraper.db_ingest --state $State `
        --year-start $YearStart --year-end $YearEnd `
        --data-dir "$Root\data" --raw-dir "$Root\raw_html" 2>&1 |
        Select-String -Pattern '"overall"|"meetings_seen"|"meetings_upserted"|"tracks_upserted"|"years"' |
        ForEach-Object { Write-Host "  $($_.Line.Trim())" }

    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$stamp] === cycle ${cycle}: parsed_db_ingest ==="
    & $py -m harness_scraper.parsed_db_ingest --state $State `
        --year-start $YearStart --year-end $YearEnd 2>&1 |
        Select-String -Pattern '"meetings_attempted"|"meetings_parsed"|"meetings_failed"|"races"|"runners"|"race_times"' |
        ForEach-Object { Write-Host "  $($_.Line.Trim())" }

    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$stamp] === cycle ${cycle}: DB totals ==="
    $totals = docker exec harness-racing-platform-postgres-1 psql -U harness -d harness -t -c @"
SELECT format('races=%s runners=%s race_times=%s horses=%s persons=%s downloaded=%s parsed=%s',
    (SELECT COUNT(*) FROM races),
    (SELECT COUNT(*) FROM runners),
    (SELECT COUNT(*) FROM race_times),
    (SELECT COUNT(*) FROM horses),
    (SELECT COUNT(*) FROM persons),
    (SELECT COUNT(*) FROM race_meetings WHERE status='DOWNLOADED'),
    (SELECT COUNT(*) FROM race_meetings WHERE status='PARSED'));
"@
    Write-Host "  $($totals.Trim())"

    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host "[$stamp] sleeping ${SleepSeconds}s..."
    Start-Sleep -Seconds $SleepSeconds
}
