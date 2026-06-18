# Devpost Hackathon Notifier

Posts new and updated [Devpost](https://devpost.com) hackathons (Open, Upcoming, Closed) to your Discord server via webhooks. Runs free on GitHub Actions — no server, no Discord bot token, and no paid hosting required.

## What it does

1. **Fetches hackathons** from Devpost's public JSON API:
   - **Open** — accepting submissions now
   - **Upcoming** — not started yet
   - **Closed** — recently ended (last 3 pages only)

2. **Sends rich Discord embeds** with title, link, status, host, prizes, dates, location, time left, themes, and thumbnail.

3. **Avoids duplicate posts** using `state.json` — only notifies on new hackathons or status changes (e.g. Upcoming → Open, Open → Closed).

4. **Runs automatically** every 6 hours via GitHub Actions, or manually on your PC.

```
GitHub Actions / python main.py
        │
        ▼
    main.py ──► Devpost API
        │           │
        ├── state.json (dedupe)
        │
        └── Discord Webhook ──► #your-channel
```

## Project structure

| File | Purpose |
|------|---------|
| `main.py` | Core logic: fetch Devpost, decide what to post, send to Discord |
| `state.json` | Tracks known hackathons so nothing is posted twice |
| `.github/workflows/devpost-bot.yml` | Scheduled GitHub Actions workflow |
| `.gitignore` | Excludes secrets and Python cache from git |

## Requirements

- Python 3.9+ (stdlib only — no `pip install` needed)
- A Discord server with a webhook URL
- (Optional) A GitHub repo for free automated scheduling

## Quick start (GitHub Actions — recommended)

### 1. Create a Discord webhook

1. In Discord, open the target channel.
2. **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**.
3. Copy the webhook URL.

> **Keep this URL secret.** Anyone with it can post to your channel. Never commit it to git.

### 2. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Add Devpost hackathon notifier"
git remote add origin https://github.com/YOUR_USER/devpost-hackathon-notifier.git
git push -u origin main
```

### 3. Add the webhook as a GitHub secret

1. Open your repo on GitHub.
2. **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
3. Name: `DISCORD_WEBHOOK_URL`
4. Value: your Discord webhook URL.

### 4. Run the workflow

1. Go to the **Actions** tab.
2. Select **Devpost to Discord**.
3. Click **Run workflow**.

**First run (default):** Seeds `state.json` with current hackathons — no Discord messages (avoids spamming ~200 posts).

**To post all current hackathons once:** Run the workflow manually with **post_existing = true**.

After setup, the bot runs automatically every **6 hours (UTC)** and commits updated `state.json` to the repo.

## Run locally

```bash
cd devpost-hackathon-notifier

# First run — seed state without posting to Discord
python main.py

# Optional: post all current hackathons once
# Linux / macOS:
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export POST_EXISTING=1
python main.py

# Windows (cmd):
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
set POST_EXISTING=1
python main.py

# Normal run — only new or changed hackathons
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python main.py
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Yes (when posting) | Discord webhook URL for your channel |
| `POST_EXISTING` | No | Set to `1`, `true`, or `yes` to post all current hackathons instead of seed-only on first run |

## How notifications work

### First run — seed mode

When `state.json` is empty and `POST_EXISTING` is not set, the bot records all current hackathons without posting. This prevents flooding your channel on day one.

### Later runs

The bot posts to Discord when:

- A **new hackathon** appears on Devpost
- A **status changes** for a hackathon already in state (e.g. Open → Closed)

It skips hackathons that are unchanged since the last run.

### Discord message format

Each notification is a rich embed:

- **Title** — hackathon name (links to Devpost)
- **Status** — Open (green), Upcoming (yellow), Closed (red)
- **Host** and **prize pool**
- **Dates**, **location**, **time left**, **themes**
- **Thumbnail** — hackathon banner image

## Schedule

The default cron runs every 6 hours UTC:

```yaml
cron: "0 */6 * * *"
```

Edit `.github/workflows/devpost-bot.yml` to change the schedule. GitHub cron jobs may be delayed by 5–15 minutes.

## Important notes

- **Unofficial API** — This uses the same JSON endpoint as the Devpost website (`https://devpost.com/api/hackathons`). It is not an official Devpost API and may change.
- **Closed hackathons** — Only the 3 most recent pages of closed events are checked (thousands exist in total). You still get alerts for recently closed hackathons.
- **Rate limits** — The bot waits 1 second between Discord posts and 0.5 seconds between Devpost API pages.
- **Webhook security** — If your webhook URL is ever exposed, regenerate it in Discord immediately.
- **GitHub Actions** — Repos with no activity for 60 days may pause scheduled workflows. A small commit re-enables them.

## Cost

| Service | Cost |
|---------|------|
| Discord webhooks | Free |
| GitHub Actions (public repo) | Free |
| Devpost API | Free (no key required) |

## License

MIT
