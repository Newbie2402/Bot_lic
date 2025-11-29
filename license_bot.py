import os
import json
import random
import string
import base64
import logging
import requests
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================================================
# CONFIG (diambil dari Railway ENV)
# ==========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Newbie2402/wg-licenses")
LICENSE_FILE_PATH = os.getenv("LICENSE_FILE_PATH", "licenses.json")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "1459150994"))

if not BOT_TOKEN or not GITHUB_TOKEN:
    raise RuntimeError("ENV VAR BOT_TOKEN atau GITHUB_TOKEN tidak ditemukan!")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LICENSE_FILE_PATH}"


# ==========================================================
# GITHUB HELPERS
# ==========================================================
def github_get():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    r = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    decoded = base64.b64decode(data["content"]).decode("utf-8")
    return json.loads(decoded), data["sha"]


def github_update(new_json, sha, message):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    encoded = base64.b64encode(json.dumps(new_json, indent=2).encode()).decode()

    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }

    r = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=15)
    r.raise_for_status()


def gen_key(prefix="WG"):
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-" + "-".join([body[i:i+4] for i in range(0, 12, 4)])


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_CHAT_ID:
            await update.message.reply_text("⚠️ Kamu bukan admin!")
            return
        return await func(update, context)

    return wrapper


# ==========================================================
# COMMANDS
# ==========================================================

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "WG License Bot Ready!\n\n"
        "Commands:\n"
        "/gen <HWID> <allowed_devices> <days>\n"
        "/ban <KEY>\n"
        "/unban <KEY>"
    )


@admin_only
async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Format: /gen <HWID> <allowed_devices> <days>")
        return

    hwid = context.args[0].upper()
    allowed = int(context.args[1])
    days = int(context.args[2])

    expire_at = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")

    data, sha = github_get()

    if "keys" not in data:
        data["keys"] = {}

    while True:
        key = gen_key()
        if key not in data["keys"]:
            break

    data["keys"][key] = {
        "allowed_devices": allowed,
        "devices": [hwid],
        "banned": False,
        "expire_at": expire_at
    }

    github_update(data, sha, f"Add key {key}")

    await update.message.reply_text(
        f"✅ License dibuat!\n\n"
        f"Key: `{key}`\n"
        f"HWID pertama: `{hwid}`\n"
        f"Max device: {allowed}\n"
        f"Expired: `{expire_at}`",
        parse_mode="Markdown"
    )


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /ban <KEY>")
        return

    key = context.args[0].strip()

    data, sha = github_get()
    if key not in data.get("keys", {}):
        await update.message.reply_text("Key tidak ditemukan!")
        return

    data["keys"][key]["banned"] = True
    github_update(data, sha, f"Ban {key}")

    await update.message.reply_text(f"🚫 Key `{key}` dibanned.", parse_mode="Markdown")


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /unban <KEY>")
        return

    key = context.args[0].strip()

    data, sha = github_get()
    if key not in data.get("keys", {}):
        await update.message.reply_text("Key tidak ditemukan!")
        return

    data["keys"][key]["banned"] = False
    github_update(data, sha, f"Unban {key}")

    await update.message.reply_text(f"✅ Key `{key}` di-unban.", parse_mode="Markdown")


# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    logger.info("🔥 Starting WG License Bot on Railway…")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gen", cmd_gen))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))

    app.run_polling()
