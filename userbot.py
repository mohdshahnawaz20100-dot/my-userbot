#!/usr/bin/env python3
# CODERNOVA SINGLE USER USERBOT

import os, sys, json, asyncio, random, re, time, logging, shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote as url_quote

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

from telethon import TelegramClient, events, functions
from telethon.tl.types import ChatBannedRights
from telethon.errors import FloodWaitError
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import EditChatTitleRequest
from telethon.tl.functions.channels import EditTitleRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji
from telethon.sessions import StringSession

load_dotenv()

API_ID       = int(os.getenv("API_ID", "37550071"))
API_HASH     = os.getenv("API_HASH", "eca739f28db4f12737a0d418f4a77343")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+918090007204")
OWNER_ID     = int(os.getenv("OWNER_ID", "8850736433"))

STRING_SESSION = os.getenv("STRING_SESSION", "")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "1e74d518ef89c703e791594f953df2a4")
NEWS_API_KEY    = os.getenv("NEWS_API_KEY", "c25f877f4c654be7980fee363be93302")

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/clonex_data"))
DATA_DIR.mkdir(exist_ok=True, parents=True)
TEMP_DIR = DATA_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True, parents=True)

DB_FILE = DATA_DIR / "userbot_db.json"

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO, datefmt='%H:%M:%S')
log = logging.getLogger("CN_USERBOT")

if not STRING_SESSION:
    log.error("❌ STRING_SESSION missing!")
    exit(1)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

db = {}

def load_db():
    global db
    defaults = {
        "owner_id": OWNER_ID,
        "admins": [],
        "ghost_data": {},
        "ghost_on": False,
        "auto_react_dm_enabled": False,
        "auto_react_group_enabled": False,
        "auto_react_emojis": ['🥰','😭','😂','🤗','🌝','😇','🤩','😎','🫡','🤝','👍','❤️','❤️‍🔥','🔥','🙈','👀','😁','🤨','🕊','🎉','👏','⚡️','🤷','👌','🧑‍💻','💔','✍️','👻','🤔'],
        "auto_reply": {"enabled": False, "mode": "always",
            "text": "The owner is busy with some personal work at the moment😌Please wait until they are back online🥀",
            "replied_users": []},
        "pmguard": {"enabled": False},
        "pm_warnings": {},
        "approved": [],
        "blacklist": [],
        "muted": {},
        "gmuted": {},
        "blocklist": [],
        "locked_groups": [],
        "clone_data": {},
        "reply_raid": {},
        "rr_raid": {},
        "flag_raid": {},
        "heart_raid": {},
        "spam_running": False,
        "fast_gc_data": {},
        "start_time": datetime.now().isoformat()
    }
    if DB_FILE.exists():
        try:
            db = json.loads(DB_FILE.read_text())
        except Exception:
            db = {}
    for k, v in defaults.items():
        if k not in db:
            db[k] = v

def save_db():
    try:
        data = dict(db)
        for key in ["reply_raid", "rr_raid", "flag_raid", "heart_raid"]:
            if key in data and isinstance(data[key], dict):
                nd = {}
                for k, v in data[key].items():
                    if isinstance(v, set):
                        nd[str(k)] = list(v)
                    else:
                        nd[str(k)] = v
                data[key] = nd
        DB_FILE.write_text(json.dumps(data, default=str, indent=2))
    except Exception as e:
        log.error(f"save_db: {e}")

load_db()

def get_args(msg):
    t = msg.text or ''
    for m in re.finditer(r'\.\w+\s*(.*)', t):
        return m.group(1).strip()
    return ''

def is_owner(uid):
    return uid == db.get("owner_id", OWNER_ID)

def is_admin(uid):
    return uid == db.get("owner_id", OWNER_ID) or uid in db["admins"]

async def resolve_user(client, msg, text):
    if msg.is_reply:
        return (await msg.get_reply_message()).sender_id
    if text:
        m = re.search(r'@(\w+)', text)
        if m:
            try:
                u = await client.get_entity(m.group(1))
                return u.id
            except Exception:
                return None
        try:
            u = await client.get_entity(int(text))
            return u.id
        except Exception:
            return None
    return None

def user_link(uid):
    return f"[User](tg://user?id={uid})"

async def delete_command_message(event, delay=2):
    try:
        await asyncio.sleep(delay)
        await event.delete()
    except Exception:
        pass

async def raid_loop(event, target_id, raid_dict, message_func, delay=1):
    chat_id = event.chat_id
    if chat_id not in raid_dict:
        raid_dict[chat_id] = set()
    if isinstance(raid_dict[chat_id], list):
        raid_dict[chat_id] = set(raid_dict[chat_id])
    raid_dict[chat_id].add(target_id)
    while target_id in raid_dict.get(chat_id, set()):
        try:
            await message_func()
            await asyncio.sleep(delay)
        except Exception:
            break

async def reply_to_target(event, text):
    if event.reply_to_msg_id:
        try:
            await event.client.send_message(event.chat_id, text, reply_to=event.reply_to_msg_id)
            return
        except Exception:
            pass
    await event.reply(text)

RAID_MESSAGES = ["🚀 Raid #{n}!", "💥 Spam #{n}!", "🔥 Attack #{n}!", "⚡ Raid #{n}", "🌀 Flood #{n}"]
REPLY_MESSAGES = ["💬 Spam reply!", "🤖 Bot attack!", "📢 Hey there!", "⚠️ Raid mode!", "🌀 Flooding!"]
SPAM_EMOJIS = ['🌟', '✨', '🔥', '💥', '⚡', '🌀', '🚀', '🎯', '💫', '⭐']
DEFAULT_SPAM_TEXTS = [
    "🔥 Spam attack!", "🚀 Flooding the chat!", "💥 Here comes the spam!",
    "🌀 Spam mode activated!", "⚡ Lightning spam!", "🎯 Target acquired!",
    "💫 Spam spam spam!", "🌟 Spam with style!", "✨ Spam is life!",
    "🔥 Spam till you drop!"
]

def cmd(pattern, owner_only=False, delete_cmd=True):
    def wrapper(func):
        @client.on(events.NewMessage(pattern=rf'^\.{pattern}(\s.*)?$'))
        async def handler(event):
            if owner_only and not is_owner(event.sender_id):
                return
            if not owner_only and not is_owner(event.sender_id) and not is_admin(event.sender_id):
                return
            try:
                if delete_cmd:
                    asyncio.create_task(delete_command_message(event, 2))
                await func(event)
                save_db()
            except FloodWaitError as e:
                log.warning(f"Flood wait {e.seconds}s")
                await event.reply(f"⏳ Flood wait {e.seconds} sec...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                log.error(f"Cmd .{pattern} error: {e}")
                await event.reply(f"❌ Error: {str(e)[:200]}")
        return handler
    return wrapper
