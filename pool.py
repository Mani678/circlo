import json
import random
from datetime import datetime, timedelta
from typing import Optional

import db
import wallet as w
from config import PLATFORM_FEE_PCT, PENALTY_PCT, PLATFORM_WALLET


def start_circle(circle_id: int) -> dict:
    """
    Called when max_members have joined.
    Assigns random payout order, sets first deadline, activates circle.
    """
    members = db.get_members(circle_id)
    circle = db.get_circle_by_id(circle_id)

    # Randomize payout order
    member_ids = [m["id"] for m in members]
    random.shuffle(member_ids)

    # Set first deadline
    cycle_days = circle["cycle_days"]
    deadline = (datetime.utcnow() + timedelta(days=cycle_days)).isoformat()

    db.update_circle(
        circle_id,
        status="active",
        payout_order=json.dumps(member_ids),
        next_deadline=deadline,
        current_round=1,
    )

    # Assign payout positions to members
    for pos, member_id in enumerate(member_ids, start=1):
        db.update_member(member_id, payout_position=pos)

    return db.get_circle_by_id(circle_id)


def get_round_recipient(circle_id: int, round_number: int) -> Optional[dict]:
    """Returns the member who receives the payout for this round."""
    circle = db.get_circle_by_id(circle_id)
    payout_order = json.loads(circle["payout_order"])
    if round_number > len(payout_order):
        return None
    member_id = payout_order[round_number - 1]
    members = db.get_members(circle_id)
    for m in members:
        if m["id"] == member_id:
            return m
    return None


