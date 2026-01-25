import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

TOKEN = "8240923716:AAEaGPVsiqz_9wp0bKO5yRb_JqEJxqAUG1I"

def get_email():
    return requests.get(
        "https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1"
    ).json()[0]

def get_messages(login, domain):
    return requests.get(
        f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"
    ).json()

def start(update: Update, context: CallbackContext):
    email = get_email()
    context.user_data["email"] = email
    update.message.reply_text(
        f"📧 Your Temporary Email:\n{email}\n\n/check to check inbox"
    )

def check(update: Update, context: CallbackContext):
    if "email" not in context.user_data:
        update.message.reply_text("Use /start first")
        return

    login, domain = context.user_data["email"].split("@")
    msgs = get_messages(login, domain)

    if not msgs:
        update.message.reply_text("📭 No mails")
        return

    text = "📬 Inbox:\n\n"
    for m in msgs:
        text += f"From: {m['from']}\nSubject: {m['subject']}\n\n"

    update.message.reply_text(text)

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("check", check))
    updater.start_polling()
    updater.idle()

main()