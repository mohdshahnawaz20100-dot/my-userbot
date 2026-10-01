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
        await event.reply(f"✅ Ghost Mode Deactivated!\n📸 Restored {restored_count} original photos.")
    except Exception as e:
        await event.reply(f"❌ Unghost failed: {str(e)[:100]}")

# ═══════════════ ADMIN COMMANDS ═══════════════
@cmd('admins')
async def admins_cmd(event):
    await event.reply(f"👑 Owner: `{db.get('owner_id', OWNER_ID)}`\n**Admins:** {db['admins']}", parse_mode='markdown')

@cmd('addadmin')
async def addadmin_cmd(event):
    if not is_owner(event.sender_id):
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid in db['admins']:
        await event.reply("⏺️ Already admin.")
        return
    db['admins'].append(uid)
    save_db()
    await event.reply("✅ **Admin Added!**")

@cmd('deladmin')
async def deladmin_cmd(event):
    if not is_owner(event.sender_id):
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid in db['admins']:
        db['admins'].remove(uid)
        save_db()
    await event.reply("✅ **Admin Removed!**")

# ═══════════════ MUTE & RESTRICT ═══════════════
@cmd('mute', delete_cmd=False)
async def mute_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    try:
        await client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, send_messages=True)))
        await event.reply("🔇 **User Muted!**")
    except Exception as e:
        await event.reply(f"❌ {str(e)[:100]}")

@cmd('unmute', delete_cmd=False)
async def unmute_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    try:
        await client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, send_messages=False)))
        await event.reply("🔊 **User Unmuted!**")
    except Exception as e:
        await event.reply(f"❌ {str(e)[:100]}")

@cmd('gmute')
async def gmute_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    db['gmuted'][str(uid)] = True
    save_db()
    await event.reply("🌐 **User Globally Muted!**")

@cmd('gunmute')
async def gunmute_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if str(uid) in db['gmuted']:
        del db['gmuted'][str(uid)]
        save_db()
    await event.reply("🌐 **User Globally Unmuted!**")

def get_base_banned_rights():
    return ChatBannedRights(
        until_date=None, send_messages=False, send_media=False,
        send_stickers=True, send_gifs=True, send_games=False,
        send_inline=False, send_polls=False, embed_links=True,
        send_photos=False, send_videos=False, send_audios=False,
        send_voices=False, send_docs=False, pin_messages=True,
        change_info=True, invite_users=False,
    )

@cmd('lock')
async def lock_cmd(event):
    if not event.is_group:
        await event.reply("❌ This is not a group.")
        return
    try:
        base = get_base_banned_rights()
        base.send_messages = True
        base.send_media = True
        base.send_photos = True
        base.send_videos = True
        base.send_audios = True
        base.send_voices = True
        base.send_docs = True
        base.send_polls = True
        base.send_games = True
        base.send_inline = True
        await client(EditChatDefaultBannedRightsRequest(peer=event.chat_id, banned_rights=base))
        await event.reply("🔒 Group Locked!")
    except Exception as e:
        await event.reply(f"❌ Lock failed: {str(e)[:100]}")

@cmd('unlock')
async def unlock_cmd(event):
    if not event.is_group:
        await event.reply("❌ This is not a group.")
        return
    try:
        base = get_base_banned_rights()
        base.send_messages = False
        base.send_media = False
        base.send_photos = False
        base.send_videos = False
        base.send_audios = False
        base.send_voices = False
        base.send_docs = False
        base.send_polls = False
        base.send_games = False
        base.send_inline = False
        await client(EditChatDefaultBannedRightsRequest(peer=event.chat_id, banned_rights=base))
        await event.reply("🔓 Group Unlocked!")
    except Exception as e:
        await event.reply(f"❌ Unlock failed: {str(e)[:100]}")

# ═══════════════ GROUP MOD ═══════════════
@cmd('tagall')
async def tagall_cmd(event):
    if not event.is_group:
        await event.reply("❌ This is not a group.")
        return
    text = get_args(event.message)
    chat_id = event.chat_id
    all_users_list = []
    try:
        async for user in client.iter_participants(chat_id):
            if not user.deleted and not user.bot:
                all_users_list.append(user)
    except Exception as e:
        await event.reply(f"❌ Failed: {str(e)[:100]}")
        return
    if not all_users_list:
        await event.reply("❌ No members found.")
        return
    chunk_size = 50
    for i in range(0, len(all_users_list), chunk_size):
        chunk = all_users_list[i:i + chunk_size]
        mentions = []
        for user in chunk:
            name = user.first_name or "User"
            name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            mentions.append(f'<a href="tg://user?id={user.id}">{name}</a>')
        mention_str = ' '.join(mentions)
        msg = f"{text}\n{mention_str}" if (i == 0 and text) else mention_str
        await event.respond(msg, parse_mode='html')
        await asyncio.sleep(1.5)

@cmd('tagall2')
async def tagall2_cmd(event):
    if not event.is_group:
        await event.reply("❌ This is not a group.")
        return
    text = get_args(event.message)
    if not text:
        await event.reply("❌ Usage: `.tagall2 <text>`")
        return
    chat_id = event.chat_id
    all_users_list = []
    try:
        async for user in client.iter_participants(chat_id):
            if not user.deleted and not user.bot:
                all_users_list.append(user)
    except Exception as e:
        await event.reply(f"❌ Failed: {str(e)[:100]}")
        return
    count = 0
    for user in all_users_list:
        try:
            name = user.first_name or "User"
            name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            msg = f'<a href="tg://user?id={user.id}">{name}</a> {text}'
            await event.respond(msg, parse_mode='html')
            count += 1
            await asyncio.sleep(1.2)
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds + 2)
        except Exception:
            continue
    await event.respond(f"✅ Done! {count} members tagged.")

@cmd('raid')
async def raid_cmd(event):
    if not event.is_reply:
        await event.reply("❌ Reply to a user.")
        return
    count_str = get_args(event.message)
    try:
        count = int(count_str) if count_str else 10
    except Exception:
        count = 10
    count = min(count, 50)
    reply = await event.get_reply_message()
    for i in range(count):
        try:
            msg_template = random.choice(RAID_MESSAGES).replace('{n}', str(i + 1))
            await reply.reply(msg_template)
            await asyncio.sleep(0.3)
        except Exception:
            break

@cmd('purge', delete_cmd=True)
async def purge_cmd(event):
    if not event.is_reply:
        await event.reply("❌ Reply to a message.")
        return
    reply_msg = await event.get_reply_message()
    if not reply_msg:
        await event.reply("❌ Could not fetch.")
        return
    chat_id = event.chat_id
    start_id = reply_msg.id
    all_ids = []
    last_id = start_id
    while True:
        try:
            msgs = await client.get_messages(chat_id, min_id=last_id, limit=100, reverse=False)
            if not msgs:
                break
            ids = [m.id for m in msgs]
            all_ids.extend(ids)
            last_id = min(ids) if ids else start_id
            if len(msgs) < 100:
                break
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)[:100]}")
            return
    if not all_ids:
        await event.reply("✅ No messages to delete.")
        return
    total_deleted = 0
    chunk_size = 100
    for i in range(0, len(all_ids), chunk_size):
        chunk = all_ids[i:i + chunk_size]
        try:
            await client.delete_messages(chat_id, chunk)
            total_deleted += len(chunk)
            await asyncio.sleep(0.5)
        except Exception as e:
            await event.reply(f"❌ Delete failed: {str(e)[:100]}")
            return
    await event.reply(f"✅ Purged **{total_deleted}** messages.")

