#!/usr/bin/env python3
# CODERNOVA SINGLE USER USERBOT
# Direct deploy with String Session (Render + GitHub Ready)

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

# ═══════════════ LOAD .env ═══════════════
load_dotenv()

# ═══════════════ CONFIG ═══════════════
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
    log.error("❌ STRING_SESSION missing! Render Environment Variables me daalo.")
    exit(1)

client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# ═══════════════ SIMPLE JSON DB ═══════════════
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

# ═══════════════ HELPERS ═══════════════
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

# ═══════════════ LISTS ═══════════════
RAID_MESSAGES = ["🚀 Raid #{n}!", "💥 Spam #{n}!", "🔥 Attack #{n}!", "⚡ Raid #{n}", "🌀 Flood #{n}"]
REPLY_MESSAGES = ["💬 Spam reply!", "🤖 Bot attack!", "📢 Hey there!", "⚠️ Raid mode!", "🌀 Flooding!"]
SPAM_EMOJIS = ['🌟', '✨', '🔥', '💥', '⚡', '🌀', '🚀', '🎯', '💫', '⭐']
DEFAULT_SPAM_TEXTS = [
    "🔥 Spam attack!", "🚀 Flooding the chat!", "💥 Here comes the spam!",
    "🌀 Spam mode activated!", "⚡ Lightning spam!", "🎯 Target acquired!",
    "💫 Spam spam spam!", "🌟 Spam with style!", "✨ Spam is life!",
    "🔥 Spam till you drop!"
]

# ═══════════════ COMMAND DECORATOR ═══════════════
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

# ═══════════════ BASIC COMMANDS ═══════════════
@cmd('help', delete_cmd=False)
async def help_cmd(event):
    await event.reply("""**⚙️ CLONEXBOT USERBOT ⚙️**

**🔹 Basic Commands**
`.help` — Show menu
`.alive` — Check status
`.profile` — Your profile
`.id` — Get ID
`.info` — Get user info

**🔹 Profile System**
`.clone @user` — Clone profile
`.reclone` — Restore profile
`.ghost` — Ghost mode
`.unghost` — Restore profile

**🔹 Admin Commands**
`.admins` — Admin list
`.addadmin <reply/@id>` — Add admin
`.deladmin <reply/@id>` — Remove admin

**🔹 Mute & Restrict**
`.mute`, `.unmute`, `.gmute`, `.gunmute`
`.lock`, `.unlock`

**🔹 Group Mod**
`.tagall`, `.tagall2`, `.raid`, `.purge`, `.throw`, `.stop`

**🔹 Auto System**
`.autoreact on/off`, `.autoreactg on/off`
`.autoreply on/off/set/reset`
`.pmguard on/off`
`.approve`, `.disapprove`, `.blacklist`, `.removeblacklist`

**🔹 Raid Engine**
`.reply`, `.sreply`, `.rr`, `.srr`, `.flag`, `.sflag`, `.hrr`, `.shrr`

**🔹 Spam & Fast**
`.spray [text]`, `.dspray`
`.fastgc set text`, `.fastgc stop`

**🔹 Fun**
`.ping`, `.flip`, `.dice`

**🔹 Stalk Tools**
`.stalk`, `.allpfp`, `.lastmsg <n>`

**🔹 Music 🎵**
`.lyrics`, `.songinfo`, `.spotify`, `.trending`, `.ringtone`, `.playlist`

**🔹 AI Image 🎨**
`.t2i <prompt>`

**🔹 Animations ✨**
`.animate`, `.spinner`, `.loveu`, `.matrix`, `.hearts`, `.countdown`, `.wave`

**🔹 Fancy Text ✨**
`.hi .hey .bye .welcome .ok .yes .wow .cool .omg .lol`
`.love .hate .sad .good .bad .best .go .fire .boss`
`.text <anything>`, `.banner <word> [font]`

**🔹 Text Art 🎨**
`.gm .gn .hbd .wlc .hello2 .love2 .heyy .gg .flower .gum .howdy .cool2 .hug .hug2 .thnx .purpose`

**🔹 Public Features 🌍**
`.weather city`, `.news [query]`, `.azan city`, `.play song`

**🔹 Image Tools 🖼️**
`.sticker`, `.toimg`, `.blur`, `.img2pdf`

**🔹 Forecast & AQI 🌤️**
`.forecast city`, `.aqi city`
""", parse_mode='markdown')

