# bot.py
"""
SIMULATED CC Checker (DEMO ONLY) Telegram Bot
- This bot is strictly a UI/behavior simulation and FORMAT validator (Luhn).
- DO NOT use real/sensitive card data with this bot. It will NOT perform any live checks,
  transactions, BIN lookups, or attempt any network verification.
- Set BOT_TOKEN environment variable before running.
"""

import os
import logging
import threading
import time
import random

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ParseMode

# ---------------- Config ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# per-chat processing flags & threads
_processing_flags = {}   # chat_id -> {'running': bool, 'thread': Thread}
# simulation probabilities (tweak safely)
SIM_PROBS = {
    "Live": 0.2,     # 20% chance (for demonstration only)
    "Dead": 0.7,     # 70% chance
    "Unknown": 0.1   # 10% chance
}
# delays to mimic the website's progressive behavior (in seconds)
MIN_DELAY = 2.0
MAX_DELAY = 5.0
# safety limits
MAX_BATCH_LINES = 300
MAX_REPLY_CHUNK = 3500  # chunk messages to avoid 4096 limit

# --------------- Logging ----------------
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --------------- Helpers ----------------
def normalize_digits(text: str) -> str:
    return "".join(ch for ch in text if ch.isdigit())

def luhn_check(number: str) -> bool:
    """Digit-by-digit Luhn algorithm (works for strings of digits)."""
    digits = [ord(c) - 48 for c in number if '0' <= c <= '9']
    if len(digits) < 12:
        return False
    total = 0
    alt = False
    for d in reversed(digits):
        if alt:
            doubled = d * 2
            if doubled > 9:
                doubled -= 9
            total += doubled
        else:
            total += d
        alt = not alt
    return (total % 10) == 0

def choose_simulated_label() -> str:
    r = random.random()
    cum = 0.0
    for label, p in SIM_PROBS.items():
        cum += p
        if r < cum:
            return label
    return "Unknown"

def safe_display_original(s: str) -> str:
    return s.replace("<", "").replace(">", "")

def chunk_text(text: str, limit: int = MAX_REPLY_CHUNK):
    """Yield chunks not exceeding limit characters (preserve newlines)."""
    if len(text) <= limit:
        yield text
        return
    lines = text.splitlines()
    cur = []
    cur_len = 0
    for ln in lines:
        ln_n = ln + "\n"
        if cur_len + len(ln_n) > limit:
            yield "\n".join(cur)
            cur = [ln]
            cur_len = len(ln_n)
        else:
            cur.append(ln)
            cur_len += len(ln_n)
    if cur:
        yield "\n".join(cur)

# --------------- Telegram Handlers ----------------
def start(update, context):
    update.message.reply_text(
        "👋 স্বাগতম — SIMULATED Checker Bot (DEMO ONLY).\n\n"
        "IMPORTANT: This bot is a UI simulation and FORMAT validator only. "
        "Do NOT send real/sensitive card data.\n\n"
        "Commands:\n"
        "/validate <number>  — single number Luhn format check + simulated label\n"
        "/batch  — paste multiple numbers (one per line) after the command (or reply with a list)\n"
        "/stop   — stop an ongoing batch processing for this chat\n"
        "/help   — show this message\n\n"
        "Note: simulated labels are clearly marked with 'SIMULATION' prefix."
    )

def help_cmd(update, context):
    start(update, context)

def validate_cmd(update, context):
    if not context.args:
        update.message.reply_text("ব্যবহার: /validate <number>\nউদাহরণ: /validate 4539 1488 0343 6467")
        return
    raw = " ".join(context.args)
    digits = normalize_digits(raw)
    if digits == "":
        update.message.reply_text("দয়া করে এমন ইনপুট দাও যাতে সংখ্যাগুলো থাকে (digits).")
        return
    ok = luhn_check(digits)
    # Build simulated label only if format valid; otherwise mark invalid
    if not ok:
        reply = f"*SIMULATION* — ` {digits} ` — *Invalid format ❌*\n_input:_ {safe_display_original(raw)}"
    else:
        sim = choose_simulated_label()
        reply = (
            f"*SIMULATION* — ` {digits} ` — *{sim}*  \n"
            f"Format: *Valid ✅*\n_input:_ {safe_display_original(raw)}"
        )
    update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)

def batch_cmd(update, context):
    """
    Start processing a batch. The user may send:
    /batch
    <paste multiline numbers in same message>
    or
    /batch
    (then reply with a multiline message) — we handle both cases by reading rest of text.
    """
    # extract possible inline content
    content = ""
    if context.args:
        # command with following text (maybe multiple lines glued)
        content = " ".join(context.args)
    else:
        # telegram may include the whole message text (command + payload). Try to detect.
        full = update.message.text or ""
        parts = full.split(None, 1)
        if len(parts) > 1:
            content = parts[1]

    if not content.strip():
        # ask user to paste list or reply with list
        update.message.reply_text(
            "Paste multiple numbers (one per line) after the command or reply to this message with the list.\n\n"
            "Example:\n/batch\n4539 1488 0343 6467\n371449635398431\n..."
        )
        return

    # Normalize: split on newlines primarily; also accept semicolon/comma separated as fallback
    lines = []
    if "\n" in content:
        for ln in content.splitlines():
            ln = ln.strip()
            if ln:
                lines.append(ln)
    else:
        # single-line long paste: split by comma/semicolon OR treat as one
        if "," in content or ";" in content:
            for ln in [s.strip() for s in content.replace(";",",").split(",")]:
                if ln:
                    lines.append(ln)
        else:
            lines = [content.strip()]

    if len(lines) == 0:
        update.message.reply_text("কোনো বৈধ লাইন পাওয়া যায়নি। প্রতিটি লাইনে একটি করে নম্বর রাখুন।")
        return
    if len(lines) > MAX_BATCH_LINES:
        update.message.reply_text(f"একবারে সর্বোচ্চ {MAX_BATCH_LINES} লাইনের বেশি পাঠাও না।")
        return

    chat_id = update.effective_chat.id
    # If already processing for this chat, reject
    flag = _processing_flags.get(chat_id)
    if flag and flag.get("running"):
        update.message.reply_text("একটি ব্যাচ ইতোমধ্যে চলছে — /stop দিয়ে সেটি থামান আগে নতুন ব্যাচ শুরু করুন।")
        return

    # create and register processing thread
    t = threading.Thread(target=_process_batch_thread, args=(context, chat_id, lines), daemon=True)
    _processing_flags[chat_id] = {"running": True, "thread": t}
    t.start()
    update.message.reply_text(f"Batch started: {len(lines)} items. Use /stop to cancel.")

