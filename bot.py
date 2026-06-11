import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
import pool as p
import wallet as w
import scheduler as sched
from config import BOT_TOKEN, DASHBOARD_URL

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── Helpers ────────────────────────────────────────────────────────────────

def user_display(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.full_name or str(user.id)


def format_deadline(deadline_str: str) -> str:
    try:
        dt = datetime.fromisoformat(deadline_str)
        return dt.strftime("%b %d, %Y at %H:%M UTC")
    except:
        return deadline_str


# ─── /start ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 <b>Welcome to Circlo</b>\n\n"
        "Circlo is an onchain rotating savings circle agent built on Celo.\n\n"
        "A group commits a fixed amount of cUSD every cycle. The agent holds it, "
        "enforces deadlines, applies penalties automatically, and rotates the full "
        "pool to one member each round — no trust required.\n\n"
        "<b>Commands:</b>\n"
        "/create — Start a new savings circle (group admin)\n"
        "/join — Join the circle in this group\n"
        "/pay — Make your contribution for the current round\n"
        "/status — See who's paid and who owes this round\n"
        "/balance — Check your wallet balance\n"
        "/history — View past rounds and payouts\n"
        "/wallet — Get your deposit wallet address\n"
        "/payout — Manually trigger payout (admin only)\n\n"
        f"📊 <a href='{DASHBOARD_URL}'>Live Dashboard</a>"
    )
    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


# ─── /create ────────────────────────────────────────────────────────────────

async def create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text(
            "⚠️ Add Circlo to a group first, then run /create in the group."
        )
        return

    # Check if circle already exists
    existing = db.get_circle_by_chat(chat.id)
    if existing and existing["status"] in ("recruiting", "active"):
        await update.message.reply_text(
            f"⚠️ A circle already exists in this group (<b>{existing['name']}</b>). "
            f"Status: {existing['status']}.",
            parse_mode="HTML"
        )
        return

    # Parse args: /create <name> <amount> <max_members> [cycle_days]
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: <code>/create &lt;name&gt; &lt;amount_cUSD&gt; &lt;max_members&gt; [cycle_days]</code>\n\n"
            "Example: <code>/create MyCrew 10 5 7</code>\n"
            "Creates a 5-member circle, 10 cUSD/round, 7-day cycles.",
            parse_mode="HTML"
        )
        return

    name = args[0]
    try:
        amount = float(args[1])
        max_members = int(args[2])
        cycle_days = int(args[3]) if len(args) > 3 else 7
    except ValueError:
        await update.message.reply_text("⚠️ Invalid arguments. Amount must be a number, members must be an integer.")
        return

    if amount < 1:
        await update.message.reply_text("⚠️ Minimum contribution amount is 1 cUSD.")
        return

    if max_members < 2 or max_members > 20:
        await update.message.reply_text("⚠️ Circle size must be between 2 and 20 members.")
        return

    circle_id = db.create_circle(
        chat_id=chat.id,
        admin_id=user.id,
        name=name,
        contribution_amount=amount,
        max_members=max_members,
        cycle_days=cycle_days,
    )

    await update.message.reply_text(
        f"✅ <b>Circle '{name}' created!</b>\n\n"
        f"💰 Contribution: <b>{amount} cUSD</b> per round\n"
        f"👥 Members needed: <b>{max_members}</b>\n"
        f"📅 Cycle: <b>{cycle_days} days</b>\n\n"
        f"Members: run <code>/join</code> to get your wallet and join the circle.\n"
        f"Circle starts automatically when all {max_members} members have joined.",
        parse_mode="HTML"
    )


