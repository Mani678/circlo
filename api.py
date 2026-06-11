"""
Lightweight Flask API serving dashboard data.
Runs alongside the bot on a separate port (5050).
nginx proxies /api/* to this and serves the static dashboard.
"""

from flask import Flask, jsonify
import db
from config import DB_PATH

app = Flask(__name__)


@app.route("/api/dashboard")
def dashboard():
    circles = db.get_all_circles()
    all_contributions = db.get_all_contributions()
    all_payouts = db.get_all_payouts()

    # Enrich circles with member count
    enriched_circles = []
    total_members = 0
    for circle in circles:
        count = db.member_count(circle["id"])
        total_members += count
        enriched_circles.append({**circle, "member_count": count})

    # Enrich payouts with circle name
    circle_map = {c["id"]: c["name"] for c in circles}

    enriched_payouts = []
    for p in all_payouts:
        enriched_payouts.append({
            **p,
            "circle_name": circle_map.get(p["circle_id"], "—")
        })

    # Enrich contributions with circle name and member info
    enriched_contributions = []
    for c in all_contributions:
        member = None
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT * FROM members WHERE id = ?", (c["member_id"],))
            row = cur.fetchone()
            conn.close()
            if row:
                member = dict(row)
        except:
            pass

        enriched_contributions.append({
            **c,
            "circle_name": circle_map.get(c["circle_id"], "—"),
            "username": member["username"] if member else None,
            "full_name": member["full_name"] if member else None,
        })

    total_transactions = (
        len(all_contributions) +
        len(all_payouts) +
        _count_penalties()
    )

    return jsonify({
        "circles": enriched_circles,
        "payouts": enriched_payouts,
        "contributions": enriched_contributions,
        "total_members": total_members,
        "total_transactions": total_transactions,
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "agent": "Circlo"})


def _count_penalties():
    try:
        conn = db.get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM penalties")
        row = c.fetchone()
        conn.close()
        return row["cnt"]
    except:
        return 0


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
