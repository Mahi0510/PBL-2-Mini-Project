# Deployment Guide

## 1. Run with Docker (recommended)

```bash
cp .env.example .env        # fill in COMPANY_NAME, ADMIN_PASSWORD, SMTP_*
docker compose up -d --build
```

The app listens on port 8000. Candidate data (database + PDFs) lives in the `titan-data` Docker volume, so it survives restarts and upgrades.

## 2. Put it behind HTTPS (required for real candidate data)

Resumes contain personal data, so never expose the app over plain HTTP. Caddy gives you automatic HTTPS in three lines (`/etc/caddy/Caddyfile`):

```
jobs.yourcompany.com {
    reverse_proxy 127.0.0.1:8000
}
```

Then set in `.env`: `COOKIE_SECURE=true` and `TRUST_PROXY=true`, and restart.

## 3. Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `COMPANY_NAME` | Shown to candidates and in emails | `TITAN` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | HR login. Use a long password | random per run |
| `SMTP_HOST/PORT/USER/PASSWORD` | Outgoing email (Gmail needs an App Password) | Gmail, 587 |
| `COOKIE_SECURE` | `true` when served over HTTPS | `false` |
| `TRUST_PROXY` | `true` only behind your own proxy (reads client IP) | `false` |
| `SESSION_HOURS` | HR login lifetime | `8` |
| `RETENTION_DAYS` | Auto-delete applications older than this (0 = never) | `365` |
| `DATABASE_PATH`, `UPLOAD_DIR` | Storage locations | project folder |

## 4. Backups

Back up the `/data` volume (database + uploads) regularly:

```bash
docker run --rm -v titan-ats_titan-data:/data -v $(pwd):/backup alpine tar czf /backup/titan-$(date +%F).tgz /data
```

## 5. Limits to know about

* SQLite + one worker is fine for a small team (hundreds of applications a week). For many HR users or high volume, move to PostgreSQL.
* Email uses Gmail SMTP, which has daily sending limits. For volume, use a transactional provider (SES, SendGrid) via the same `SMTP_*` settings.
* Matching is keyword/TF-IDF based. It cannot judge seniority, context or quality of experience - this is why every decision stays with a human.
* Hosting platforms with ephemeral disks (e.g. free Render/Heroku tiers) will lose data on restart. Attach a persistent disk or use a VPS.