@cmd('throw')
async def throw_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    try:
        await client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, view_messages=True)))
        await asyncio.sleep(0.5)
        await client(EditBannedRequest(event.chat_id, uid, ChatBannedRights(until_date=None, view_messages=False)))
        await event.reply("👢 **User Kicked!**")
    except Exception as e:
        await event.reply(f"❌ {str(e)[:100]}")

@cmd('stop')
async def stop_cmd(event):
    db['reply_raid'].clear()
    db['rr_raid'].clear()
    db['flag_raid'].clear()
    db['heart_raid'].clear()
    db['spam_running'] = False
    db['fast_gc_data'].clear()
    save_db()
    await event.reply("🛑 **All loops stopped!**")

# ═══════════════ FAST GC ═══════════════
async def fast_gc_loop(chat_id):
    while True:
        data = db['fast_gc_data'].get(str(chat_id))
        if not data or not data.get('enabled', False):
            break
        template = data.get('template', 'FastGC')
        counter = data.get('counter', 0) + 1
        new_title = f"{template} [{counter}]"
        try:
            entity = await client.get_entity(chat_id)
            if hasattr(entity, 'broadcast') and entity.broadcast:
                await client(EditTitleRequest(channel=entity, title=new_title))
            else:
                await client(EditChatTitleRequest(chat_id=chat_id, title=new_title))
            data['counter'] = counter
            save_db()
        except Exception as e:
            log.warning(f"FastGC error: {e}")
            db['fast_gc_data'][str(chat_id)]['enabled'] = False
            save_db()
            break
        await asyncio.sleep(1.5)

@cmd('fastgc')
async def fastgc_cmd(event):
    args = get_args(event.message).split()
    if not args:
        await event.reply("Usage: `.fastgc set <text>` | `.fastgc stop`")
        return
    chat_id = str(event.chat_id)
    action = args[0].lower()
    if action == 'set' and len(args) > 1:
        template = ' '.join(args[1:])
        db['fast_gc_data'][chat_id] = {'enabled': True, 'template': template, 'counter': 0}
        save_db()
        asyncio.create_task(fast_gc_loop(event.chat_id))
        await event.reply(f"⚡ **Fast GC started!**")
    elif action == 'stop':
        if chat_id in db['fast_gc_data']:
            db['fast_gc_data'][chat_id]['enabled'] = False
            save_db()
            await event.reply("🛑 **Fast GC stopped!**")
        else:
            await event.reply("❌ No fast GC running.")
    else:
        await event.reply("Usage: `.fastgc set <text>` | `.fastgc stop`")

# ═══════════════ AUTO SYSTEM ═══════════════
@cmd('autoreact')
async def autoreact_cmd(event):
    arg = get_args(event.message).lower()
    if arg == 'on':
        db['auto_react_dm_enabled'] = True
        save_db()
        await event.reply("✅ **DM Auto‑React ON**")
    elif arg == 'off':
        db['auto_react_dm_enabled'] = False
        save_db()
        await event.reply("✅ **DM Auto‑React OFF**")
    else:
        await event.reply("Usage: `.autoreact on/off`")

@cmd('autoreactg')
async def autoreactg_cmd(event):
    arg = get_args(event.message).lower()
    if arg == 'on':
        db['auto_react_group_enabled'] = True
        save_db()
        await event.reply("✅ **Group Auto‑React ON**")
    elif arg == 'off':
        db['auto_react_group_enabled'] = False
        save_db()
        await event.reply("✅ **Group Auto‑React OFF**")
    else:
        await event.reply("Usage: `.autoreactg on/off`")

@cmd('autoreply')
async def autoreply_cmd(event):
    text = get_args(event.message)
    parts = text.split(' ', 1)
    DEFAULT_REPLY = "The owner is busy with some personal work at the moment😌Please wait until they are back online🥀"
    if not parts or not parts[0]:
        await event.reply("**Usage:**\n`.autoreply on`\n`.autoreply off`\n`.autoreply set <text>`\n`.autoreply reset`", parse_mode='markdown')
        return
    action = parts[0].lower()
    if action == 'on':
        db['auto_reply']['enabled'] = True
        db['auto_reply']['mode'] = 'always'
        db['auto_reply']['text'] = DEFAULT_REPLY
        db['auto_reply']['replied_users'] = []
        save_db()
        await event.reply("✅ Auto Reply ON (Always Mode)")
    elif action == 'off':
        db['auto_reply']['enabled'] = False
        db['auto_reply']['replied_users'] = []
        save_db()
        await event.reply("✅ Auto Reply OFF")
    elif action == 'set' and len(parts) > 1:
        db['auto_reply']['text'] = parts[1]
        db['auto_reply']['enabled'] = True
        db['auto_reply']['mode'] = 'once'
        db['auto_reply']['replied_users'] = []
        save_db()
        await event.reply("✅ Custom Auto Reply Set (Once Mode)")
    elif action == 'reset':
        db['auto_reply']['replied_users'] = []
        save_db()
        await event.reply("✅ Replied list reset!")

@cmd('pmguard')
async def pmguard_cmd(event):
    arg = get_args(event.message).lower()
    if arg == 'on':
        db['pmguard']['enabled'] = True
        save_db()
        await event.reply("🛡️ **PM Guard ON**")
    elif arg == 'off':
        db['pmguard']['enabled'] = False
        save_db()
        await event.reply("🛡️ **PM Guard OFF**")
    else:
        await event.reply("Usage: `.pmguard on/off`")

@cmd('approve')
async def approve_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid in db['approved']:
        await event.reply("✅ Already approved.")
        return
    db['approved'].append(uid)
    db['pm_warnings'].pop(str(uid), None)
    try:
        await client(UnblockRequest(id=uid))
    except Exception:
        pass
    save_db()
    await event.reply("✅ **User Approved!**")

@cmd('disapprove')
async def disapprove_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid in db['approved']:
        db['approved'].remove(uid)
        save_db()
    await event.reply("✅ **User Disapproved!**")

@cmd('blacklist')
async def blacklist_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid not in db['blacklist']:
        db['blacklist'].append(uid)
        save_db()
    await event.reply("🚫 **User Blacklisted!**")

@cmd('removeblacklist')
async def removeblacklist_cmd(event):
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    if uid in db['blacklist']:
        db['blacklist'].remove(uid)
        save_db()
    await event.reply("✅ **User Removed from Blacklist!**")

# ═══════════════ PM GUARD HANDLER ═══════════════
@client.on(events.NewMessage(func=lambda e: e.is_private and not e.out))
async def pm_guard_handler(event):
    uid = event.sender_id
    if uid == db.get('owner_id', OWNER_ID):
        return
    if not db['pmguard'].get('enabled', False):
        return
    if uid in db['approved']:
        return
    if uid in db['blacklist']:
        await client(BlockRequest(id=uid))
        return
    w = db['pm_warnings'].get(str(uid), 0) + 1
    db['pm_warnings'][str(uid)] = w
    save_db()
    if w < 5:
        await event.reply(f"**🔒 SECURITY ALERT**\n\nOwner is busy. Warning: {w}/5")
    else:
        await event.reply("🚫 **You have been blocked!**")
        try:
            await client(BlockRequest(id=uid))
            if uid not in db['blocklist']:
                db['blocklist'].append(uid)
                save_db()
        except Exception:
            pass

