import asyncio
import json
from datetime import datetime, timezone
from telegram import Bot
from telegram.error import TelegramError

import db
import pool as p
from config import BOT_TOKEN, REMINDER_HOURS


bot = Bot(token=BOT_TOKEN)


def utcnow():
    return datetime.now(timezone.utc)


def parse_deadline(deadline_str: str) -> datetime:
    dt = datetime.fromisoformat(deadline_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def send_message(chat_id: str, text: str):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    except TelegramError as e:
        print(f"[SCHEDULER] Failed to send message to {chat_id}: {e}")


async def check_circles():
    circles = db.get_all_active_circles()
    now = utcnow()

    for circle in circles:
        if circle["status"] != "active":
            continue

        if not circle.get("next_deadline"):
            continue

        deadline = parse_deadline(circle["next_deadline"])
        time_left = (deadline - now).total_seconds()
        hours_left = time_left / 3600
        chat_id = circle["chat_id"]
        circle_id = circle["id"]
        round_number = circle["current_round"]

        # Send reminders at 24h, 6h, 1h before deadline
        for reminder_hour in REMINDER_HOURS:
            window_start = reminder_hour * 3600
            window_end = window_start - 600  # 10 min window
            if window_end < time_left <= window_start:
                await send_reminder(circle, hours_left)
                break

        # Deadline passed — apply penalties and execute payout
        if time_left <= 0:
            await handle_deadline(circle)


async def send_reminder(circle: dict, hours_left: float):
    circle_id = circle["id"]
    chat_id = circle["chat_id"]
    round_number = circle["current_round"]

    status = p.get_circle_status(circle_id)
    unpaid = status["unpaid"]

    if not unpaid:
        return  # Everyone already paid

    hours_str = f"{int(hours_left)}h" if hours_left >= 1 else "less than 1 hour"
    mentions = " ".join(
        [f"@{m['username']}" if m.get("username") else m.get("full_name", "member")
         for m in unpaid]
    )

    msg = (
        f"⏰ <b>Circlo Reminder — Round {round_number}</b>\n\n"
        f"Deadline in <b>{hours_str}</b>.\n\n"
        f"Still waiting on: {mentions}\n\n"
        f"Send /pay to contribute {circle['contribution_amount']} cUSD before the deadline. "
        f"Miss it and a penalty applies automatically. 🔒"
    )
    await send_message(chat_id, msg)


async def handle_deadline(circle: dict):
    circle_id = circle["id"]
    chat_id = circle["chat_id"]
    round_number = circle["current_round"]

    await send_message(
        chat_id,
        f"⌛ <b>Round {round_number} deadline reached.</b>\n\nProcessing penalties for late members..."
    )

    # Apply penalties
    penalty_results = p.apply_penalties(circle_id)

    if penalty_results:
        lines = []
        for r in penalty_results:
            name = r["member"].get("username") or r["member"].get("full_name", "Member")
            if r["penalized"]:
                lines.append(f"❌ @{name} — {r['amount']} cUSD penalty applied")
            else:
                lines.append(f"⚠️ @{name} — penalty could not be collected (low balance)")

        await send_message(
            chat_id,
            "🔒 <b>Penalties processed:</b>\n\n" + "\n".join(lines)
        )

    # Execute payout
    result = p.execute_payout(circle_id)

    if result["success"]:
        recipient = result["recipient"]
        name = recipient.get("username") or recipient.get("full_name", "member")
        amount = result["amount"]
        tx = result["tx_hash"]

        await send_message(
            chat_id,
            f"🎉 <b>Round {round_number} Complete!</b>\n\n"
            f"💸 <b>{amount:.2f} cUSD</b> sent to @{name}\n"
            f"🔗 <a href='https://celoscan.io/tx/{tx}'>View on CeloScan</a>\n\n"
            f"Round {result['next_round']} begins now. Next deadline set."
        )
    else:
        await send_message(
            chat_id,
            f"⚠️ <b>Payout failed:</b> {result['error']}\n\nAdmin please run /payout manually."
        )


async def scheduler_loop():
    print("[SCHEDULER] Starting background loop...")
    while True:
        try:
            await check_circles()
        except Exception as e:
            print(f"[SCHEDULER] Error: {e}")
        await asyncio.sleep(300)  # Check every 5 minutes
