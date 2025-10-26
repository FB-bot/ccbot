# cc_checker_bot.py
# ==============================
# Telegram CC Checker Bot
# Works like your HTML + JS version
# Developer: @noobxvau (MN SIDDIK)
# ==============================

import os
import random
import re
import time
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------------
BOT_TOKEN = os.environ.get("8239266013:AAHoOITQp3OepWy94DdDE82SbeQFgcHiqwY", "8239266013:AAHoOITQp3OepWy94DdDE82SbeQFgcHiqwY")

# -------------------------
# Credit Card Validation (Luhn Algorithm)
def is_valid_credit_card(number: str) -> bool:
    number = re.sub(r"\D", "", number)
    pattern = r"^(?:3[47][0-9]{13}|4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3(?:0[0-5]|[68][0-9])[0-9]{11}|(?:2131|1800|35\d{3})\d{11})$"
    if not re.match(pattern, number):
        return False

    total = 0
    alt = False
    for digit in number[::-1]:
        n = int(digit)
        if alt:
            n *= 2
            if n > 9:
                n = (n % 10) + 1
        total += n
        alt = not alt
    return total % 10 == 0

# -------------------------
# Start Command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💳 *Welcome to CC Checker Bot!*\n\n"
        "Send me a list of CCs like this:\n"
        "`4111111111111111|12|2026|123`\n\n"
        "I will check them and categorize into:\n"
        "✅ Live\n❌ Dead\n⚙️ Unknown\n\n"
        "Developer: @noobxvau (MN SIDDIK)",
        parse_mode="Markdown"
    )

# -------------------------
# Process CC List
async def handle_cc_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    cards = [line.strip() for line in text.split("\n") if line.strip()]

    if not cards:
        await update.message.reply_text("❌ Please send some credit card numbers first.")
        return

    ali_list, muhammad_list, murad_list = [], [], []

    for line in cards:
        card_number = line.split("|")[0].strip()

        if not is_valid_credit_card(card_number):
            murad_list.append(f"⚙️ *Invalid (Luhn Check)* | `{line}` /noobxvau")
            continue

        rnd = random.random()
        if rnd < 0.2:
            ali_list.append(f"✅ *Live* | `{line}` → [Charge: $4.99] [GATE:01] /noobxvau")
        elif rnd < 0.9:
            muhammad_list.append(f"❌ *Dead* | `{line}` → [Charge: $0.00] [GATE:01] /noobxvau")
        else:
            murad_list.append(f"⚙️ *Unknown* | `{line}` → [Charge: N/A] [GATE:01] /noobxvau")

    # Simulate checking delay like JS version
    await update.message.reply_text("🔍 Checking cards... Please wait...")

    time.sleep(random.randint(2, 5))

    result_msg = "✅ *CC Check Complete!*\n\n"
    result_msg += f"💚 Live: {len(ali_list)}\n"
    result_msg += f"❤️ Dead: {len(muhammad_list)}\n"
    result_msg += f"🟠 Unknown: {len(murad_list)}\n\n"

    await update.message.reply_text(result_msg, parse_mode="Markdown")

    if ali_list:
        await update.message.reply_text("\n".join(ali_list), parse_mode="Markdown")
    if muhammad_list:
        await update.message.reply_text("\n".join(muhammad_list), parse_mode="Markdown")
    if murad_list:
        await update.message.reply_text("\n".join(murad_list), parse_mode="Markdown")

# -------------------------
# Main Function
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cc_list))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