# ═══════════════ GLOBAL MUTE FILTER ═══════════════
@client.on(events.NewMessage)
async def gmute_filter(event):
    if event.out:
        return
    uid = event.sender_id
    if str(uid) in db['gmuted']:
        try:
            await event.delete()
            if event.is_private:
                await client(BlockRequest(id=uid))
        except Exception:
            pass

# ═══════════════ AUTO-REACT HANDLER ═══════════════
@client.on(events.NewMessage)
async def auto_react_handler(event):
    if event.out:
        return
    if event.is_private:
        if db['auto_react_dm_enabled']:
            emoji = random.choice(db['auto_react_emojis'])
            try:
                await client(SendReactionRequest(
                    peer=event.chat_id,
                    msg_id=event.message.id,
                    reaction=[ReactionEmoji(emoticon=emoji)]
                ))
            except Exception:
                pass
    else:
        if db['auto_react_group_enabled']:
            emoji = random.choice(db['auto_react_emojis'])
            try:
                await client(SendReactionRequest(
                    peer=event.chat_id,
                    msg_id=event.message.id,
                    reaction=[ReactionEmoji(emoticon=emoji)]
                ))
            except Exception:
                pass

# ═══════════════ AUTO REPLY HANDLER ═══════════════
@client.on(events.NewMessage(func=lambda e: e.is_private and not e.out))
async def auto_reply_handler(event):
    uid = event.sender_id
    if uid == db.get('owner_id', OWNER_ID):
        return
    if not db['auto_reply'].get('enabled', False):
        return
    mode = db['auto_reply'].get('mode', 'always')
    text = db['auto_reply'].get('text', 'Busy...')
    if mode == 'always':
        await asyncio.sleep(0.5)
        try:
            await event.reply(text)
        except Exception:
            pass
        return
    if mode == 'once':
        replied = db['auto_reply'].get('replied_users', [])
        if uid in replied:
            return
        await asyncio.sleep(0.5)
        try:
            await event.reply(text)
            replied.append(uid)
            db['auto_reply']['replied_users'] = replied
            save_db()
        except Exception:
            pass

# ═══════════════ RAID ENGINE ═══════════════
@cmd('reply')
async def reply_raid_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    async def send_reply():
        msg = random.choice(REPLY_MESSAGES)
        await event.reply(f"@{uid} {msg}")
    asyncio.create_task(raid_loop(event, uid, db['reply_raid'], send_reply, 1.5))
    await event.reply(f"⚔️ **Reply raid started!**")

@cmd('sreply')
async def sreply_raid_cmd(event):
    chat_id = event.chat_id
    if chat_id in db['reply_raid']:
        db['reply_raid'][chat_id].clear()
        await event.reply("🛑 **Reply raid stopped!**")

@cmd('rr')
async def rr_raid_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    async def send_rr():
        await event.reply(f"🤣 {user_link(uid)}", parse_mode='markdown')
    asyncio.create_task(raid_loop(event, uid, db['rr_raid'], send_rr, 1))
    await event.reply(f"🤣 **RR raid started!**")

@cmd('srr')
async def srr_raid_cmd(event):
    chat_id = event.chat_id
    if chat_id in db['rr_raid']:
        db['rr_raid'][chat_id].clear()
        await event.reply("🛑 **RR raid stopped!**")

@cmd('flag')
async def flag_raid_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    flags = ['🇮🇳', '🇺🇸', '🇬🇧', '🇩🇪', '🇫🇷', '🇯🇵', '🇨🇳', '🇷🇺', '🇧🇷', '🇦🇪']
    async def send_flag():
        await event.reply(f"{random.choice(flags)} {user_link(uid)}", parse_mode='markdown')
    asyncio.create_task(raid_loop(event, uid, db['flag_raid'], send_flag, 1.2))
    await event.reply(f"🚩 **Flag raid started!**")

@cmd('sflag')
async def sflag_raid_cmd(event):
    chat_id = event.chat_id
    if chat_id in db['flag_raid']:
        db['flag_raid'][chat_id].clear()
        await event.reply("🛑 **Flag raid stopped!**")

@cmd('hrr')
async def heart_raid_cmd(event):
    if not event.is_group:
        return
    uid = await resolve_user(client, event.message, get_args(event.message))
    if not uid:
        await event.reply("❌ User not found.")
        return
    hearts = ['❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💗']
    async def send_heart():
        await event.reply(f"{random.choice(hearts)} {user_link(uid)}", parse_mode='markdown')
    asyncio.create_task(raid_loop(event, uid, db['heart_raid'], send_heart, 1))
    await event.reply(f"💖 **Heart raid started!**")

@cmd('shrr')
async def sheart_raid_cmd(event):
    chat_id = event.chat_id
    if chat_id in db['heart_raid']:
        db['heart_raid'][chat_id].clear()
        await event.reply("🛑 **Heart raid stopped!**")

# ═══════════════ SPAM ═══════════════
@cmd('spray')
async def spray_cmd(event):
    text = get_args(event.message)
    db['spam_running'] = True
    if not text:
        async def spam_loop():
            count = 0
            while db['spam_running'] and count < 100:
                try:
                    msg = random.choice(DEFAULT_SPAM_TEXTS)
                    emoji = random.choice(SPAM_EMOJIS)
                    await event.reply(f"{msg} {emoji}")
                    count += 1
                    await asyncio.sleep(0.8)
                except Exception:
                    break
            db['spam_running'] = False
        asyncio.create_task(spam_loop())
        await event.reply("💣 **Spam started!**")
    else:
        async def spam_loop():
            count = 0
            while db['spam_running'] and count < 100:
                try:
                    emoji = random.choice(SPAM_EMOJIS)
                    await event.reply(f"{text} {emoji}")
                    count += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    break
            db['spam_running'] = False
        asyncio.create_task(spam_loop())
        await event.reply(f"💣 **Spam started!**")

@cmd('dspray')
async def dspray_cmd(event):
    db['spam_running'] = False
    await event.reply("🛑 **Spam stopped!**")

# ═══════════════ FUN ═══════════════
@cmd('ping', delete_cmd=False)
async def ping_cmd(event):
    start = time.time()
    msg = await event.reply("🏓 Pong!")
    await msg.edit(f"🏓 **Pong!** `{round((time.time() - start) * 1000, 2)}ms`", parse_mode='markdown')

@cmd('flip', delete_cmd=False)
async def flip_cmd(event):
    await event.reply(f"{random.choice(['**Heads** 🪙', '**Tails** 🪙'])}", parse_mode='markdown')

@cmd('dice', delete_cmd=False)
async def dice_cmd(event):
    await event.reply(f"🎲 **Dice:** `{random.randint(1, 6)}`", parse_mode='markdown')

