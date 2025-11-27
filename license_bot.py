import json
import logging
import random
import string
from typing import Dict, Any
import multiprocessing
multiprocessing.freeze_support()

from telegram.ext import ApplicationBuilder, CommandHandler
...

import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================================
# CONFIG
# ================================
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Newbie2402/wg-licenses")
LICENSE_FILE_PATH = os.getenv("LICENSE_FILE_PATH", "licenses.json")
ADMIN_CHAT_ID = 1459150994  # ganti dengan chat ID kamu

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# HELPERS
# ================================

def get_github_file() -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LICENSE_FILE_PATH}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    data = resp.json()
    content = data["content"]
    sha = data["sha"]

    import base64
    decoded = base64.b64decode(content).decode("utf-8")
    return {"json": json.loads(decoded), "sha": sha}


def update_github_file(new_json: Dict[str, Any], sha: str, message: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LICENSE_FILE_PATH}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    import base64

    encoded = base64.b64encode(json.dumps(new_json, indent=2).encode()).decode()

    payload = {
        "message": message,
        "content": encoded,
        "sha": sha,
    }

    resp = requests.put(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()


def gen_key(prefix="WG"):
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=12))
    return f"{prefix}-" + "-".join([body[i:i+4] for i in range(0, 12, 4)])


def admin_only(func):
    async def wrap(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_CHAT_ID:
            await update.message.reply_text("⚠️ Kamu bukan admin.")
            return
        return await func(update, context)
    return wrap

# ================================
# COMMANDS
# ================================

@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "WG License Bot Siap!\n\n"
        "Perintah:\n"
        "/gen <HWID> <allowed_devices>\n"
        "/ban <KEY>\n"
        "/unban <KEY>"
    )


@admin_only
async def cmd_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Format: /gen <HWID> <allowed_devices>")
        return

    hwid = context.args[0].upper()
    allowed = int(context.args[1])

    # Load file
    data = get_github_file()
    j = data["json"]
    sha = data["sha"]

    if "keys" not in j:
        j["keys"] = {}

    # Generate unique key
    while True:
        key = gen_key()
        if key not in j["keys"]:
            break

    # Save
    j["keys"][key] = {
        "allowed_devices": allowed,
        "devices": [hwid],
        "banned": False
    }

    update_github_file(j, sha, f"Add key {key}")

    await update.message.reply_text(
        f"✅ License dibuat!\n\n"
        f"Key: `{key}`\n"
        f"HWID pertama: `{hwid}`\n"
        f"Max device: {allowed}",
        parse_mode="Markdown"
    )


@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /ban <KEY>")
        return

    key = context.args[0].strip()

    data = get_github_file()
    j = data["json"]
    sha = data["sha"]

    if key not in j["keys"]:
        await update.message.reply_text("Key tidak ditemukan!")
        return

    j["keys"][key]["banned"] = True
    update_github_file(j, sha, f"Ban key {key}")

    await update.message.reply_text(f"🚫 Key `{key}` dibanned.", parse_mode="Markdown")


@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: /unban <KEY>")
        return

    key = context.args[0].strip()

    data = get_github_file()
    j = data["json"]
    sha = data["sha"]

    if key not in j["keys"]:
        await update.message.reply_text("Key tidak ditemukan!")
        return

    j["keys"][key]["banned"] = False
    update_github_file(j, sha, f"Unban key {key}")

    await update.message.reply_text(f"✅ Key `{key}` di-unban.", parse_mode="Markdown")


# ================================
# MAIN FINAL untuk python-telegram-bot v21+
# ================================
if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("gen", cmd_gen))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(CommandHandler("unban", cmd_unban))

    print("BOT RUNNING...")
    application.run_polling()


