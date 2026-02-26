#!/usr/bin/env python3
"""Delete all tweets from your X/Twitter account."""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime

import requests
from requests_oauthlib import OAuth1
from dotenv import load_dotenv

BASE_URL_V2 = "https://api.twitter.com/2"
BASE_URL_V1 = "https://api.twitter.com/1.1"
RATE_LIMIT_WINDOW = 15 * 60  # 15 minutes in seconds
RATE_LIMIT_MAX = 14  # v1.1 destroy is 15 per 15 min, stay 1 under
TIMELINE_PAGE_SIZE = 100


def setup_logging(verbose):
    logger = logging.getLogger("tweet_deleter")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    return logger


def load_credentials():
    load_dotenv()
    required = ["API_KEY", "API_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"]
    creds = {}
    missing = []
    for key in required:
        val = os.environ.get(key, "").strip()
        if not val or val.startswith("your_"):
            missing.append(key)
        else:
            creds[key] = val

    if missing:
        print(f"Error: Missing credentials: {', '.join(missing)}", file=sys.stderr)
        print("Copy .env.example to .env and fill in your API keys.", file=sys.stderr)
        sys.exit(1)

    return creds


def create_auth(creds):
    return OAuth1(
        creds["API_KEY"],
        creds["API_SECRET"],
        creds["ACCESS_TOKEN"],
        creds["ACCESS_TOKEN_SECRET"],
    )


