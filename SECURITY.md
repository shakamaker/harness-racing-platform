# Security Policy

`harness-racing-platform` operates on a **security-first** basis. We treat
security defects as the highest-priority class of bug, ahead of features and
performance work.

## Supported versions

The project is pre-1.0. Until a tagged release exists, only the `main` branch
is "supported" for security fixes — please ensure you are running the latest
`main` (or a commit no more than 7 days behind) before reporting.

| Version  | Supported          |
| -------- | ------------------ |
| `main`   | :white_check_mark: |
| `develop`| :white_check_mark: |
| any other branch / fork | :x: |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**
Public disclosure before a fix is available exposes every operator of the
platform to the same defect.

Use one of the following private channels, in order of preference:

1. **GitHub Private Vulnerability Reporting** (preferred) — open a private
   security advisory at
   <https://github.com/shakamaker/harness-racing-platform/security/advisories/new>.
   This is encrypted in transit, scoped to the maintainers, and gives us a
   private fork to develop the fix on.
2. **Email** — write to the repository owner via the email listed on their
   GitHub profile. Use subject prefix `[security]`. PGP welcome but not
   required.

When reporting, please include:

- A description of the vulnerability and its impact (what an attacker can do).
- The affected component (`services/scraper`, `services/api`,
  `packages/models`, `apps/web`, CI workflow, dependency, etc.).
- The commit SHA you observed the issue on.
- Reproduction steps (proof-of-concept code, request payload, etc.).
- Your proposed severity (CVSS or informal — we'll re-score).
- Whether you want public credit in the advisory.

## Our response

We aim to:

- Acknowledge receipt within **2 business days**.
- Triage and confirm (or rebut) the report within **7 calendar days**.
- Ship a fix for **critical/high** issues within **30 days** of confirmation.
- Ship a fix for **medium/low** issues within **90 days** of confirmation.
- Coordinate public disclosure with the reporter, with a default 90-day
  embargo after a fix is released.

We will keep you updated on progress. If you do not hear back within the
acknowledgement window, please escalate by reopening the channel.

## Out of scope

The following are explicitly **not** in scope for this security policy
(though we still appreciate the report — please use a regular issue):

- Findings that require physical access to a maintainer's machine.
- Findings in dependencies for which an upstream fix already exists — please
  let Dependabot raise the bump PR.
- Theoretical issues without a demonstrated impact (e.g. "this header could
  be tighter").
- Vulnerabilities in **third-party** services we scrape from (report those
  directly to the operator of that service).
- Compliance gaps that are already tracked in our compliance ADR
  (`docs/adr/` once published) — those are known.

## Safe harbour

We will not pursue legal action against researchers who:

- Make a good-faith effort to comply with this policy.
- Avoid violating the privacy of users (incl. drivers, trainers, horse owners).
- Avoid destroying data or degrading the service for other users.
- Do not exfiltrate data beyond the minimum needed to demonstrate the issue.
- Give us reasonable time to respond before any disclosure.

## Hall of fame

Researchers who report valid vulnerabilities will be credited in the
corresponding GitHub Security Advisory (unless they request anonymity).