@cmd('alive', delete_cmd=False)
async def alive_cmd(event):
    start = db.get("start_time", datetime.now().isoformat())
    try:
        uptime = datetime.now() - datetime.fromisoformat(start)
    except Exception:
        uptime = datetime.now() - datetime.now()
    h, r = divmod(int(uptime.total_seconds()), 3600)
    m, s = divmod(r, 60)
    me = await client.get_me()
    my_name = me.first_name or "User"
    caption = ("❛.𝁘ໍ🎭Cl❍n𝛜X.𝁘ໍ  USERBOT IS ALIVE\n"
               "✨\n"
               f"⏳ **UPTIME:** {h}h : {m}m : {s}s\n"
               f"👤 **USER:** {my_name}\n"
               f"👑 **OWNER:** @iVILLAINi\n")
    IMG = "https://i.ibb.co/zVTxPwfX/empty-dark-room-modern-futuristic-sci-fi-background-3d-illustration-35913-2332.jpg"
    try:
        await client.send_file(event.chat_id, IMG, caption=caption, parse_mode='markdown', reply_to=event.message.id)
    except Exception:
        await event.reply(caption, parse_mode='markdown')

@cmd('profile', delete_cmd=False)
async def profile_cmd(event):
    me = await client.get_me()
    await event.reply(f"**👤 Your Profile**\nName: {me.first_name}\nID: `{me.id}`\nUsername: @{me.username or 'None'}", parse_mode='markdown')

@cmd('id', delete_cmd=False)
async def id_cmd(event):
    if event.is_reply:
        msg = await event.get_reply_message()
        uid = msg.sender_id
        await event.reply(f"**User ID:** `{uid}`", parse_mode='markdown')
    else:
        await event.reply(f"**Chat ID:** `{event.chat_id}`", parse_mode='markdown')

@cmd('info', delete_cmd=False)
async def info_cmd(event):
    text = get_args(event.message)
    uid = await resolve_user(client, event.message, text)
    if not uid:
        await event.reply("❌ User not found.")
        return
    try:
        u = await client.get_entity(uid)
        await event.reply(f"**👤 User Info**\nName: {u.first_name}\nID: `{u.id}`\nUsername: @{u.username or 'None'}", parse_mode='markdown')
    except Exception:
        await event.reply("❌ Could not get user info.")

# ═══════════════ PROFILE SYSTEM ═══════════════
@cmd('clone')
async def clone_cmd(event):
    if not is_owner(event.sender_id):
        return
    text = get_args(event.message)
    target_id = await resolve_user(client, event.message, text)
    if not target_id:
        await event.reply("❌ Target not found. Reply or @mention.")
        return
    me = await client.get_me()
    db['clone_data']['orig_first_name'] = me.first_name or ''
    db['clone_data']['orig_last_name'] = me.last_name or ''
    try:
        full_me = await client(functions.users.GetFullUserRequest(id=me.id))
        db['clone_data']['orig_bio'] = full_me.full_user.about or ''
    except Exception:
        db['clone_data']['orig_bio'] = ''
    try:
        photo_dir = DATA_DIR / "original_photos"
        shutil.rmtree(photo_dir, ignore_errors=True)
        photo_dir.mkdir(parents=True, exist_ok=True)
        all_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        photos_list = list(all_photos.photos)
        photos_list.reverse()
        saved_paths = []
        for i, photo in enumerate(photos_list):
            photo_path = str(photo_dir / f"orig_photo_{i:03d}.jpg")
            downloaded = await client.download_media(photo, photo_path)
            if downloaded:
                saved_paths.append(photo_path)
        db['clone_data']['orig_photo_paths'] = saved_paths
    except Exception:
        db['clone_data']['orig_photo_paths'] = []
    try:
        target = await client.get_entity(target_id)
        await client(UpdateProfileRequest(
            first_name=getattr(target, 'first_name', '') or '',
            last_name=getattr(target, 'last_name', '') or ''
        ))
        try:
            full_target = await client(functions.users.GetFullUserRequest(id=target_id))
            bio = getattr(full_target.full_user, 'about', '') or ''
            if bio:
                await client(functions.account.UpdateProfileRequest(about=bio))
        except Exception:
            pass
        try:
            target_photos = await client(functions.photos.GetUserPhotosRequest(user_id=target_id, offset=0, max_id=0, limit=1))
            if target_photos.photos:
                photo_path = str(TEMP_DIR / "clone_temp.jpg")
                await client.download_media(target_photos.photos[0], photo_path)
                if os.path.exists(photo_path):
                    await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
                    os.remove(photo_path)
        except Exception:
            pass
        save_db()
        await event.reply("✅ **Profile Cloned!**")
    except Exception as e:
        await event.reply(f"❌ Clone failed: {str(e)[:100]}")

