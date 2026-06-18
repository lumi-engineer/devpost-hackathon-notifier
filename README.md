# Devpost Hackathon Notifier

Syncs **Open** and **Upcoming** [Devpost](https://devpost.com) hackathons to Discord channels sorted by prize tier. Runs once daily on GitHub Actions — delete old posts and repost fresh sorted embeds each run.

## What it does

1. Fetches all **Open** and **Upcoming** hackathons from Devpost.
2. Parses prize amounts and assigns each hackathon to a tier:
   - **A — $100k+**
   - **B — $10k–$100k**
   - **C — Under $10k**
   - **D — Free** ($0)
3. Sorts hackathons **highest prize first** within each tier.
4. Posts **one embed per hackathon** to the matching Discord channel.
5. On each daily run: **deletes previous bot messages** in each channel and **reposts** the full sorted list.

```
Daily GitHub Action
        │
        ▼
    main.py ──► Devpost API (open + upcoming)
        │
        ├── Sort by prize tier
        │
        ├── Delete old Discord messages (state.json)
        │
        └── Repost sorted embeds ──► 4 Discord channels
```

## Project structure

| File | Purpose |
|------|---------|
| `main.py` | Fetch, sort, delete old posts, repost embeds |
| `channels.json` | Prize tier definitions and webhook env var names |
| `state.json` | Stores Discord message IDs per tier for cleanup |
| `.env.example` | Template for local webhook URLs |
| `.github/workflows/devpost-bot.yml` | Daily scheduled workflow |

## Discord setup

Create **4 channels** and one webhook each:

| Channel | Tier | GitHub secret |
|---------|------|---------------|
| A - level | $100k+ | `WEBHOOK_100K_PLUS` |
| B - level | $10k–$100k | `WEBHOOK_10K_100K` |
| C - level | Under $10k | `WEBHOOK_UNDER_10K` |
| D - level | Free | `WEBHOOK_FREE` |

> **Never commit webhook URLs to git.** Use GitHub Secrets or a local `.env` file.

## GitHub Actions setup

1. Push this repo to GitHub.
2. Add four repository secrets under **Settings → Secrets → Actions**:
   - `WEBHOOK_100K_PLUS`
   - `WEBHOOK_10K_100K`
   - `WEBHOOK_UNDER_10K`
   - `WEBHOOK_FREE`
3. Enable **Actions** and run **Devpost to Discord** manually once to test.
4. The workflow runs automatically **every day at 09:00 UTC**.

## Run locally

```bash
# Copy template and fill in your webhook URLs
cp .env.example .env

# Linux / macOS — load .env then run
set -a && source .env && set +a
python main.py

# Windows (PowerShell)
Get-Content .env | ForEach-Object {
  if ($_ -match '^([^#=]+)=(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}
python main.py
```

Each run deletes previous messages in all four channels and reposts the current sorted list.

## How sorting works

| Prize parsed | Tier | Channel |
|--------------|------|---------|
| ≥ $100,000 | `100k_plus` | A - level |
| $10,000 – $99,999 | `10k_100k` | B - level |
| $1 – $9,999 | `under_10k` | C - level |
| $0 | `free` | D - level |

Prizes are parsed from Devpost's `prize_amount` field. Non-USD values use the numeric amount for tier assignment.

## Discord message format

Each hackathon gets one embed with:

- Title (linked to Devpost)
- Tier, rank by prize, status (Open / Upcoming)
- Host, prizes, dates, location, time left, themes
- Thumbnail banner

## Schedule

Default: **once per day at 09:00 UTC** (`0 9 * * *`).

Edit `.github/workflows/devpost-bot.yml` to change the time.

## Run duration

| Step | Approximate time |
|------|------------------|
| Fetch Devpost data | ~1–2 minutes |
| Delete + repost ~170 embeds | ~5–6 minutes |
| **Total** | **~6–8 minutes** |

The bot waits 1 second between Discord API calls to avoid rate limits.

## Important notes

- **Full refresh daily** — old messages are deleted and replaced, not edited in place.
- **Open + Upcoming only** — closed/ended hackathons are not included.
- **No region filtering** — all locations appear in the price tier channels.
- **Unofficial API** — uses `https://devpost.com/api/hackathons` (same as the Devpost website).
- **Webhook security** — regenerate webhooks if URLs are ever exposed publicly.

## Cost

| Service | Cost |
|---------|------|
| Discord webhooks | Free |
| GitHub Actions | Free tier sufficient |
| Devpost API | Free |

## License

MIT