def _process_batch_thread(context, chat_id, lines):
    """
    Process lines one by one, send progressive updates.
    Honour the per-chat _processing_flags[chat_id]['running'] to allow /stop.
    """
    total = len(lines)
    valid_count = 0
    invalid_count = 0
    simulated_count = {"Live":0, "Dead":0, "Unknown":0}

    # We'll send incremental messages (one per item) to mimic web incremental UI.
    for idx, raw_line in enumerate(lines, start=1):
        # Check stop flag
        flag = _processing_flags.get(chat_id)
        if not flag or not flag.get("running"):
            # send cancellation note and break
            try:
                context.bot.send_message(chat_id=chat_id, text=f"Processing stopped by user at item {idx}/{total}.")
            except Exception as e:
                logger.exception("Failed to send stop message: %s", e)
            break

        digits = normalize_digits(raw_line)
        if digits == "":
            # ignore or report as invalid format
            msg = f"*SIMULATION* — `_ignored_` — no digits found in: `{safe_display_original(raw_line)}`"
            try:
                context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
            except:
                pass
            # small pause to mimic site pacing
            time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
            continue

        ok = luhn_check(digits)
        if not ok:
            invalid_count += 1
            out = (
                f"*SIMULATION* — `{digits}` — *Invalid format ❌*\n"
                f"_input:_ {safe_display_original(raw_line)}\n"
                f"Progress: {idx}/{total}"
            )
            try:
                context.bot.send_message(chat_id=chat_id, text=out, parse_mode=ParseMode.MARKDOWN)
            except:
                pass
        else:
            valid_count += 1
            sim_label = choose_simulated_label()
            simulated_count[sim_label] += 1
            out = (
                f"*SIMULATION* — `{digits}` — *{sim_label}*\n"
                f"Format: *Valid ✅*\n"
                f"_input:_ {safe_display_original(raw_line)}\n"
                f"Progress: {idx}/{total}"
            )
            try:
                context.bot.send_message(chat_id=chat_id, text=out, parse_mode=ParseMode.MARKDOWN)
            except:
                pass

        # mimic web random delay between items
        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    # final summary (if still running)
    flag = _processing_flags.get(chat_id)
    if flag and flag.get("running"):
        summary_lines = [
            "*SIMULATION - Batch Summary*",
            f"Total items processed: {valid_count + invalid_count}",
            f"Valid format: {valid_count}",
            f"Invalid format: {invalid_count}",
            f"Simulated Live: {simulated_count['Live']}",
            f"Simulated Dead: {simulated_count['Dead']}",
            f"Simulated Unknown: {simulated_count['Unknown']}",
            "\nNote: These are SIMULATED labels for DEMO only. Do NOT use real/sensitive card data."
        ]
        summary_text = "\n".join(summary_lines)
        # chunk and send safely
        for chunk in chunk_text(summary_text):
            try:
                context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.MARKDOWN)
            except:
                pass
    # mark as stopped/finished
    _processing_flags[chat_id] = {"running": False, "thread": None}

def stop_cmd(update, context):
    chat_id = update.effective_chat.id
    flag = _processing_flags.get(chat_id)
    if not flag or not flag.get("running"):
        update.message.reply_text("এই চ্যাটে কোনো চলমান ব্যাচ নেই।")
        return
    # set running flag to False; thread will check and break
    _processing_flags[chat_id]['running'] = False
    update.message.reply_text("Stopping batch... please wait a moment. (You will receive a message when it halts.)")

def unknown_text_handler(update, context):
    # If user pastes a multiline list (>=2 lines), treat as batch (convenience)
    text = update.message.text or ""
    if text.count("\n") >= 1 and len(text.splitlines()) >= 2:
        # start batch directly
        update.message.text = "/batch " + text  # hack for reuse
        return batch_cmd(update, context)
    # otherwise, gentle help
    update.message.reply_text("আমি বুঝিনো — সাহায্যের জন্য /help ব্যবহার কর।")

def error_handler(update, context):
    logger.exception("Update caused error: %s", context.error)

# --------------- Main ----------------
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set. Exiting.")
        return
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CommandHandler("validate", validate_cmd))
    dp.add_handler(CommandHandler("batch", batch_cmd))
    dp.add_handler(CommandHandler("stop", stop_cmd))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), unknown_text_handler))
    dp.add_error_handler(error_handler)

    logger.info("Starting bot (polling)...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
