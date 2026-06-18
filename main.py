"""Sync Devpost open/upcoming hackathons to Discord channels by prize tier."""

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
STATUSES = ("open", "upcoming")
ROOT = Path(__file__).resolve().parent
CHANNELS_FILE = ROOT / "channels.json"
STATE_FILE = ROOT / "state.json"

STATUS_COLORS = {
    "open": 0x57F287,
    "upcoming": 0xFEE75C,
}

STATUS_LABELS = {
    "open": "Open",
    "upcoming": "Upcoming",
}

USER_AGENT = "devpost-hackathon-notifier/2.0"
POST_DELAY_SECONDS = 1.0
API_PAGE_DELAY_SECONDS = 0.5


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return load_json(STATE_FILE)
    return {"tiers": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_tier_config() -> list[dict]:
    config = load_json(CHANNELS_FILE)
    return config["tiers"]


def webhook_for_tier(tier: dict) -> str:
    env_name = tier["webhook_env"]
    url = os.environ.get(env_name, "").strip()
    if not url:
        raise RuntimeError(f"Missing environment variable: {env_name}")
    return url


def fetch_page(status: str, page: int) -> list[dict]:
    url = f"{DEVPOST_API}?status={status}&page={page}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("hackathons", [])


def fetch_all_hackathons() -> list[dict]:
    hackathons: list[dict] = []
    seen_ids: set[int] = set()

    for status in STATUSES:
        page = 1
        while True:
            batch = fetch_page(status, page)
            if not batch:
                break
            for hackathon in batch:
                hackathon_id = hackathon["id"]
                if hackathon_id not in seen_ids:
                    seen_ids.add(hackathon_id)
                    hackathons.append(hackathon)
            page += 1
            time.sleep(API_PAGE_DELAY_SECONDS)

    return hackathons


def parse_prize_amount(raw: str | None) -> int:
    if not raw:
        return 0

    match = re.search(r"data-currency-value[^>]*>([\d,]+)", raw)
    if match:
        return int(match.group(1).replace(",", ""))

    text = re.sub(r"<[^>]+>", "", raw)
    numbers = re.findall(r"[\d,]+", text)
    if numbers:
        return int(numbers[0].replace(",", ""))
    return 0


def classify_tier(prize: int) -> str:
    if prize >= 100_000:
        return "100k_plus"
    if prize >= 10_000:
        return "10k_100k"
    if prize > 0:
        return "under_10k"
    return "free"


def embed_text(value: str | None, fallback: str = "N/A") -> str:
    text = (value or "").strip()
    return text[:1024] if text else fallback


def clean_prize_display(raw: str | None, prize: int) -> str:
    if prize == 0:
        return "Free / no cash prizes"
    if raw:
        text = re.sub(r"<[^>]+>", "", raw)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            return text
    return f"${prize:,}"


def thumbnail_url(raw: str | None) -> str | None:
    if not raw:
        return None
    if raw.startswith("//"):
        return f"https:{raw}"
    if raw.startswith("http"):
        return raw
    return None


def bucket_hackathons(hackathons: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {
        "100k_plus": [],
        "10k_100k": [],
        "under_10k": [],
        "free": [],
    }

    for hackathon in hackathons:
        prize = parse_prize_amount(hackathon.get("prize_amount"))
        hackathon["_prize_value"] = prize
        tier_id = classify_tier(prize)
        buckets[tier_id].append(hackathon)

    for tier_id in buckets:
        buckets[tier_id].sort(key=lambda item: item["_prize_value"], reverse=True)

    return buckets


def build_embed(hackathon: dict, tier_label: str, rank: int) -> dict:
    status = hackathon["open_state"]
    status_label = STATUS_LABELS.get(status, status.title())
    location = embed_text(hackathon.get("displayed_location", {}).get("location"))
    themes = embed_text(", ".join(theme["name"] for theme in hackathon.get("themes", [])[:4]))
    prize = clean_prize_display(hackathon.get("prize_amount"), hackathon["_prize_value"])
    organization = hackathon.get("organization_name") or "N/A"

    embed: dict = {
        "title": hackathon["title"][:256],
        "url": hackathon["url"],
        "color": STATUS_COLORS.get(status, 0x5865F2),
        "description": (
            f"**Tier:** {tier_label}\n"
            f"**Rank:** #{rank} by prize\n"
            f"**Status:** {status_label}\n"
            f"**Host:** {organization}\n"
            f"**Prizes:** {prize}"
        ),
        "fields": [
            {
                "name": "Dates",
                "value": embed_text(hackathon.get("submission_period_dates")),
                "inline": True,
            },
            {
                "name": "Location",
                "value": location,
                "inline": True,
            },
            {
                "name": "Time left",
                "value": embed_text(hackathon.get("time_left_to_submission")),
                "inline": True,
            },
            {
                "name": "Themes",
                "value": themes,
                "inline": False,
            },
        ],
        "footer": {"text": "Devpost Hackathon Notifier • Updated daily"},
    }

    thumb = thumbnail_url(hackathon.get("thumbnail_url"))
    if thumb:
        embed["thumbnail"] = {"url": thumb}

    return embed


def discord_request(
    webhook_url: str,
    method: str,
    payload: dict | None = None,
) -> dict | None:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": USER_AGENT}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            if not body:
                return None
            return json.loads(body)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            retry_after = error.headers.get("Retry-After", "2")
            time.sleep(float(retry_after))
            return discord_request(webhook_url, method, payload)
        if error.code == 404 and method == "DELETE":
            return None
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord API error {error.code} for {method}: {body or error.reason}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Network error for {method}: {error.reason}") from error


def webhook_with_wait(webhook_url: str) -> str:
    separator = "&" if "?" in webhook_url else "?"
    if "wait=" in webhook_url:
        return webhook_url
    return f"{webhook_url}{separator}wait=true"


def post_embed(webhook_url: str, embed: dict) -> str:
    response = discord_request(
        webhook_with_wait(webhook_url),
        "POST",
        {"embeds": [embed]},
    )
    if not response or "id" not in response:
        raise RuntimeError("Discord did not return a message id (expected response with ?wait=true)")
    return response["id"]


def delete_message(webhook_url: str, message_id: str) -> None:
    url = f"{webhook_url.rstrip('/')}/messages/{message_id}"
    discord_request(url, "DELETE")


def validate_webhook(env_name: str, webhook_url: str) -> None:
    request = urllib.request.Request(
        webhook_url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Invalid webhook for {env_name} (HTTP {error.code}): {body or error.reason}"
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not reach webhook for {env_name}: {error.reason}"
        ) from error


def validate_webhooks(tiers: list[dict]) -> None:
    print("Validating Discord webhooks...")
    for tier in tiers:
        env_name = tier["webhook_env"]
        webhook_url = os.environ.get(env_name, "").strip()
        if not webhook_url:
            raise RuntimeError(f"Missing environment variable: {env_name}")
        validate_webhook(env_name, webhook_url)
        print(f"  OK: {tier['label']} ({env_name})")


def sync_tier(
    tier: dict,
    hackathons: list[dict],
    state: dict,
) -> int:
    tier_id = tier["id"]
    webhook_url = webhook_for_tier(tier)
    tier_state = state["tiers"].setdefault(tier_id, {"message_ids": []})
    old_message_ids = list(tier_state.get("message_ids", []))

    for message_id in old_message_ids:
        delete_message(webhook_url, message_id)
        time.sleep(POST_DELAY_SECONDS)

    new_message_ids: list[str] = []
    for index, hackathon in enumerate(hackathons, start=1):
        embed = build_embed(hackathon, tier["label"], index)
        message_id = post_embed(webhook_url, embed)
        new_message_ids.append(message_id)
        print(f"  Posted #{index}: [{hackathon['open_state']}] {hackathon['title']}")
        time.sleep(POST_DELAY_SECONDS)

    tier_state["message_ids"] = new_message_ids
    tier_state["count"] = len(new_message_ids)
    tier_state["last_synced"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return len(new_message_ids)


def run() -> int:
    try:
        tiers = load_tier_config()
        validate_webhooks(tiers)

        print("Fetching open and upcoming hackathons from Devpost...")
        hackathons = fetch_all_hackathons()
        buckets = bucket_hackathons(hackathons)
        state = load_state()
        state.setdefault("tiers", {})

        total_posted = 0
        print(f"Found {len(hackathons)} hackathon(s). Syncing Discord channels...")
        for tier in tiers:
            tier_hackathons = buckets.get(tier["id"], [])
            print(f"\n{tier['label']} ({len(tier_hackathons)} hackathon(s))")
            total_posted += sync_tier(tier, tier_hackathons, state)

        save_state(state)
        print(f"\nDone. Posted {total_posted} message(s) across {len(tiers)} channel(s).")
        return 0
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