@cmd('reclone')
async def reclone_cmd(event):
    if not is_owner(event.sender_id):
        return
    cd = db.get("clone_data", {})
    if not cd.get('orig_first_name'):
        await event.reply("❌ No saved data. Clone first.")
        return
    try:
        await client(UpdateProfileRequest(
            first_name=cd.get('orig_first_name', ''),
            last_name=cd.get('orig_last_name', '')
        ))
        if cd.get('orig_bio'):
            await client(functions.account.UpdateProfileRequest(about=cd['orig_bio']))
        else:
            await client(functions.account.UpdateProfileRequest(about=""))
        try:
            me = await client.get_me()
            current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            if current_photos.photos:
                await client(DeletePhotosRequest(id=current_photos.photos))
            orig_paths = cd.get('orig_photo_paths', [])
            orig_paths.sort()
            for photo_path in orig_paths:
                if os.path.exists(photo_path):
                    await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
                    await asyncio.sleep(0.5)
        except Exception as e:
            log.warning(f"Photo restore failed: {e}")
        db['clone_data'] = {}
        save_db()
        await event.reply("✅ **Profile Restored!**")
    except Exception as e:
        await event.reply(f"❌ Restore failed: {str(e)[:100]}")

@cmd('ghost')
async def ghost_cmd(event):
    if not is_owner(event.sender_id):
        return
    if db.get("ghost_on"):
        await event.reply("👻 Ghost mode already active!")
        return
    me = await client.get_me()
    db['ghost_data'] = {
        'first_name': me.first_name or '',
        'last_name': me.last_name or '',
        'bio': '',
    }
    try:
        full_me = await client(functions.users.GetFullUserRequest(id=me.id))
        db['ghost_data']['bio'] = full_me.full_user.about or ''
    except Exception:
        db['ghost_data']['bio'] = ''
    photo_paths = []
    try:
        photo_dir = DATA_DIR / "ghost_photos"
        shutil.rmtree(photo_dir, ignore_errors=True)
        photo_dir.mkdir(parents=True, exist_ok=True)
        all_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        photos_list = list(all_photos.photos)
        photos_list.reverse()
        for i, photo in enumerate(photos_list):
            photo_path = str(photo_dir / f"ghost_photo_{i:03d}.jpg")
            downloaded = await client.download_media(photo, photo_path)
            if downloaded:
                photo_paths.append(photo_path)
    except Exception as e:
        log.warning(f"Could not save photos for ghost: {e}")
    db['ghost_data']['photo_paths'] = photo_paths
    try:
        await client(UpdateProfileRequest(first_name="Deleted", last_name="Account"))
        await client(functions.account.UpdateProfileRequest(about="This account has been deleted"))
        current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        if current_photos.photos:
            await client(DeletePhotosRequest(id=current_photos.photos))
        ghost_img_url = "https://i.ibb.co/MDZVcWjh/IMG-20260921-203641-296.jpg"
        ghost_img_path = str(TEMP_DIR / "ghost_temp.jpg")
        async with aiohttp.ClientSession() as session:
            async with session.get(ghost_img_url) as resp:
                if resp.status == 200:
                    with open(ghost_img_path, "wb") as f:
                        f.write(await resp.read())
        if os.path.exists(ghost_img_path):
            await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(ghost_img_path)))
            try: os.remove(ghost_img_path)
            except: pass
        db['ghost_on'] = True
        save_db()
        await event.reply("👻 Ghost Mode Activated!")
    except Exception as e:
        await event.reply(f"❌ Ghost mode failed: {str(e)[:100]}")

@cmd('unghost')
async def unghost_cmd(event):
    if not is_owner(event.sender_id):
        return
    if not db.get("ghost_on"):
        await event.reply("❌ Ghost mode is not active!")
        return
    gd = db.get("ghost_data", {})
    try:
        me = await client.get_me()
        current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
        if current_photos.photos:
            await client(DeletePhotosRequest(id=current_photos.photos))
        await client(UpdateProfileRequest(
            first_name=gd.get('first_name', ''),
            last_name=gd.get('last_name', '')
        ))
        if gd.get('bio'):
            await client(functions.account.UpdateProfileRequest(about=gd['bio']))
        else:
            await client(functions.account.UpdateProfileRequest(about=""))
        photo_paths = gd.get('photo_paths', [])
        restored_count = 0
        for photo_path in photo_paths:
            if os.path.exists(photo_path):
                try:
                    await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
                    restored_count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    log.warning(f"Failed to restore photo {photo_path}: {e}")
        db['ghost_on'] = False
        db['ghost_data'] = {}
        save_db()
        await event.reply(f"✅ Ghost Mode Deactivated!\n📸 Restored {restored_count} original photos.
