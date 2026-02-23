# Legal Dump Bot

Telegram bot that searches public legal records and exports result dumps as CSV.

## Features

- `/keywords <topic> [count]`: auto-generate legal search keywords
- `/search <query>`: returns top legal case matches
- `/dump <query> [limit]`: generates CSV dump file for the query
- `/sources`: shows source information

## Data Source

- CourtListener public API: https://www.courtlistener.com/
- Optional API token support through environment variable

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="your-telegram-bot-token"
export COURTLISTENER_API_KEY="optional-courtlistener-api-key"
```

Run:

```bash
python bot.py
```

## Notes

- This bot works on public legal data indexes.
- `count` for `/keywords` is clamped between 3 and 30.
- `limit` for `/dump` is clamped between 1 and 100.