# ─── /join ──────────────────────────────────────────────────────────────────

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("⚠️ Run /join in the group where the circle was created.")
        return

    circle = db.get_circle_by_chat(chat.id)
    if not circle:
        await update.message.reply_text("⚠️ No circle found in this group. Admin should run /create first.")
        return

    if circle["status"] != "recruiting":
        await update.message.reply_text(
            f"⚠️ Circle is already <b>{circle['status']}</b>. Joining is closed.",
            parse_mode="HTML"
        )
        return

    existing_member = db.get_member(circle["id"], user.id)
    if existing_member:
        await update.message.reply_text(
            f"✅ You're already in the circle!\n\n"
            f"Your wallet: <code>{existing_member['wallet_address']}</code>",
            parse_mode="HTML"
        )
        return

    count = db.member_count(circle["id"])
    if count >= circle["max_members"]:
        await update.message.reply_text("⚠️ This circle is full.")
        return

    # Generate wallet
    address, encrypted_key = w.generate_wallet()

    db.add_member(
        circle_id=circle["id"],
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        wallet_address=address,
        encrypted_key=encrypted_key,
    )

    new_count = count + 1
    spots_left = circle["max_members"] - new_count

    # Fund wallet with small CELO for gas
    try:
        w.fund_wallet_for_gas(address, 0.005)
    except Exception as e:
        logger.warning(f"Could not fund gas for {address}: {e}")

    await update.message.reply_text(
        f"🎉 <b>Welcome to '{circle['name']}'!</b>\n\n"
        f"Your Celo wallet has been created:\n"
        f"<code>{address}</code>\n\n"
        f"💰 Deposit <b>{circle['contribution_amount']} cUSD</b> to this address before the first round deadline.\n\n"
        f"👥 {new_count}/{circle['max_members']} members joined"
        + (f" — {spots_left} spot(s) left." if spots_left > 0 else " — Circle is full! Starting now..."),
        parse_mode="HTML"
    )

    # Auto-start if full
    if new_count >= circle["max_members"]:
        started = p.start_circle(circle["id"])
        members = db.get_members(circle["id"])
        payout_order = json.loads(started["payout_order"])

        order_lines = []
        for pos, mid in enumerate(payout_order, 1):
            for m in members:
                if m["id"] == mid:
                    name = f"@{m['username']}" if m.get("username") else m.get("full_name", "member")
                    order_lines.append(f"Round {pos}: {name}")

        deadline_str = format_deadline(started["next_deadline"])

        await update.message.reply_text(
            f"🚀 <b>Circle '{circle['name']}' is now ACTIVE!</b>\n\n"
            f"📋 <b>Payout Order:</b>\n" + "\n".join(order_lines) + "\n\n"
            f"⏰ <b>First deadline: {deadline_str}</b>\n\n"
            f"Everyone: run /pay to make your Round 1 contribution of "
            f"<b>{circle['contribution_amount']} cUSD</b>.",
            parse_mode="HTML"
        )


