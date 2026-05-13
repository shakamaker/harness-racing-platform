# scraper

Playwright async crawler with anti-bot subterfuge (CLAUDE.md §4.1). **Owner: Agent 1.**

Sprint 0 stub:
- Playwright launches Chromium headless
- Fetches one VIC monthly results page
- Asserts `<table class="meetingListFull">` exists
- Logs structured JSON with meeting count
- Does NOT write to DB yet
