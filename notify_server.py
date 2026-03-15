"""
MCXC Push Notification Server
------------------------------
Tiny Flask server that sends Web Push notifications to subscribed devices.
Deployed on Render.com (free tier) — sleeps when idle, wakes on request.

Endpoints:
  POST /send-announcement  — called by Streamlit when a new announcement posts
  POST /send-results       — called by Streamlit when meet results are published
  POST /subscribe          — called by the browser to store a push subscription
  GET  /health             — health check

Environment variables (set in Render dashboard):
  VAPID_PRIVATE_KEY   — your VAPID private key
  VAPID_PUBLIC_KEY    — your VAPID public key
  VAPID_SUBJECT       — mailto:your@email.com
  FIREBASE_DB_URL     — https://mcxc-timer-default-rtdb.firebaseio.com
  NOTIFY_SECRET       — a secret string Streamlit sends to authenticate calls
"""

import os
import json
import requests
from flask import Flask, request, jsonify
from pywebpush import webpush, WebPushException

app = Flask(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_SUBJECT     = os.environ.get("VAPID_SUBJECT", "mailto:matthew.t.bennett95@gmail.com")
FIREBASE_DB_URL   = os.environ.get("FIREBASE_DB_URL", "https://mcxc-timer-default-rtdb.firebaseio.com")
NOTIFY_SECRET     = os.environ.get("NOTIFY_SECRET", "")


def get_subscriptions():
    """Fetch all push subscriptions from Firebase."""
    try:
        url  = f"{FIREBASE_DB_URL}/subscriptions.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200 or not resp.json():
            return []
        data = resp.json()
        # Each value is a subscription object {endpoint, keys: {p256dh, auth}}
        return [v for v in data.values() if v and isinstance(v, dict) and "endpoint" in v]
    except Exception as e:
        print(f"Error fetching subscriptions: {e}")
        return []


def send_push(subscription, payload):
    """Send a Web Push notification to one subscription. Returns True on success."""
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except WebPushException as e:
        # 410 Gone = subscription expired/unsubscribed — clean it up
        if e.response and e.response.status_code == 410:
            remove_subscription(subscription.get("endpoint", ""))
        print(f"Push failed: {e}")
        return False
    except Exception as e:
        print(f"Push error: {e}")
        return False


def remove_subscription(endpoint):
    """Remove an expired subscription from Firebase."""
    try:
        url  = f"{FIREBASE_DB_URL}/subscriptions.json"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200 or not resp.json():
            return
        data = resp.json()
        for key, val in data.items():
            if val and val.get("endpoint") == endpoint:
                requests.delete(f"{FIREBASE_DB_URL}/subscriptions/{key}.json", timeout=5)
                break
    except Exception as e:
        print(f"Error removing subscription: {e}")


def broadcast(payload):
    """Send payload to all subscriptions. Returns (sent, failed) counts."""
    subs = get_subscriptions()
    sent, failed = 0, 0
    for sub in subs:
        if send_push(sub, payload):
            sent += 1
        else:
            failed += 1
    return sent, failed


def check_secret():
    """Verify the NOTIFY_SECRET header."""
    if not NOTIFY_SECRET:
        return True  # No secret configured — allow (set one in Render!)
    return request.headers.get("X-Notify-Secret") == NOTIFY_SECRET


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "subscriptions": len(get_subscriptions())})


@app.route("/subscribe", methods=["POST"])
def subscribe():
    """Store a push subscription sent from the browser."""
    data = request.get_json(silent=True)
    if not data or "endpoint" not in data:
        return jsonify({"error": "Invalid subscription"}), 400
    try:
        # Use a hash of the endpoint as the Firebase key
        import hashlib
        key = hashlib.md5(data["endpoint"].encode()).hexdigest()[:16]
        url = f"{FIREBASE_DB_URL}/subscriptions/{key}.json"
        requests.put(url, json=data, timeout=5)
        return jsonify({"status": "subscribed"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send-announcement", methods=["POST"])
def send_announcement():
    """Send a push notification for a new announcement."""
    if not check_secret():
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    title   = body.get("title", "New Announcement")
    message = body.get("message", "Check the team dashboard for a new announcement.")
    payload = {
        "type":    "announcement",
        "title":   f"MCXC — {title}",
        "body":    message,
        "url":     body.get("url", "/"),
        "icon":    "/mcxc_logo.png",
    }
    sent, failed = broadcast(payload)
    return jsonify({"sent": sent, "failed": failed}), 200


@app.route("/send-results", methods=["POST"])
def send_results():
    """Send a push notification for published meet results."""
    if not check_secret():
        return jsonify({"error": "Unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    meet    = body.get("meet", "Recent Meet")
    payload = {
        "type":    "results",
        "title":   f"MCXC — Results Posted",
        "body":    f"{meet} results are now available. Check the team leaderboard!",
        "url":     body.get("leaderboard_url", "/"),
        "icon":    "/mcxc_logo.png",
    }
    sent, failed = broadcast(payload)
    return jsonify({"sent": sent, "failed": failed}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