# ─── /pay ───────────────────────────────────────────────────────────────────

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    circle = db.get_circle_by_chat(chat.id)
    if not circle:
        await update.message.reply_text("⚠️ No active circle in this group.")
        return

    await update.message.reply_text("⏳ Processing your contribution on Celo...")

    result = p.process_contribution(circle["id"], user.id)

    if not result["success"]:
        if result.get("wallet"):
            await update.message.reply_text(
                f"⚠️ <b>Insufficient balance</b>\n\n"
                f"You need <b>{result['needed']} cUSD</b> but your wallet has <b>{result['balance']:.4f} cUSD</b>.\n\n"
                f"Deposit cUSD to:\n<code>{result['wallet']}</code>\n\n"
                f"Then run /pay again.",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(f"⚠️ {result['error']}")
        return

    tx = result["tx_hash"]
    contributed = result["contributed"]
    total = result["total"]

    await update.message.reply_text(
        f"✅ <b>Contribution confirmed!</b>\n\n"
        f"💸 <b>{result['amount']} cUSD</b> received (fee: {result['fee']} cUSD)\n"
        f"🔗 <a href='https://celoscan.io/tx/{tx}'>View on CeloScan</a>\n\n"
        f"📊 Round {result['round']}: {contributed}/{total} members paid",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    # Auto-payout if everyone has paid
    if result["all_paid"]:
        await update.message.reply_text("🎯 All members have paid! Executing payout...")
        payout = p.execute_payout(circle["id"])

        if payout["success"]:
            recipient = payout["recipient"]
            name = recipient.get("username") or recipient.get("full_name", "member")
            if recipient.get("username"):
                name = f"@{name}"

            await update.message.reply_text(
                f"🎉 <b>Round {payout['round']} Payout Complete!</b>\n\n"
                f"💰 <b>{payout['amount']:.2f} cUSD</b> sent to <b>{name}</b>\n"
                f"🔗 <a href='https://celoscan.io/tx/{payout['tx_hash']}'>View on CeloScan</a>\n\n"
                f"Round {payout['next_round']} is now open.",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(f"⚠️ Payout error: {payout['error']}")


# ─── /status ────────────────────────────────────────────────────────────────

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    circle = db.get_circle_by_chat(chat.id)

    if not circle:
        await update.message.reply_text("⚠️ No circle found in this group.")
        return

    if circle["status"] == "recruiting":
        count = db.member_count(circle["id"])
        await update.message.reply_text(
            f"⏳ <b>'{circle['name']}'</b> is recruiting.\n\n"
            f"👥 {count}/{circle['max_members']} members joined.\n"
            f"Run /join to take your spot.",
            parse_mode="HTML"
        )
        return

    s = p.get_circle_status(circle["id"])

    paid_names = [
        f"✅ @{m['username']}" if m.get("username") else f"✅ {m.get('full_name', 'member')}"
        for m in s["paid"]
    ]
    unpaid_names = [
        f"⏳ @{m['username']}" if m.get("username") else f"⏳ {m.get('full_name', 'member')}"
        for m in s["unpaid"]
    ]

    recipient = s["recipient"]
    recipient_name = ""
    if recipient:
        recipient_name = f"@{recipient['username']}" if recipient.get("username") else recipient.get("full_name", "?")

    deadline_str = format_deadline(s["deadline"]) if s["deadline"] else "Not set"

    lines = [f"📊 <b>{circle['name']} — Round {s['round']}</b>\n"]
    lines.append(f"⏰ Deadline: <b>{deadline_str}</b>")
    lines.append(f"🏆 This round's payout goes to: <b>{recipient_name}</b>\n")
    lines += paid_names + unpaid_names
    lines.append(f"\n💰 Contribution: <b>{circle['contribution_amount']} cUSD</b>")
    lines.append(f"📊 <a href='{DASHBOARD_URL}'>Full Dashboard</a>")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


# ─── /balance ───────────────────────────────────────────────────────────────

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    circle = db.get_circle_by_chat(chat.id)
    if not circle:
        await update.message.reply_text("⚠️ No circle found in this group.")
        return

    member = db.get_member(circle["id"], user.id)
    if not member:
        await update.message.reply_text("⚠️ You are not a member of this circle. Run /join first.")
        return

    cusd_bal = w.get_cusd_balance(member["wallet_address"])
    celo_bal = w.get_celo_balance(member["wallet_address"])

    await update.message.reply_text(
        f"👛 <b>Your Circlo Wallet</b>\n\n"
        f"<code>{member['wallet_address']}</code>\n\n"
        f"💵 cUSD: <b>{cusd_bal:.4f}</b>\n"
        f"⛽ CELO: <b>{celo_bal:.6f}</b>\n\n"
        f"Need {circle['contribution_amount']} cUSD to contribute this round.",
        parse_mode="HTML"
    )


# ─── /wallet ────────────────────────────────────────────────────────────────

async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    circle = db.get_circle_by_chat(chat.id)
    if not circle:
        await update.message.reply_text("⚠️ No circle found in this group.")
        return

    member = db.get_member(circle["id"], user.id)
    if not member:
        await update.message.reply_text("⚠️ You are not a member. Run /join first.")
        return

    await update.message.reply_text(
        f"🔑 <b>Your Deposit Address</b>\n\n"
        f"<code>{member['wallet_address']}</code>\n\n"
        f"Send cUSD (on Celo network) to this address to fund your contributions.\n"
        f"Minimum needed: <b>{circle['contribution_amount']} cUSD</b>",
        parse_mode="HTML"
    )


# ─── /history ───────────────────────────────────────────────────────────────

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    circle = db.get_circle_by_chat(chat.id)

    if not circle:
        await update.message.reply_text("⚠️ No circle found in this group.")
        return

    payouts = db.get_payouts(circle["id"])

    if not payouts:
        await update.message.reply_text("No completed rounds yet.")
        return

    lines = [f"📜 <b>{circle['name']} — Payout History</b>\n"]
    for payout in payouts:
        name = payout.get("username") or payout.get("full_name") or "member"
        if payout.get("username"):
            name = f"@{name}"
        tx = payout.get("tx_hash", "")
        tx_link = f"<a href='https://celoscan.io/tx/{tx}'>tx</a>" if tx else ""
        lines.append(
            f"Round {payout['round_number']}: <b>{payout['amount']:.2f} cUSD</b> → {name} {tx_link}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ─── /payout (admin manual trigger) ────────────────────────────────────────

async def payout_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    circle = db.get_circle_by_chat(chat.id)
    if not circle:
        await update.message.reply_text("⚠️ No circle found.")
        return

    if str(user.id) != str(circle["admin_id"]):
        await update.message.reply_text("⚠️ Only the circle admin can trigger a manual payout.")
        return

    await update.message.reply_text("⏳ Executing payout...")
    result = p.execute_payout(circle["id"])

    if result["success"]:
        recipient = result["recipient"]
        name = recipient.get("username") or recipient.get("full_name", "member")
        if recipient.get("username"):
            name = f"@{name}"
        await update.message.reply_text(
            f"✅ <b>Payout executed!</b>\n\n"
            f"💸 <b>{result['amount']:.2f} cUSD</b> → <b>{name}</b>\n"
            f"🔗 <a href='https://celoscan.io/tx/{result['tx_hash']}'>View on CeloScan</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(f"⚠️ Payout failed: {result['error']}")


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("payout", payout_cmd))

    # Run scheduler alongside bot
    asyncio.create_task(sched.scheduler_loop())

    print("[CIRCLO] Bot starting...")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
