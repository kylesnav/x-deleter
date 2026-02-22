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

### More examples

**Enable verbose (debug-level) logging to see full request details:**

```bash
python delete_tweets.py api --verbose
python delete_tweets.py archive tweets.js --verbose
```

**Combine dry-run with verbose to inspect everything without risk:**

```bash
python delete_tweets.py api --dry-run --verbose
```

**Handle multi-part archive exports** (some accounts produce `tweet-part1.js`, `tweet-part2.js`, etc.):

```bash
python delete_tweets.py archive data/tweet-part1.js
python delete_tweets.py archive data/tweet-part2.js
```

**Recommended workflow for large accounts:**

```bash
# 1. Start with a dry run to see how many tweets will be affected
python delete_tweets.py archive tweets.js --dry-run

# 2. A CSV backup is automatically saved to your Desktop before any deletions
#    (e.g. ~/Desktop/tweets_backup_yourusername_20250115_143022.csv)

# 3. Run the actual deletion — you'll be prompted to confirm
python delete_tweets.py archive tweets.js

# 4. If interrupted (Ctrl+C), partial progress is reported. Re-run
#    with the same archive file to continue — already-deleted tweets
#    are skipped with a 404 warning.
```

**View help and all available options:**

```bash
python delete_tweets.py --help
python delete_tweets.py api --help
python delete_tweets.py archive --help
```

## Rate Limits

The X API allows 50 tweet deletions per 15 minutes. The script handles this automatically — it sleeps between batches and retries on rate limit errors. Deleting 1,000 tweets takes about 5 hours.

## Limitations

- **API mode** can only see your 3,200 most recent tweets (Twitter API limitation). Use **archive mode** for full history.
- Deletions are permanent and cannot be undone.
- If your archive has multiple part files (`tweet-part1.js`, etc.), run the script once per file.

## Troubleshooting

### Authentication errors

**`Error: Missing credentials: API_KEY, API_SECRET, ...`**

You haven't set up your `.env` file, or some values are still the placeholder defaults (e.g. `your_api_key_here`). Copy the example and fill in real values:

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

**`Error: Invalid credentials. Check your .env file.` (HTTP 401)**

Your API keys or access tokens are wrong or expired. Common causes:
- You regenerated keys in the developer portal but didn't update `.env`.
- The Access Token & Secret belong to a different account than the one you want to delete from. These tokens must be for the _owner_ of the tweets.
- Your app doesn't have **OAuth 1.0a User Context** enabled, or it only has read permissions. Go to your app settings on [developer.x.com](https://developer.x.com/en/portal/dashboard) and ensure it has **Read and Write** permissions.

**`Error: Could not connect to Twitter API: ...`**

A network-level failure (DNS, timeout, firewall). Check your internet connection. If you're behind a corporate proxy, make sure `requests` can reach `api.twitter.com`.

### Rate limits

The X API enforces a limit of **50 tweet deletions per 15-minute window**. The script handles this two ways:

1. **Proactive throttling** -- after every 50 deletions it pauses for the remainder of the 15-minute window automatically.
2. **Reactive retry** -- if the API returns HTTP 429 (Too Many Requests), the script reads the `x-rate-limit-reset` header and sleeps until the limit resets, then retries the failed request.

You don't need to do anything; just let it run. Expect roughly **200 deletions per hour**. For 10,000 tweets, that's about 50 hours. Running it overnight or across a few days is normal.

If you interrupt the script with Ctrl+C, it will print partial results. You can safely re-run it -- tweets that were already deleted will return 404 and be skipped.

### Archive file issues

**`Error: File not found: path/to/tweets.js`**

Double-check the path. After extracting the archive ZIP, the file is typically at `Your archive/data/tweets.js` (or `tweet.js` in some exports).

**`Error: Could not find JSON array in archive file.`**

The script expects the standard Twitter export format where `tweets.js` starts with a JavaScript assignment like `window.YTD.tweet.part0 = [...]`. It strips everything before the first `[` and parses the rest as JSON. This error means the file doesn't contain a `[` character at all -- you may be pointing at the wrong file. Make sure it's the `tweets.js` (or `tweet-part*.js`) from the `data/` folder inside your Twitter archive.

**`Error: Failed to parse archive JSON: ...`**

The file has the expected prefix but the JSON is malformed. This can happen if the file was truncated (incomplete download or extraction). Try re-extracting the archive ZIP. If the file is very large, make sure your disk has enough free space.

### Python dependency issues

**`ModuleNotFoundError: No module named 'requests'` (or `requests_oauthlib`, `dotenv`)**

Install the dependencies:

```bash
pip install -r requirements.txt
```

If you have multiple Python versions, use `pip3` explicitly or run via:

```bash
python3 -m pip install -r requirements.txt
python3 delete_tweets.py api --dry-run
```

**Virtual environment recommended** to avoid conflicts with system packages:

```bash
python3 -m venv venv
source venv/bin/activate    # on macOS/Linux
# venv\Scripts\activate     # on Windows
pip install -r requirements.txt
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