def get_me(auth):
    try:
        resp = requests.get(f"{BASE_URL_V2}/users/me", auth=auth)
    except requests.RequestException as e:
        print(f"Error: Could not connect to Twitter API: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code == 401:
        print("Error: Invalid credentials. Check your .env file.", file=sys.stderr)
        sys.exit(1)
    if resp.status_code != 200:
        print(f"Error: GET /users/me returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    return resp.json()["data"]


def fetch_timeline_tweet_ids(auth, user_id, logger):
    tweets = []
    url = f"{BASE_URL_V2}/users/{user_id}/tweets"
    params = {
        "max_results": TIMELINE_PAGE_SIZE,
        "tweet.fields": "id,created_at,text",
    }
    page = 0

    while True:
        page += 1
        try:
            resp = requests.get(url, params=params, auth=auth)
        except requests.RequestException as e:
            logger.error(f"Network error fetching timeline: {e}")
            break

        if resp.status_code != 200:
            logger.error(f"GET timeline returned {resp.status_code}: {resp.text}")
            break

        data = resp.json()
        batch = data.get("data", [])
        tweets.extend(batch)
        logger.info(f"Fetched page {page} ({len(tweets)} tweets so far)")

        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
        params["pagination_token"] = next_token

    return tweets


def parse_archive(archive_path, logger):
    try:
        with open(archive_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {archive_path}", file=sys.stderr)
        sys.exit(1)

    # Strip the JS variable assignment prefix: window.YTD.tweet.part0 = [...]
    bracket_pos = content.find("[")
    if bracket_pos == -1:
        print("Error: Could not find JSON array in archive file.", file=sys.stderr)
        print("Make sure you're pointing at the tweets.js file from your Twitter data export.", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(content[bracket_pos:])
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse archive JSON: {e}", file=sys.stderr)
        sys.exit(1)

    tweets = []
    for item in raw:
        tweet = item.get("tweet", item)
        tweet_id = tweet.get("id_str") or tweet.get("id")
        text = tweet.get("full_text") or tweet.get("text", "")
        created_at = tweet.get("created_at", "")
        if tweet_id:
            tweets.append({"id": str(tweet_id), "text": text, "created_at": created_at})

    logger.info(f"Parsed {len(tweets)} tweets from archive file")
    return tweets


def save_tweets_csv(tweets, username, logger):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    desktop = os.path.expanduser("~/Desktop")
    filename = os.path.join(desktop, f"tweets_backup_{username}_{timestamp}.csv")
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "created_at", "text"])
        for tweet in tweets:
            writer.writerow([
                tweet.get("id", ""),
                tweet.get("created_at", ""),
                tweet.get("text", ""),
            ])
    logger.info(f"Saved {len(tweets)} tweets to {filename}")
    return filename


def delete_tweets(auth, tweets, dry_run, logger):
    if dry_run:
        for i, tweet in enumerate(tweets):
            text = (tweet.get("text") or "")[:50]
            logger.info(f"[DRY RUN] [{i+1}/{len(tweets)}] Would delete {tweet['id']}: \"{text}\"")
        return 0, 0

    deleted = 0
    failed = 0
    skipped = 0

    try:
        for i, tweet in enumerate(tweets):
            url = f"{BASE_URL_V1}/statuses/destroy/{tweet['id']}.json"

            try:
                resp = requests.post(url, auth=auth)
            except requests.RequestException as e:
                logger.error(f"[{i+1}/{len(tweets)}] Network error: {e}")
                failed += 1
                continue

            if resp.status_code == 200:
                deleted += 1
                logger.info(f"[{i+1}/{len(tweets)}] Deleted tweet {tweet['id']}")
            elif resp.status_code == 404:
                skipped += 1
                logger.debug(f"[{i+1}/{len(tweets)}] Tweet {tweet['id']} already gone (404)")
            elif resp.status_code == 429:
                reset_time = int(resp.headers.get("x-rate-limit-reset", time.time() + RATE_LIMIT_WINDOW))
                sleep_seconds = max(reset_time - int(time.time()), 1) + 2
                logger.warning(f"Rate limited (429). Sleeping {sleep_seconds}s until reset...")
                time.sleep(sleep_seconds)
                # Retry this tweet
                try:
                    retry = requests.post(url, auth=auth)
                    if retry.status_code == 200:
                        deleted += 1
                        logger.info(f"[{i+1}/{len(tweets)}] Deleted tweet {tweet['id']} (retry)")
                    elif retry.status_code == 404:
                        skipped += 1
                    else:
                        logger.error(f"[{i+1}/{len(tweets)}] Retry failed for {tweet['id']}: {retry.status_code}")
                        failed += 1
                except requests.RequestException as e:
                    logger.error(f"[{i+1}/{len(tweets)}] Retry network error: {e}")
                    failed += 1
            else:
                logger.error(f"[{i+1}/{len(tweets)}] Failed {tweet['id']}: HTTP {resp.status_code}")
                failed += 1

            # Check remaining rate limit from headers and sleep proactively
            remaining = resp.headers.get("x-rate-limit-remaining")
            reset_ts = resp.headers.get("x-rate-limit-reset")
            if remaining is not None and int(remaining) <= 0 and reset_ts:
                sleep_seconds = max(int(reset_ts) - int(time.time()), 1) + 2
                logger.info(f"Rate limit exhausted. Sleeping {sleep_seconds}s until reset...")
                time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        logger.info("\nInterrupted. Partial results below.")

    logger.info(f"Skipped (already deleted): {skipped}")
    return deleted, failed


def main():
    parser = argparse.ArgumentParser(
        description="Delete all tweets from your X/Twitter account.",
        epilog=(
            "Examples:\n"
            "  python delete_tweets.py api --dry-run\n"
            "  python delete_tweets.py api\n"
            "  python delete_tweets.py archive tweets.js --dry-run\n"
            "  python delete_tweets.py archive tweets.js\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    api_parser = subparsers.add_parser("api", help="Fetch up to 3,200 recent tweets via API and delete them.")
    api_parser.add_argument("--dry-run", action="store_true", help="Preview without deleting.")
    api_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    api_parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")

    archive_parser = subparsers.add_parser("archive", help="Delete tweets from a Twitter data export.")
    archive_parser.add_argument("file", help="Path to tweets.js from your Twitter data export.")
    archive_parser.add_argument("--dry-run", action="store_true", help="Preview without deleting.")
    archive_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt.")
    archive_parser.add_argument("--verbose", action="store_true", help="Debug-level logging.")

    args = parser.parse_args()
    logger = setup_logging(args.verbose)

    creds = load_credentials()
    auth = create_auth(creds)

    logger.info("Verifying credentials...")
    me = get_me(auth)
    logger.info(f"Authenticated as @{me['username']} (ID: {me['id']})")

    if args.mode == "api":
        logger.info("Fetching tweets from timeline API...")
        tweets = fetch_timeline_tweet_ids(auth, me["id"], logger)
    else:
        logger.info(f"Parsing archive: {args.file}")
        tweets = parse_archive(args.file, logger)

    if not tweets:
        logger.info("No tweets found. Nothing to do.")
        return

    logger.info(f"Found {len(tweets)} tweets.")

    # Always save a backup CSV before doing anything
    backup_file = save_tweets_csv(tweets, me["username"], logger)

    if args.dry_run:
        deleted, failed = delete_tweets(auth, tweets, True, logger)
        logger.info(f"Dry run complete. {len(tweets)} tweets would be deleted. Backup saved to {backup_file}")
    else:
        if not args.yes:
            confirm = input(f"Delete {len(tweets)} tweets from @{me['username']}? This cannot be undone. [y/N] ")
            if confirm.lower() != "y":
                logger.info(f"Aborted. Backup still saved to {backup_file}")
                return

        deleted, failed = delete_tweets(auth, tweets, False, logger)
        logger.info(f"Done. Deleted: {deleted}, Failed: {failed}, Total: {len(tweets)}")
        logger.info(f"Backup saved to {backup_file}")


if __name__ == "__main__":
    main()