# ═══════════════ STALK TOOLS ═══════════════
@cmd('stalk', delete_cmd=False)
async def stalk_cmd(event):
    reply = await event.get_reply_message()
    if not reply:
        await event.reply("❌ Reply to a user's message!")
        return
    try:
        user = await reply.get_sender()
        full = await client(functions.users.GetFullUserRequest(user.id))
        fu = full.full_user
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
        username = f"@{user.username}" if user.username else "Hidden"
        bio = fu.about or "No bio"
        photos = await client.get_profile_photos(user)
        status = "Unknown"
        if hasattr(user, 'status') and user.status:
            sn = type(user.status).__name__
            if 'Online' in sn:
                status = "🟢 Online NOW"
            elif 'Recently' in sn:
                status = "🟡 Recently"
            elif 'LastWeek' in sn:
                status = "🟠 Last week"
            elif 'LastMonth' in sn:
                status = "🔴 Last month"
            else:
                status = "⚫ Long time ago"
        premium = "⭐ Yes" if getattr(user, 'premium', False) else "No"
        verified = "✅ Yes" if getattr(user, 'verified', False) else "No"
        scam = "⚠️ YES!" if getattr(user, 'scam', False) else "No"
        fake = "⚠️ YES!" if getattr(user, 'fake', False) else "No"
        await event.reply(
            f"🕵️ **Deep Stalk**\n\n"
            f"👤 **Name:** {name}\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"📛 **Username:** {username}\n"
            f"📝 **Bio:** {bio}\n"
            f"📊 **Status:** {status}\n"
            f"📸 **Profile Pics:** {len(photos)}\n"
            f"⭐ **Premium:** {premium}\n"
            f"✅ **Verified:** {verified}\n"
            f"🚫 **Scam:** {scam}\n"
            f"🎭 **Fake:** {fake}\n"
            f"💬 **Common Chats:** {fu.common_chats_count}\n\n"
            f"🔗 [Profile Link](tg://user?id={user.id})",
            parse_mode='markdown'
        )
    except Exception as e:
        await event.reply(f"❌ Error: `{str(e)[:150]}`")

@cmd('allpfp', delete_cmd=False)
async def allpfp_cmd(event):
    reply = await event.get_reply_message()
    if reply:
        user = await reply.get_sender()
    else:
        user = await event.get_sender()
    try:
        photos = await client.get_profile_photos(user)
        if not photos:
            await event.reply("❌ No profile pictures found!")
            return
        msg = await event.reply(f"📸 Downloading {len(photos)} pics...")
        for i, photo in enumerate(photos[:10]):
            await client.send_file(
                event.chat_id, photo,
                caption=f"📸 **{user.first_name or 'User'}'s PFP** ({i + 1}/{min(len(photos), 10)})"
            )
        await msg.edit(f"✅ Sent {min(len(photos), 10)} profile pictures!")
    except Exception as e:
        await event.reply(f"❌ Error: `{str(e)[:150]}`")

@cmd('lastmsg', delete_cmd=False)
async def lastmsg_cmd(event):
    reply = await event.get_reply_message()
    if not reply:
        await event.reply("❌ Reply to a user's message!")
        return
    args = get_args(event.message)
    try:
        count = min(int(args) if args else 5, 20)
    except Exception:
        count = 5
    try:
        user = await reply.get_sender()
        chat = await event.get_chat()
        msgs = []
        async for m in client.iter_messages(chat, from_user=user, limit=count):
            text = m.text or "[Media]"
            msgs.append(f"• `{text[:60]}{'...' if len(text) > 60 else ''}`")
        if not msgs:
            await event.reply(f"❌ No messages from {user.first_name or 'user'}!")
            return
        await event.reply(
            f"🕵️ **Last {len(msgs)} messages from {user.first_name or 'user'}**\n\n"
            + "\n".join(msgs)
        )
    except Exception as e:
        await event.reply(f"❌ Error: `{str(e)[:150]}`")

# ═══════════════ MUSIC ═══════════════
async def deezer_search(query, limit=1):
    try:
        url = f"https://api.deezer.com/search?q={url_quote(query)}&limit={limit}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None

@cmd('lyrics', delete_cmd=False)
async def lyrics_cmd(event):
    query = get_args(event.message)
    if not query:
        await event.reply("❌ Usage: `.lyrics <song>`")
        return
    msg = await event.reply("🎵 Searching lyrics...")
    try:
        parts = query.split(maxsplit=1)
        data = None
        if len(parts) == 2:
            url = f"https://api.lyrics.ovh/v1/{url_quote(parts[0])}/{url_quote(parts[1])}"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
        if data and data.get("lyrics"):
            await msg.edit(f"🎶 **Lyrics for:** `{query}`\n\n{data['lyrics'][:3990]}")
            return
        deezer = await deezer_search(query)
        if deezer and deezer.get("data"):
            track = deezer["data"][0]
            artist = track["artist"]["name"]
            title = track["title"]
            url = f"https://api.lyrics.ovh/v1/{url_quote(artist)}/{url_quote(title)}"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        d2 = await resp.json()
                        if d2.get("lyrics"):
                            await msg.edit(f"🎶 **{title}** - {artist}\n\n{d2['lyrics'][:3990]}")
                            return
        await msg.edit("❌ Lyrics not found.")
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

@cmd('songinfo', delete_cmd=False)
async def songinfo_cmd(event):
    query = get_args(event.message)
    if not query:
        await event.reply("❌ Usage: `.songinfo <song>`")
        return
    msg = await event.reply("🎵 Fetching details...")
    try:
        search = await deezer_search(query, 1)
        if not search or not search.get("data"):
            await msg.edit("❌ Song not found.")
            return
        track_id = search["data"][0]["id"]
        url = f"https://api.deezer.com/track/{track_id}"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as resp:
                track = await resp.json()
        dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
        explicit = "🔞 Yes" if track.get("explicit_lyrics") else "✅ No"
        await msg.edit(
            f"🎵 **Detailed Song Info**\n\n"
            f"🎤 **Title:** `{track.get('title', 'N/A')}`\n"
            f"👤 **Artist:** `{track['artist']['name']}`\n"
            f"💿 **Album:** `{track['album']['title']}`\n"
            f"📅 **Released:** `{track.get('release_date', 'N/A')}`\n"
            f"⏱ **Duration:** `{dur}`\n"
            f"🎛 **BPM:** `{track.get('bpm', 'N/A')}`\n"
            f"🔞 **Explicit:** {explicit}\n"
            f"🔗 [Listen]({track.get('link', '')})",
            parse_mode='markdown'
        )
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

@cmd('spotify', delete_cmd=False)
async def spotify_cmd(event):
    query = get_args(event.message)
    if not query:
        await event.reply("❌ Usage: `.spotify <query>`")
        return
    msg = await event.reply("🎵 Searching...")
    try:
        data = await deezer_search(query, 5)
        if not data or not data.get("data"):
            await msg.edit("❌ No results found.")
            return
        text = f"🎵 **Search results:** `{query}`\n\n"
        for i, track in enumerate(data["data"], 1):
            dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
            preview = f"[▶️]({track['preview']})" if track.get("preview") else ""
            text += (
                f"**{i}.** `{track['title']}` – {track['artist']['name']}\n"
                f"   ⏱ {dur} {preview} 🔗 [Listen]({track['link']})\n\n"
            )
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

@cmd('trending', delete_cmd=False)
async def trending_cmd(event):
    msg = await event.reply("📊 Loading trending...")
    try:
        url = "https://api.deezer.com/chart/0/tracks?limit=10"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url) as resp:
                data = await resp.json()
        if not data or not data.get("data"):
            await msg.edit("❌ Failed to load charts.")
            return
        text = "🔥 **Global Trending Songs**\n\n"
        for i, track in enumerate(data["data"], 1):
            dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"**{i}.**"
            text += f"{medal} `{track['title']}` – {track['artist']['name']} (⏱ {dur})\n"
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

