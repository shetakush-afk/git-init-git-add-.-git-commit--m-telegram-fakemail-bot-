import logging
import os
import re
from telegram import Update
from telegram import InputFile
from telegram.ext import CallbackContext, CommandHandler, Updater

from legal_dump import (
    LegalSourceError,
    build_csv_dump,
    generate_keywords,
    search_cases,
)

MAX_SEARCH_RESULTS = 5
DEFAULT_DUMP_RESULTS = 20
MAX_DUMP_RESULTS = 100
DEFAULT_KEYWORD_RESULTS = 12
MAX_KEYWORD_RESULTS = 30

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Legal Dump Bot me aapka swagat hai.\n\n"
        "Available commands:\n"
        "/keywords <topic> [count] - Auto keyword suggestions\n"
        "/search <query> - Top legal results dekhein\n"
        "/dump <query> [limit] - CSV dump file paayen\n"
        "/sources - Data source info"
    )


def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Usage:\n"
        "/keywords contract 12\n"
        "/search bail\n"
        "/dump contract dispute 30\n\n"
        "Notes:\n"
        "- keywords count optional hai (3-30)\n"
        "- dump limit optional hai (1-100)\n"
        "- Bot public legal records source use karta hai."
    )


def sources(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Current source: CourtListener public API\n"
        "Website: https://www.courtlistener.com/\n\n"
        "Sirf public legal data index kiya jata hai."
    )


def _extract_query_and_number(args, default_value, max_value, min_value=1):
    if not args:
        return "", default_value

    value = default_value
    updated_args = list(args)
    if updated_args and updated_args[-1].isdigit():
        possible_value = int(updated_args[-1])
        value = max(min_value, min(possible_value, max_value))
        updated_args = updated_args[:-1]

    return " ".join(updated_args).strip(), value


def keywords(update: Update, context: CallbackContext):
    query, count = _extract_query_and_number(
        context.args, DEFAULT_KEYWORD_RESULTS, MAX_KEYWORD_RESULTS, min_value=3
    )
    if not query:
        update.message.reply_text("Usage: /keywords <topic> [count]")
        return

    generated = generate_keywords(query, limit=count)
    if not generated:
        update.message.reply_text("Keywords generate nahi ho paaye. Query change karke try karein.")
        return

    lines = [f"Auto keywords for: {query}\n"]
    for index, keyword in enumerate(generated, start=1):
        lines.append(f"{index}. {keyword}")
    lines.append("\nTip: /search <keyword> ya /dump <keyword> 20 use karein.")
    update.message.reply_text("\n".join(lines))


def search(update: Update, context: CallbackContext):
    query = " ".join(context.args).strip()
    if not query:
        update.message.reply_text("Usage: /search <query>")
        return

    try:
        cases = search_cases(query, limit=MAX_SEARCH_RESULTS)
    except LegalSourceError as exc:
        update.message.reply_text(str(exc))
        return

    if not cases:
        update.message.reply_text("Is query ke liye koi result nahi mila.")
        return

    lines = [f"Top {len(cases)} results for: {query}\n"]
    for index, case in enumerate(cases, start=1):
        case_name = case.get("case_name", "Unknown")[:120]
        lines.append(
            f"{index}. {case_name}\n"
            f"Court: {case.get('court', 'Unknown')}\n"
            f"Date: {case.get('date_filed', 'Unknown')}\n"
            f"Citation: {case.get('citation', '-') or '-'}\n"
            f"URL: {case.get('url', '-') or '-'}\n"
        )
    update.message.reply_text("\n".join(lines))


def dump(update: Update, context: CallbackContext):
    query, limit = _extract_query_and_number(
        context.args, DEFAULT_DUMP_RESULTS, MAX_DUMP_RESULTS
    )
    if not query:
        update.message.reply_text("Usage: /dump <query> [limit]")
        return

    try:
        cases = search_cases(query, limit=limit)
    except LegalSourceError as exc:
        update.message.reply_text(str(exc))
        return

    if not cases:
        update.message.reply_text("Dump banane ke liye koi result nahi mila.")
        return

    csv_file = build_csv_dump(query, cases)
    safe_query = re.sub(r"[^a-zA-Z0-9_-]+", "_", query.strip().lower())[:40]
    if not safe_query:
        safe_query = "results"

    filename = f"legal_dump_{safe_query}.csv"
    update.message.reply_document(
        document=InputFile(csv_file, filename=filename),
        caption=f"Query: {query}\nRows: {len(cases)}",
    )


def on_error(update: object, context: CallbackContext):
    logger.exception("Unhandled bot error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        update.effective_message.reply_text(
            "Unexpected error aaya. Thodi der baad dobara try karein."
        )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable set karein.")

    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("sources", sources))
    dp.add_handler(CommandHandler("keywords", keywords))
    dp.add_handler(CommandHandler("search", search))
    dp.add_handler(CommandHandler("dump", dump))
    dp.add_error_handler(on_error)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()