def process_contribution(circle_id: int, user_id: str) -> dict:
    """
    Called when a member triggers /pay.
    Transfers cUSD from their wallet to platform wallet.
    Records contribution.
    Returns result dict.
    """
    circle = db.get_circle_by_id(circle_id)
    member = db.get_member(circle_id, user_id)

    if not member:
        return {"success": False, "error": "You are not a member of this circle."}

    if circle["status"] != "active":
        return {"success": False, "error": "Circle is not active yet."}

    round_number = circle["current_round"]

    if db.has_contributed(circle_id, member["id"], round_number):
        return {"success": False, "error": "You have already contributed this round."}

    amount = circle["contribution_amount"]
    balance = w.get_cusd_balance(member["wallet_address"])

    if balance < amount:
        return {
            "success": False,
            "error": f"Insufficient balance. You need {amount} cUSD but have {balance:.4f} cUSD.",
            "wallet": member["wallet_address"],
            "needed": amount,
            "balance": balance,
        }

    # Take platform fee
    fee = round(amount * PLATFORM_FEE_PCT, 6)
    net = round(amount - fee, 6)

    try:
        # Transfer full amount to platform wallet first
        tx_hash = w.transfer_cusd(
            member["encrypted_key"],
            PLATFORM_WALLET,
            amount
        )

        db.record_contribution(
            circle_id=circle_id,
            member_id=member["id"],
            round_number=round_number,
            amount=net,
            tx_hash=tx_hash,
            status="confirmed"
        )

        # Check if all members have contributed — trigger payout if so
        contributions = db.get_round_contributions(circle_id, round_number)
        total_members = db.member_count(circle_id)

        result = {
            "success": True,
            "tx_hash": tx_hash,
            "amount": amount,
            "fee": fee,
            "net": net,
            "round": round_number,
            "contributed": len(contributions),
            "total": total_members,
            "all_paid": len(contributions) >= total_members,
        }

        return result

    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_payout(circle_id: int) -> dict:
    """
    Execute the payout for the current round.
    Sends pooled funds to the round's recipient.
    """
    circle = db.get_circle_by_id(circle_id)
    round_number = circle["current_round"]
    recipient = get_round_recipient(circle_id, round_number)

    if not recipient:
        return {"success": False, "error": "No recipient found for this round."}

    contributions = db.get_round_contributions(circle_id, round_number)
    total_contributed = sum(c["amount"] for c in contributions)

    # Add any penalties from this round
    conn = db.get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM penalties WHERE circle_id = ? AND round_number = ?
    """, (circle_id, round_number))
    penalty_total = c.fetchone()["total"]
    conn.close()

    payout_amount = round(total_contributed + penalty_total, 6)

    if payout_amount <= 0:
        return {"success": False, "error": "No funds to pay out."}

    try:
        tx_hash = w.platform_transfer_cusd(recipient["wallet_address"], payout_amount)

        db.record_payout(
            circle_id=circle_id,
            round_number=round_number,
            recipient_member_id=recipient["id"],
            amount=payout_amount,
            tx_hash=tx_hash,
            status="confirmed"
        )

        # Advance to next round
        payout_order = json.loads(circle["payout_order"])
        next_round = round_number + 1

        if next_round > len(payout_order):
            # Circle complete
            db.update_circle(circle_id, status="completed", current_round=next_round)
        else:
            next_deadline = (datetime.utcnow() + timedelta(days=circle["cycle_days"])).isoformat()
            db.update_circle(
                circle_id,
                current_round=next_round,
                next_deadline=next_deadline
            )

        return {
            "success": True,
            "tx_hash": tx_hash,
            "recipient": recipient,
            "amount": payout_amount,
            "round": round_number,
            "next_round": next_round,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def apply_penalties(circle_id: int) -> list:
    """
    Called at deadline. For each member who hasn't contributed,
    transfer penalty from their wallet to platform wallet.
    Returns list of penalty results.
    """
    circle = db.get_circle_by_id(circle_id)
    round_number = circle["current_round"]
    members = db.get_members(circle_id)
    results = []

    penalty_amount = round(circle["contribution_amount"] * PENALTY_PCT, 6)

    for member in members:
        if db.has_contributed(circle_id, member["id"], round_number):
            continue

        # Try to deduct penalty from their wallet
        balance = w.get_cusd_balance(member["wallet_address"])

        if balance >= penalty_amount:
            try:
                tx_hash = w.transfer_cusd(
                    member["encrypted_key"],
                    PLATFORM_WALLET,
                    penalty_amount
                )
                db.record_penalty(
                    circle_id=circle_id,
                    member_id=member["id"],
                    round_number=round_number,
                    amount=penalty_amount,
                    tx_hash=tx_hash,
                    reason="Missed contribution deadline"
                )
                results.append({
                    "member": member,
                    "penalized": True,
                    "amount": penalty_amount,
                    "tx_hash": tx_hash
                })
            except Exception as e:
                results.append({
                    "member": member,
                    "penalized": False,
                    "error": str(e)
                })
        else:
            # Mark as penalized but wallet insufficient
            db.record_penalty(
                circle_id=circle_id,
                member_id=member["id"],
                round_number=round_number,
                amount=0,
                tx_hash=None,
                reason="Missed deadline - insufficient balance for penalty"
            )
            results.append({
                "member": member,
                "penalized": False,
                "reason": "Insufficient balance",
                "balance": balance
            })

    return results


def get_circle_status(circle_id: int) -> dict:
    """Returns a full status snapshot for the circle."""
    circle = db.get_circle_by_id(circle_id)
    members = db.get_members(circle_id)
    round_number = circle["current_round"]
    contributions = db.get_round_contributions(circle_id, round_number)
    paid_ids = {c["member_id"] for c in contributions}

    paid = [m for m in members if m["id"] in paid_ids]
    unpaid = [m for m in members if m["id"] not in paid_ids]
    recipient = get_round_recipient(circle_id, round_number)

    return {
        "circle": circle,
        "members": members,
        "round": round_number,
        "paid": paid,
        "unpaid": unpaid,
        "recipient": recipient,
        "contributions": contributions,
        "deadline": circle.get("next_deadline"),
    }