@cmd('ringtone', delete_cmd=False)
async def ringtone_cmd(event):
    query = get_args(event.message)
    if not query:
        await event.reply("❌ Usage: `.ringtone <song>`")
        return
    msg = await event.reply("🔔 Searching ringtones...")
    try:
        data = await deezer_search(query, 5)
        if not data or not data.get("data"):
            await msg.edit("❌ No ringtones found.")
            return
        text = f"🔔 **Ringtone Search:** `{query}`\n\n"
        found = False
        for i, track in enumerate(data["data"], 1):
            if track.get("preview"):
                found = True
                text += f"**{i}.** `{track['title']}` – {track['artist']['name']}\n   📥 [Download 30s]({track['preview']})\n\n"
        if not found:
            await msg.edit("❌ No previews available.")
            return
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

@cmd('playlist', delete_cmd=False)
async def playlist_cmd(event):
    mood = get_args(event.message).lower()
    if not mood:
        await event.reply("❌ Usage: `.playlist <mood>`\nMoods: happy, sad, chill, party, romantic, workout, focus")
        return
    MOOD_GENRES = {
        "happy": "132", "sad": "165", "chill": "106", "party": "113",
        "romantic": "98", "workout": "129", "focus": "466",
    }
    msg = await event.reply(f"🎶 Generating `{mood}` playlist...")
    try:
        genre_id = MOOD_GENRES.get(mood, "132")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(f"https://api.deezer.com/genre/{genre_id}/artists") as resp:
                artists = await resp.json()
        if not artists or not artists.get("data"):
            await msg.edit("❌ Mood not found.")
            return

        async def fetch_top(aid):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
                    async with s.get(f"https://api.deezer.com/artist/{aid}/top?limit=2") as r:
                        return await r.json()
            except Exception:
                return None

        results = await asyncio.gather(*[fetch_top(a["id"]) for a in artists["data"][:5]])
        tracks = []
        for top in results:
            if top and top.get("data"):
                tracks.extend(top["data"])
        if not tracks:
            await msg.edit("❌ No tracks found.")
            return
        emoji = {"happy": "😄", "sad": "😢", "chill": "😌", "party": "🎉", "romantic": "💕", "workout": "💪", "focus": "🧠"}.get(mood, "🎵")
        text = f"{emoji} **{mood.title()} Playlist**\n\n"
        for i, t in enumerate(tracks[:10], 1):
            dur = f"{t['duration'] // 60}:{t['duration'] % 60:02d}"
            text += f"**{i}.** `{t['title']}` – {t['artist']['name']} ({dur})\n"
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:150]}`")

# ═══════════════ TEXT-TO-IMAGE ═══════════════
@cmd('t2i', delete_cmd=False)
async def t2i_cmd(event):
    prompt = get_args(event.message)
    if not prompt:
        await event.reply("❌ Usage: `.t2i <prompt>`")
        return
    status = await event.reply(f"🎨 Generating...\n`{prompt[:80]}`")
    try:
        encoded = url_quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?nologo=true&enhance=true&width=1024&height=1024"
            f"&model=flux&seed={random.randint(1, 999999)}"
        )
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await status.edit(f"❌ Image API error: {resp.status}")
                    return
                img_data = await resp.read()
        img_path = TEMP_DIR / f"t2i_{int(time.time())}.jpg"
        img_path.write_bytes(img_data)
        try:
            await status.delete()
        except Exception:
            pass
        await client.send_file(event.chat_id, str(img_path), reply_to=event.message.id)
        try:
            os.remove(img_path)
        except Exception:
            pass
    except asyncio.TimeoutError:
        await status.edit("❌ **Timeout** – Try again.")
    except Exception as e:
        await status.edit(f"❌ **Error:** `{str(e)[:150]}`")

# ═══════════════ ANIMATIONS ═══════════════
@cmd('animate', delete_cmd=True)
async def animate_cmd(event):
    text = get_args(event.message)
    if not text:
        await event.reply("❌ Usage: `.animate <text>`")
        return
    frames = ["🤍", "🦋", "🌸", "💖", "💝", "🎼", "😇", "✨"]
    msg = await event.reply("🤍")
    try:
        for i in range(1, len(text) + 1):
            await msg.edit(text[:i] + " " + random.choice(frames))
            await asyncio.sleep(0.35)
        for _ in range(5):
            await msg.edit(f"🤍 {text} 🌸")
            await asyncio.sleep(0.6)
            await msg.edit(f"💖 {text} 💝")
            await asyncio.sleep(0.6)
            await msg.edit(f"🦋 {text} 🎼")
            await asyncio.sleep(0.6)
        await msg.edit(f"💖 **{text}** 💖")
    except Exception:
        pass

@cmd('spinner', delete_cmd=True)
async def spinner_cmd(event):
    args = get_args(event.message)
    try:
        secs = int(args) if args else 8
    except Exception:
        secs = 8
    secs = min(max(secs, 3), 30)
    stages = [("🤍", "Starting up"), ("🦋", "Loading data"), ("🌸", "Processing"),
              ("💖", "Almost done"), ("💝", "Finalizing")]
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    msg = await event.reply("⠋ Starting...")
    try:
        total = secs * 4
        for i in range(total):
            stage_idx = min(int((i / total) * len(stages)), len(stages) - 1)
            emoji, label = stages[stage_idx]
            bar_len = 12
            filled = int((i / total) * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            await msg.edit(
                f"{emoji} **{label}...**\n\n"
                f"`{bar}` {int((i / total) * 100)}%\n"
                f"{frames[i % len(frames)]}"
            )
            await asyncio.sleep(0.35)
        await msg.edit("💝 **Complete!** 🎼")
        await asyncio.sleep(1.5)
    except Exception:
        pass

@cmd('loveu', delete_cmd=False)
async def loveu_cmd(event):
    final_box = (
        "╭═════════💜═╮\n"
        "  🇮 🇱‌🇴‌🇻‌🇪 🇾‌🇴‌🇺\n"
        "╰═💜═════════╯"
    )
    await event.reply(final_box)

@cmd('matrix', delete_cmd=True)
async def matrix_cmd(event):
    args = get_args(event.message)
    try:
        secs = int(args) if args else 8
    except Exception:
        secs = 8
    secs = min(max(secs, 3), 20)
    chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
    msg = await event.reply("`01001000`")
    try:
        total = secs * 2
        for i in range(total):
            line = "".join(random.choice(chars) for _ in range(14))
            await msg.edit(f"🟢 `{line}`" if i % 4 == 0 else f"`{line}`")
            await asyncio.sleep(0.5)
        for _ in range(2):
            await msg.edit("`Wake up, Neo...`")
            await asyncio.sleep(0.9)
            await msg.edit("`Follow the white rabbit 🐇`")
            await asyncio.sleep(0.9)
        await msg.edit("🟢 **Welcome to the Matrix** 🟢")
    except Exception:
        pass

@cmd('hearts', delete_cmd=True)
async def hearts_cmd(event):
    text = get_args(event.message) or "CipherElite"
    hearts = ["💖", "💗", "💓", "💞", "💕", "❤️", "🧡", "💛", "💚", "💙", "💜"]
    msg = await event.reply(f"💖 {text} 💖")
    try:
        for _ in range(15):
            h1, h2 = random.choice(hearts), random.choice(hearts)
            await msg.edit(f"{h1} {text} {h2}")
            await asyncio.sleep(0.4)
        positions = ["💕", "  💕", "    💕", "      💕", "    💕", "  💕"]
        for i in range(12):
            pos = positions[i % len(positions)]
            await msg.edit(f"{pos}\n  {text}\n{pos}")
            await asyncio.sleep(0.3)
        await msg.edit(f"💖💗💓 **{text}** 💓💗💖")
    except Exception:
        pass

@cmd('countdown', delete_cmd=True)
async def countdown_cmd(event):
    args = get_args(event.message)
    try:
        n = int(args) if args else 5
    except Exception:
        n = 5
    n = min(max(n, 1), 30)
    msg = await event.reply(f"⏱️ Starting countdown from {n}...")
    try:
        for i in range(n, 0, -1):
            await msg.edit(f"⏱️ **{i}**")
            await asyncio.sleep(1.2)
        await msg.edit("🎉 **GO!** 🎉")
    except Exception:
        pass

@cmd('wave', delete_cmd=True)
async def wave_cmd(event):
    text = get_args(event.message)
    if not text:
        await event.reply("❌ Usage: `.wave <text>`")
        return
    msg = await event.reply(text)
    try:
        for i in range(len(text)):
            shifted = "  " * i + text[:len(text) - i]
            await msg.edit(f"`{shifted}`")
            await asyncio.sleep(0.25)
        for i in range(len(text), -1, -1):
            shifted = "  " * i + text[:len(text) - i]
            await msg.edit(f"`{shifted}`")
            await asyncio.sleep(0.25)
        waves = ["🌊", "〰️", "🌸", "🦋", "🤍", "💖"]
        for i in range(8):
            w = waves[i % len(waves)]
            await msg.edit(f"{w} {text} {w}")
            await asyncio.sleep(0.7)
        await msg.edit(f"🌊 **{text}** 🌊\n\n_💖 Beautiful 💖_")
    except Exception:
        pass

# ═══════════════ FANCY TEXT ═══════════════
FANCY_WORDS = ["hi", "hey", "bye", "welcome", "ok", "yes", "wow", "cool", "omg", "lol",
               "love", "hate", "sad", "good", "bad", "best", "go", "fire", "boss"]

def _make_banner(word, font="big"):
    try:
        import pyfiglet
        banner = pyfiglet.figlet_format(word.upper(), font=font)
        if len(banner) > 3500:
            banner = banner[:3500] + "..."
        return f"🦋✨\n`{banner}`\n✨🦋"
    except Exception as e:
        return f"❌ Error: `{str(e)[:100]}`"

for _word in FANCY_WORDS:
    @cmd(_word, delete_cmd=True)
    async def fancy_handler(event, w=_word):
        await reply_to_target(event, _make_banner(w))

@cmd('text', delete_cmd=True)
async def text_cmd(event):
    text = get_args(event.message)
    if not text:
        await event.reply("❌ Usage: `.text <word>`")
        return
    await reply_to_target(event, _make_banner(text))

@cmd('banner', delete_cmd=True)
async def banner_cmd(event):
    args = get_args(event.message).split()
    if not args:
        await event.reply("❌ Usage: `.banner <word> [font]`")
        return
    text = args[0]
    font = args[1].lower() if len(args) > 1 else "big"
    fonts_available = ["big", "banner", "block", "doom", "slant", "standard", "digital"]
    if font not in fonts_available:
        font = "big"
    await reply_to_target(event, _make_banner(text, font))

# ═══════════════ TEXT ART ═══════════════
ART_TEXTS = {
    "gm": """⁣....♥).....♥)..
....(♥.....(♥..
....♥).....♥)..
_C█ __ █C
Good Morning

▬▬▬▬▬▬▬►🍀
🌸◄▬▬▬▬▬▬""",
    "gn": """∩――――∩
|| ∧ ﾍ        ||
||(* ´ ｰ`) Good Night💤
|ﾉ^⌒⌒づ`￣＼Sweet Dreams🦋
(    ノ        ⌒ ヽ ＼Take care💖
＼        ||￣￣￣￣￣||
     ＼,ﾉ||￣￣￣￣￣||""",
    "hbd": """✧✧🔥🔥🔥🔥🔥✧✧
✧╭┻┻┻┻┻┻┻┻┻┻╮✧
✧┃╱╲ 🍓╱╲🍒 ╱╲┃✧
╭┻━🍒━━━🍍━━━┻╮
┃╱╲╱╲ 🍈╱╲🍇 ╱╲ ┃
🎁━━━━━━━━━━━━🎁
✨💕Happy Birthday💕✨""",
    "wlc": """🌟。♥。✨。🍀
。🎁 。🎉。🌟
✨。＼｜／。🌺
WELCOME🌸🌸
💜。／｜＼。💎
。☀。 🌹。🌙。
🌟。 🦋。 🎶""",
    "hello2": """　　　/)＿/)☆ Hello~
    ／(๑^᎑^๑)っ ＼
／|￣∪￣ ￣ |＼／
  |＿＿_＿＿|／""",
    "love2": """　∧__∧
（｀•ω• )づ__∧
（つ     /( •ω•。)
  しーＪ   (nnノ)𝙄𝙩'𝙨 𝙤𝙠""",
    "heyy": """　▬▬.◙.▬▬
▂▄▄▓▄▄▂
◢◤ █▀▀████▄▄▄▄▄◢◤
█Heyy Listen   👀  █▀▀▀▀╬
◥████████◤
══╩══╩══
I will send a helicopter to pick you up!""",
    "gg": """🎩
😁
👕👍Great!
👖""",
    "flower": """　🌷🌸🌷🌸
    🌸🌷🌸🌷🌸
 Λ🌷🌸🌷🌸🌷
( ˘ ᵕ ˘🌷🌸🌷
ヽ  つ＼     ／
   UU   / 🎀 \\""",
    "gum": """૮₍ ˃ ⤙ ˂ ₎ა
./づᡕᠵ᠊ᡃ່࡚ࠢ࠘ ⸝່ࠡࠣ᠊߯᠆ࠣ࠘ᡁࠣ࠘᠊᠊ࠢ࠘~~~~♡""",
    "howdy": """█░█░█ █▀█ █░█░█
▀▄▀▄▀ █▄█ ▀▄▀▄▀""",
    "cool2": """█▀ █▀█ █▀█ █░
█▄ █▄█ █▄█ █▄""",
    "hug": """ଘ😇ଓ""",
    "hug2": """˚∧＿∧  　+        —̳͟͞͞💗
(  •‿• )つ  —̳͟͞͞ 💗         —̳͟͞͞💗 +
(つ　 <                —̳͟͞͞💗
｜　 _つ      +  —̳͟͞͞💗         —̳͟͞͞💗 ˚
`し´""",
    "thnx": """✨╭━━┳╮╭┳━━┳━┳┳┳┳━━╮💖
