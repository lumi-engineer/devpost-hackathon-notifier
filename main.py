"""Post Devpost hackathon updates (open, upcoming, ended) to a Discord webhook."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEVPOST_API = "https://devpost.com/api/hackathons"
STATUSES = ("open", "upcoming", "ended")
# Ended hackathons number in the thousands; only check recent pages.
MAX_ENDED_PAGES = 3
STATE_FILE = Path(__file__).resolve().parent / "state.json"

STATUS_COLORS = {
    "open": 0x57F287,
    "upcoming": 0xFEE75C,
    "ended": 0xED4245,
}

STATUS_LABELS = {
    "open": "Open",
    "upcoming": "Upcoming",
    "ended": "Closed",
}

USER_AGENT = "devpost-hackathon-notifier/1.0 (+https://github.com/devpost-hackathon-notifier)"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"hackathons": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fetch_page(status: str, page: int) -> list[dict]:
    url = f"{DEVPOST_API}?status={status}&page={page}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("hackathons", [])


def fetch_all_for_status(status: str) -> list[dict]:
    hackathons: list[dict] = []
    page = 1
    max_pages = MAX_ENDED_PAGES if status == "ended" else None

    while True:
        batch = fetch_page(status, page)
        if not batch:
            break
        hackathons.extend(batch)
        if max_pages is not None and page >= max_pages:
            break
        page += 1
        time.sleep(0.5)

    return hackathons


def clean_prize_amount(raw: str | None) -> str:
    if not raw:
        return "N/A"
    text = re.sub(r"<[^>]+>", "", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "N/A"


def thumbnail_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("//"):
        return f"https:{raw}"
    if raw.startswith("http"):
        return raw
    return None


def should_notify(hackathon: dict, state: dict) -> bool:
    hackathon_id = str(hackathon["id"])
    current_status = hackathon["open_state"]
    known = state["hackathons"].get(hackathon_id)

    if known is None:
        return True

    return known.get("status") != current_status


def record_hackathon(hackathon: dict, state: dict) -> None:
    hackathon_id = str(hackathon["id"])
    state["hackathons"][hackathon_id] = {
        "status": hackathon["open_state"],
        "title": hackathon.get("title", ""),
        "url": hackathon.get("url", ""),
    }


def build_embed(hackathon: dict) -> dict:
    status = hackathon["open_state"]
    status_label = STATUS_LABELS.get(status, status.title())
    location = hackathon.get("displayed_location", {}).get("location", "N/A")
    themes = ", ".join(theme["name"] for theme in hackathon.get("themes", [])[:4]) or "N/A"
    prize = clean_prize_amount(hackathon.get("prize_amount"))
    organization = hackathon.get("organization_name") or "N/A"

    embed: dict = {
        "title": hackathon["title"][:256],
        "url": hackathon["url"],
        "color": STATUS_COLORS.get(status, 0x5865F2),
        "description": (
            f"**Status:** {status_label}\n"
            f"**Host:** {organization}\n"
            f"**Prizes:** {prize}"
        ),
        "fields": [
            {
                "name": "Dates",
                "value": hackathon.get("submission_period_dates", "N/A")[:1024],
                "inline": True,
            },
            {
                "name": "Location",
                "value": location[:1024],
                "inline": True,
            },
            {
                "name": "Time left",
                "value": hackathon.get("time_left_to_submission", "N/A")[:1024],
                "inline": True,
            },
            {
                "name": "Themes",
                "value": themes[:1024],
                "inline": False,
            },
        ],
        "footer": {"text": "Devpost Hackathon Notifier"},
    }

    thumb = thumbnail_url(hackathon.get("thumbnail_url"))
    if thumb:
        embed["thumbnail"] = {"url": thumb}

    return embed


def post_to_discord(webhook_url: str, embed: dict) -> None:
    payload = json.dumps({"embeds": [embed]}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 400:
            raise urllib.error.HTTPError(
                request.full_url,
                response.status,
                response.reason,
                response.headers,
                None,
            )


def seed_state(state: dict) -> int:
    count = 0
    for status in STATUSES:
        for hackathon in fetch_all_for_status(status):
            record_hackathon(hackathon, state)
            count += 1
    return count


def run() -> int:
    state = load_state()
    is_first_run = not state["hackathons"]
    post_existing = os.environ.get("POST_EXISTING", "").lower() in ("1", "true", "yes")

    if is_first_run and not post_existing:
        seeded = seed_state(state)
        save_state(state)
        print(f"First run: seeded {seeded} hackathons without posting.")
        print("Re-run with POST_EXISTING=1 to post current hackathons to Discord.")
        return 0

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL is not set.", file=sys.stderr)
        return 1

    posted = 0
    for status in STATUSES:
        for hackathon in fetch_all_for_status(status):
            if should_notify(hackathon, state):
                embed = build_embed(hackathon)
                post_to_discord(webhook_url, embed)
                posted += 1
                print(f"Posted: [{hackathon['open_state']}] {hackathon['title']}")
                time.sleep(1.0)
            record_hackathon(hackathon, state)

    save_state(state)
    print(f"Done. Posted {posted} update(s). Tracking {len(state['hackathons'])} hackathon(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
