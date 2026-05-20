"""Reddit Scout — polls subreddits hourly and posts opportunities to Zoho Cliq.

Run locally:
    python scout.py

Env vars:
    ZOHO_CLIQ_WEBHOOK_URL  Required (unless DRY_RUN=1)
    DRY_RUN                "1" to print instead of posting
    LOOKBACK_MINUTES       Default 75
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from filters import SUBREDDITS, score_thread

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "state" / "seen.json"
SEEN_TTL_DAYS = 14
USER_AGENT = "reddit-scout/1.0 (by /u/Anxious-Community-65)"
REDDIT_TIMEOUT = 15
MIN_SCORE = 2
REQUEST_DELAY = 1.2  # seconds between subreddit fetches (be polite)


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


# --------------------------- state ---------------------------

def load_seen() -> dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text() or "{}")
    except json.JSONDecodeError:
        log("WARN: seen.json corrupt, resetting")
        return {}


def save_seen(seen: dict[str, float]) -> None:
    # Prune entries older than TTL
    cutoff = time.time() - SEEN_TTL_DAYS * 86400
    pruned = {k: v for k, v in seen.items() if v >= cutoff}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(pruned, indent=2, sort_keys=True) + "\n")


# --------------------------- reddit ---------------------------

def fetch_subreddit_new(sub: str, limit: int = 25) -> list[dict]:
    url = f"https://www.reddit.com/r/{sub}/new.json?limit={limit}"
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=REDDIT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return [c["data"] for c in data.get("data", {}).get("children", [])]
    except Exception as e:  # noqa: BLE001
        log(f"ERROR fetching r/{sub}: {e}")
        return []


# --------------------------- summary ---------------------------

def two_line_summary(post: dict) -> str:
    """Compose a brief 2-line description of the thread topic."""
    sub = post.get("subreddit_name_prefixed") or f"r/{post.get('subreddit', '?')}"
    title = (post.get("title") or "").strip()
    selftext = (post.get("selftext") or "").strip().replace("\n", " ")
    if selftext:
        snippet = selftext[:180].rsplit(" ", 1)[0]
        if len(selftext) > 180:
            snippet += "…"
        return f"{sub} — {title}\n{snippet}"
    return f"{sub} — {title}\n(Link/discussion post — no body text)"


# --------------------------- cliq ---------------------------

def post_to_cliq(webhook_url: str, link: str, summary: str) -> bool:
    text = f"🧵 {link}\n{summary}"
    payload = {"text": text}
    try:
        r = requests.post(webhook_url, json=payload, timeout=15)
        if r.status_code >= 300:
            log(f"ERROR Cliq POST {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log(f"ERROR posting to Cliq: {e}")
        return False


def post_to_cliq_raw(webhook_url: str, text: str) -> bool:
    try:
        r = requests.post(webhook_url, json={"text": text}, timeout=20)
        if r.status_code >= 300:
            log(f"ERROR Cliq POST {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:  # noqa: BLE001
        log(f"ERROR posting to Cliq: {e}")
        return False


def chunk_text(text: str, max_chars: int = 9000) -> list[str]:
    """Split text into chunks under max_chars, breaking on blank lines when possible."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        addition = (block + "\n\n")
        if len(current) + len(addition) > max_chars and current:
            chunks.append(current.rstrip())
            current = addition
        else:
            current += addition
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


# --------------------------- main ---------------------------

def main() -> int:
    webhook = os.environ.get("ZOHO_CLIQ_WEBHOOK_URL", "").strip()
    dry_run = os.environ.get("DRY_RUN", "0") == "1"
    lookback_min = int(os.environ.get("LOOKBACK_MINUTES", "75"))

    if not webhook and not dry_run:
        log("FATAL: ZOHO_CLIQ_WEBHOOK_URL not set (or set DRY_RUN=1)")
        return 1

    seen = load_seen()
    cutoff_ts = time.time() - lookback_min * 60
    log(f"Polling {len(SUBREDDITS)} subs | lookback={lookback_min}min | dry_run={dry_run}")

    candidates: list[tuple[int, dict]] = []

    for i, sub in enumerate(SUBREDDITS):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        posts = fetch_subreddit_new(sub)
        for p in posts:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            created = p.get("created_utc") or 0
            if created < cutoff_ts:
                continue
            if p.get("stickied") or p.get("over_18"):
                continue
            title = p.get("title") or ""
            selftext = p.get("selftext") or ""
            flair = p.get("link_flair_text")
            score = score_thread(title, selftext, flair)
            if score >= MIN_SCORE:
                candidates.append((score, p))

    log(f"Found {len(candidates)} candidate(s) above threshold")

    # Sort by score desc, then newest first
    candidates.sort(key=lambda t: (-t[0], -(t[1].get("created_utc") or 0)))

    posted = 0
    if candidates:
        lines = [f"🧵 *{len(candidates)} Reddit threads in the last {lookback_min} min*\n"]
        for score, p in candidates:
            pid = p["id"]
            link = "https://www.reddit.com" + p.get("permalink", "")
            summary = two_line_summary(p)
            lines.append(f"[{score}] {link}\n{summary}\n")
            seen[pid] = time.time()

        digest = "\n".join(lines)

        if dry_run:
            log(f"DRY digest ({len(candidates)} threads):\n{digest}")
            posted = len(candidates)
        else:
            # Cliq has ~10k char message limit; split if needed
            chunks = chunk_text(digest, max_chars=9000)
            all_ok = True
            for chunk in chunks:
                if not post_to_cliq_raw(webhook, chunk):
                    all_ok = False
                    break
                time.sleep(1)
            if all_ok:
                posted = len(candidates)
            else:
                # Don't mark seen if posting failed
                for _, p in candidates:
                    seen.pop(p["id"], None)

    save_seen(seen)
    log(f"Posted {posted} thread(s) in digest. State saved ({len(seen)} ids).")

    if posted == 0 and not dry_run and webhook:
        idle_msg = f"🕒 No relevant threads found in the last {lookback_min} minutes."
        try:
            r = requests.post(webhook, json={"text": idle_msg}, timeout=15)
            if r.status_code >= 300:
                log(f"ERROR posting idle notice: {r.status_code} {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            log(f"ERROR posting idle notice: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