✨╰╮╭┫╰╯┃╭╮┃┃┃┃╭┫━━┫💖
✨╱┃┃┃╭╮┃┣┫┃┃┃┃╰╋━━┃💖
✨╱╰╯╰╯╰┻╯╰┻┻━┻┻┻━━╯💖""",
    "purpose": """　　👩
👨🌹ノl>
  |/       ▲`
  |┑      ∥
/"""
}

for _key, _art in ART_TEXTS.items():
    @cmd(_key, delete_cmd=True)
    async def art_handler(event, a=_art):
        await reply_to_target(event, a)

# ═══════════════ PUBLIC FEATURES ═══════════════
@cmd('weather', owner_only=True, delete_cmd=False)
async def weather_cmd(event):
    city = get_args(event.message)
    if not city:
        await event.reply("❌ **Usage:** `.weather city`")
        return
    await client.send_read_acknowledge(event.chat_id)
    try:
        city = city.strip().lower()
        if city == 'bihar':
            city = 'patna'
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    city_name = data.get('name', city.title())
                    country = data.get('sys', {}).get('country', '')
                    temp = data['main']['temp']
                    feels_like = data['main']['feels_like']
                    desc = data['weather'][0]['description'].title()
                    humidity = data['main']['humidity']
                    wind = data['wind']['speed']
                    pressure = data['main']['pressure']
                    emoji_map = {'clear': '☀️', 'clouds': '☁️', 'rain': '🌧️', 'snow': '❄️',
                                 'thunderstorm': '⛈️', 'drizzle': '🌦️', 'mist': '🌫️', 'smoke': '💨', 'haze': '🌫️'}
                    emoji = '🌤️'
                    for key, em in emoji_map.items():
                        if key in desc.lower():
                            emoji = em
                            break
                    msg = f"""**{emoji} Weather Report: {city_name}, {country}**
📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}

🌡️ **Temperature:** {temp}°C
🌡️ **Feels Like:** {feels_like}°C
📝 **Condition:** {desc}
💧 **Humidity:** {humidity}%
🌬️ **Wind Speed:** {wind} m/s
📊 **Pressure:** {pressure} hPa"""
                    await event.reply(msg)
                elif resp.status == 404:
                    url2 = f"http://api.openweathermap.org/data/2.5/weather?q={city},india&appid={WEATHER_API_KEY}&units=metric"
                    async with session.get(url2) as resp2:
                        if resp2.status == 200:
                            data = await resp2.json()
                            city_name = data.get('name', city.title())
                            country = data.get('sys', {}).get('country', '')
                            temp = data['main']['temp']
                            feels_like = data['main']['feels_like']
                            desc = data['weather'][0]['description'].title()
                            humidity = data['main']['humidity']
                            wind = data['wind']['speed']
                            pressure = data['main']['pressure']
                            emoji_map = {'clear': '☀️', 'clouds': '☁️', 'rain': '🌧️', 'snow': '❄️',
                                         'thunderstorm': '⛈️', 'drizzle': '🌦️', 'mist': '🌫️', 'smoke': '💨', 'haze': '🌫️'}
                            emoji = '🌤️'
                            for key, em in emoji_map.items():
                                if key in desc.lower():
                                    emoji = em
                                    break
                            msg = f"""**{emoji} Weather Report: {city_name}, {country}**
📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}

🌡️ **Temperature:** {temp}°C
🌡️ **Feels Like:** {feels_like}°C
📝 **Condition:** {desc}
💧 **Humidity:** {humidity}%
🌬️ **Wind Speed:** {wind} m/s
📊 **Pressure:** {pressure} hPa"""
                            await event.reply(msg)
                        else:
                            await event.reply(f"❌ City '{city}' not found.")
                else:
                    await event.reply(f"❌ Weather API error: {resp.status}")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)[:100]}")

@cmd('news', owner_only=True, delete_cmd=False)
async def news_cmd(event):
    query = get_args(event.message)
    await client.send_read_acknowledge(event.chat_id)
    try:
        if query:
            url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=5"
        else:
            url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={NEWS_API_KEY}&pageSize=5"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    articles = data.get('articles', [])
                    if not articles:
                        await event.reply(f"❌ No news found for '{query or 'India'}'")
                        return
                    articles = articles[:5]
                    location = query.title() if query else "India"
                    current_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
                    msg = f"**📰 Latest News - {location}**\n🕐 {current_time}\n" + "═" * 30 + "\n\n"
                    for i, article in enumerate(articles, 1):
                        title = article.get('title', 'No title')
                        source = article.get('source', {}).get('name', 'Unknown')
                        published = article.get('publishedAt', '')
                        time_str = ""
                        if published:
                            try:
                                pub_time = datetime.fromisoformat(published.replace('Z', '+00:00'))
                                time_str = pub_time.strftime("%I:%M %p")
                            except Exception:
                                pass
                        description = article.get('description', '')
                        if description and len(description) > 120:
                            description = description[:117] + '...'
                        msg += f"**{i}. {title}**\n📰 {source}"
                        if time_str:
                            msg += f" ⏰ {time_str}"
                        msg += "\n"
                        if description:
                            msg += f"📝 {description}\n"
                        msg += "\n" + "─" * 25 + "\n\n"
                    msg += f"🔗 Source: NewsAPI\n📅 {datetime.now().strftime('%d %b %Y')}"
                    await event.reply(msg)
                else:
                    await event.reply(f"❌ News API error: {resp.status}")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)[:100]}")

@cmd('azan', owner_only=True, delete_cmd=False)
async def azan_cmd(event):
    city = get_args(event.message)
    if not city:
        await event.reply("❌ **Usage:** `.azan city`")
        return
    await client.send_read_acknowledge(event.chat_id)
    try:
        url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=India&method=1"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if data.get('code') == 200:
                    t = data['data']['timings']
                    date = data['data']['date']['readable']
                    def convert_to_12h(time_str):
                        try:
                            if ':' in time_str:
                                parts = time_str.split(':')
                                hour = int(parts[0])
                                minute = int(parts[1])
                                ampm = "AM" if hour < 12 else "PM"
                                hour = hour % 12
                                if hour == 0:
                                    hour = 12
                                return f"{hour}:{minute:02d} {ampm}"
                            return time_str
                        except Exception:
                            return time_str
                    msg = f"""**🕌 Prayer Times: {city.title()}**
📅 {date}

🌅 **Fajr:** {convert_to_12h(t['Fajr'])}
☀️ **Sunrise:** {convert_to_12h(t['Sunrise'])}
🌙 **Dhuhr:** {convert_to_12h(t['Dhuhr'])}
🌤️ **Asr:** {convert_to_12h(t['Asr'])}
🌅 **Maghrib:** {convert_to_12h(t['Maghrib'])}
🌌 **Isha:** {convert_to_12h(t['Isha'])}"""
                    await event.reply(msg)
                else:
                    await event.reply(f"❌ City '{city}' not found.")
    except Exception as e:
        await event.reply(f"❌ Error: {str(e)[:100]}")

@cmd('play', owner_only=True, delete_cmd=False)
async def play_cmd(event):
    query = get_args(event.message)
    if not query:
        await event.reply("❌ **Usage:** `.play song_name`")
        return
    await client.send_read_acknowledge(event.chat_id)
    status_msg = await event.reply(f"🔍 Searching for '{query}'...")
    try:
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as resp:
                html = await resp.text()
                video_ids = re.findall(r'"videoId":"([^"]+)"', html)
                if not video_ids:
                    await status_msg.edit(f"❌ No results found for '{query}'")
                    return
                video_id = video_ids[0]
                video_url = f"https://youtube.com/watch?v={video_id}"
                video_titles = re.findall(r'"title":"([^"]+)"', html)
                title = video_titles[0].replace('\\u0026', '&').replace('\\u003c', '<').replace('\\u003e', '>') if video_titles else query
                title = re.sub(r'[^\w\s\-\.\&\(\)]', '', title)
                if len(title) > 60:
                    title = title[:57] + '...'
                duration = re.findall(r'"lengthSeconds":"([^"]+)"', html)
                duration_str = ""
                if duration:
                    try:
                        secs = int(duration[0])
                        mins = secs // 60
                        secs = secs % 60
                        duration_str = f"⏱️ {mins:02d}:{secs:02d}"
                    except Exception:
                        pass
                channels = re.findall(r'"ownerChannelName":"([^"]+)"', html)
                channel = channels[0] if channels else "YouTube"
                await status_msg.delete()
                msg = f"""**🎵 {title}**

📺 **Channel:** {channel}
{duration_str}

🔗 **Watch on YouTube:**

[{title}]({video_url})

---
💡 Tap the link above to open in Telegram"""
                await event.reply(msg, parse_mode='markdown', link_preview=True)
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)[:100]}")

# ═══════════════ IMAGE TOOLS ═══════════════
@cmd('sticker', delete_cmd=False)
async def sticker_cmd(event):
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        await event.reply("❌ Reply to an image!")
        return
    msg = await event.reply("🎨 Creating sticker...")
    try:
        from PIL import Image
        img_path = await reply.download_media(file=str(TEMP_DIR))
        img = Image.open(img_path).convert("RGBA")
        img.thumbnail((512, 512), Image.LANCZOS)
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        offset = ((512 - img.width) // 2, (512 - img.height) // 2)
        canvas.paste(img, offset, img)
        sticker_path = str(TEMP_DIR / "sticker.webp")
        canvas.save(sticker_path, "WEBP")
        await client.send_file(event.chat_id, sticker_path, force_document=False)
        try: os.remove(img_path)
        except: pass
        try: os.remove(sticker_path)
        except: pass
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

@cmd('toimg', delete_cmd=False)
async def toimg_cmd(event):
    reply = await event.get_reply_message()
    if not reply or not reply.sticker:
        await event.reply("❌ Reply to a sticker!")
        return
    msg = await event.reply("🖼️ Converting...")
    try:
        from PIL import Image
        sticker_path = await reply.download_media(file=str(TEMP_DIR))
        img = Image.open(sticker_path).convert("RGBA")
        img_path = str(TEMP_DIR / "from_sticker.png")
        img.save(img_path, "PNG")
        await client.send_file(event.chat_id, img_path, caption="🖼️ **Sticker → Image**")
        try: os.remove(sticker_path)
        except: pass
        try: os.remove(img_path)
        except: pass
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

@cmd('blur', delete_cmd=False)
async def blur_cmd(event):
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        await event.reply("❌ Reply to an image!")
        return
    msg = await event.reply("🎨 Blurring...")
    try:
        from PIL import Image, ImageFilter
        img_path = await reply.download_media(file=str(TEMP_DIR))
        img = Image.open(img_path)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=15))
        output = str(TEMP_DIR / "blurred.jpg")
        blurred.save(output, "JPEG", quality=85)
        await client.send_file(event.chat_id, output, caption="🎨 **Blurred**")
        try: os.remove(img_path)
        except: pass
        try: os.remove(output)
        except: pass
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

@cmd('img2pdf', delete_cmd=False)
async def img2pdf_cmd(event):
    reply = await event.get_reply_message()
    if not reply or not reply.photo:
        await event.reply("❌ Reply to an image!")
        return
    msg = await event.reply("📄 Converting to PDF...")
    try:
        import img2pdf
        img_path = await reply.download_media(file=str(TEMP_DIR))
        pdf_path = str(TEMP_DIR / "output.pdf")
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert(img_path))
        await client.send_file(event.chat_id, pdf_path, caption="📄 **PDF Created**")
        try: os.remove(img_path)
        except: pass
        try: os.remove(pdf_path)
        except: pass
        await msg.delete()
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

# ═══════════════ FORECAST ═══════════════
@cmd('forecast', owner_only=True, delete_cmd=False)
async def forecast_cmd(event):
    city = get_args(event.message)
    if not city:
        await event.reply("❌ Usage: `.forecast <city>`")
        return
    msg = await event.reply("🌤️ Loading forecast...")
    try:
        url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_API_KEY}&units=metric&cnt=40"
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status != 200:
                    await msg.edit("❌ City not found")
                    return
                data = await r.json()
        text = f"🌤️ **5-Day Forecast: {data['city']['name']}**\n\n"
        daily = {}
        for item in data['list']:
            date = item['dt_txt'].split()[0]
            if date not in daily:
                daily[date] = item
        for date, item in list(daily.items())[:5]:
            temp = item['main']['temp']
            desc = item['weather'][0]['description'].title()
            emoji_map = {'clear':'☀️','clouds':'☁️','rain':'🌧️','snow':'❄️','thunderstorm':'⛈️','drizzle':'🌦️','mist':'🌫️'}
            em = '🌤️'
            for k, v in emoji_map.items():
                if k in desc.lower():
                    em = v; break
            text += f"**{date}** {em} {temp}°C — {desc}\n"
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

# ═══════════════ AQI ═══════════════
@cmd('aqi', owner_only=True, delete_cmd=False)
async def aqi_cmd(event):
    city = get_args(event.message)
    if not city:
        await event.reply("❌ Usage: `.aqi <city>`")
        return
    msg = await event.reply("🌫️ Loading AQI...")
    try:
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={WEATHER_API_KEY}"
        async with aiohttp.ClientSession() as s:
            async with s.get(geo_url) as r:
                geo = await r.json()
        if not geo:
            await msg.edit("❌ City not found")
            return
        lat, lon = geo[0]['lat'], geo[0]['lon']
        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
        async with aiohttp.ClientSession() as s:
            async with s.get(aqi_url) as r:
                data = await r.json()
        aqi = data['list'][0]['main']['aqi']
        components = data['list'][0]['components']
        levels = {1: "🟢 Good", 2: "🟡 Fair", 3: "🟠 Moderate", 4: "🔴 Poor", 5: "⚫ Very Poor"}
        text = (
            f"🌫️ **AQI: {city.title()}**\n\n"
            f"**Air Quality:** {levels.get(aqi, 'Unknown')} ({aqi}/5)\n\n"
            f"**Pollutants:**\n"
            f"• PM2.5: {components.get('pm2_5', 0)} µg/m³\n"
            f"• PM10: {components.get('pm10', 0)} µg/m³\n"
            f"• NO₂: {components.get('no2', 0)} µg/m³\n"
            f"• O₃: {components.get('o3', 0)} µg/m³\n"
            f"• CO: {components.get('co', 0)} µg/m³"
        )
        await msg.edit(text, parse_mode='markdown')
    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)[:200]}`")

# ═══════════════ HEALTH CHECK SERVER (Render ke liye) ═══════════════
async def health_server():
    async def handle(request):
        return web.Response(text="✅ Codernova Userbot Running")
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', handle)
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"✅ Health server on port {port}")
    await asyncio.Event().wait()

# ═══════════════ STARTUP ═══════════════
async def main():
    # Health server background me chalao (Render ke liye)
    asyncio.create_task(health_server())
    
    await client.start(phone=PHONE_NUMBER)
    me = await client.get_me()
    log.info(f"✅ Userbot Started: {me.first_name} (@{me.username})")
    log.info(f"👑 Owner: {OWNER_ID}")
    log.info("⚙️ Type .help in any chat.")
    await client.run_until_disconnected()

if __name__ == '__main__':
    print("=" * 50)
    print("  CODERNOVA SINGLE-USER USERBOT")
    print("=" * 50)
    try:
        if __name__ == '__main__':
    print("=" * 50)
    print("  CODERNOVA SINGLE-USER USERBOT")
    print("=" * 50)
    try:
        asyncio.run(main())                        ← ✅ ye lagao
    except KeyboardInterrupt:
        log.info("🛑 Stopped.")
    except Exception as e:
        log.error(f"Fatal: {e}")
