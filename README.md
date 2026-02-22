# X/Twitter Tweet Deleter

Deletes all tweets from your X/Twitter account. Supports fetching tweets via the API (up to 3,200) or parsing a full Twitter data archive export for complete history.

## Prerequisites

- Python 3.8+
- An X/Twitter developer account with an app that has **OAuth 1.0a User Context** enabled
- Your app's API keys and your user access tokens (from [developer.x.com](https://developer.x.com/en/portal/dashboard))

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and fill in your four API credentials
```

## Usage

**Preview what would be deleted (safe, no deletions):**

```bash
python delete_tweets.py api --dry-run
```

**Delete recent tweets via API (up to 3,200):**

```bash
python delete_tweets.py api
```

**Delete ALL tweets using your Twitter data archive:**

1. Request your archive: X Settings > Your Account > Download an Archive of Your Data
2. Extract the archive and find `data/tweets.js`
3. Run:

```bash
python delete_tweets.py archive path/to/tweets.js --dry-run   # preview first
python delete_tweets.py archive path/to/tweets.js              # delete
```

## Rate Limits

The X API allows 50 tweet deletions per 15 minutes. The script handles this automatically — it sleeps between batches and retries on rate limit errors. Deleting 1,000 tweets takes about 5 hours.

## Limitations

- **API mode** can only see your 3,200 most recent tweets (Twitter API limitation). Use **archive mode** for full history.
- Deletions are permanent and cannot be undone.
- If your archive has multiple part files (`tweet-part1.js`, etc.), run the script once per file.
