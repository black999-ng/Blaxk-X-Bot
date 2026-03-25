#!/usr/bin/env python3
"""
================================================================
X SMART CONTENT BOT v3 — Full Featured Multi-User Edition
================================================================
Telegram bot that helps developers manage X (Twitter) posts.
One-tap posting via X intent URLs. No API keys. No passwords.
Zero risk to your X account.

Features:
  - Multi-user (anyone can use it)
  - One-tap posting (X opens with text pre-filled)
  - Persistent keyboard buttons (no typing commands)
  - Smart content variety balancing
  - Posting streak tracker
  - Content templates
  - Drafts
  - Weekly analytics
  - Admin panel
  - Scheduled reminders per user timezone

Deploy to Render with just TELEGRAM_BOT_TOKEN.
Or run locally: python bot.py
================================================================
"""

import os
import sys
import json
import uuid
import random
import logging
import threading
import time as _time
from pathlib import Path
from datetime import datetime, timedelta, time as dt_time
from collections import Counter
from functools import wraps
from urllib.parse import quote as url_encode

import pytz
from flask import Flask, jsonify

from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PORT = int(os.getenv("PORT", 10000))

DATA_DIR = Path(__file__).parent / "data"
USERS_FILE = DATA_DIR / "users.json"
ADMIN_FILE = DATA_DIR / "admin.json"
CONFIG_FILE = DATA_DIR / "config.json"

# Conversation states
(
    SETUP_NAME,
    SETUP_TIMEZONE,
    SETUP_CUSTOM_TIMEZONE,
    SETUP_SCHEDULE,
    SETUP_CUSTOM_SCHEDULE,
    ADDING_SINGLE,
    ADDING_THREAD_TWEETS,
    ADDING_BULK,
    TEMPLATE_FILLING,
    ADDING_DRAFT,
) = range(10)

CATEGORIES = {
    "tip": {"emoji": "💻", "label": "Code Tip"},
    "project": {"emoji": "🚀", "label": "Project Update"},
    "thread": {"emoji": "🧵", "label": "Thread/Lesson"},
    "opentowork": {"emoji": "💼", "label": "Open to Work"},
    "question": {"emoji": "❓", "label": "Question"},
    "motivation": {"emoji": "💪", "label": "Motivation"},
    "showcase": {"emoji": "🎨", "label": "Showcase"},
    "opinion": {"emoji": "🗣️", "label": "Hot Take"},
    "resource": {"emoji": "📚", "label": "Resource"},
    "personal": {"emoji": "👋", "label": "Personal"},
    "general": {"emoji": "📝", "label": "General"},
}

TIMEZONE_OPTIONS = {
    "Africa/Lagos": "🇳🇬 Lagos / WAT (UTC+1)",
    "Africa/Nairobi": "🇰🇪 Nairobi / EAT (UTC+3)",
    "Africa/Cairo": "🇪🇬 Cairo (UTC+2)",
    "Africa/Johannesburg": "🇿🇦 Johannesburg (UTC+2)",
    "Africa/Accra": "🇬🇭 Accra / GMT (UTC+0)",
    "Europe/London": "🇬🇧 London (UTC+0)",
    "Europe/Berlin": "🇩🇪 Berlin (UTC+1)",
    "America/New_York": "🇺🇸 New York (UTC-5)",
    "America/Los_Angeles": "🇺🇸 Los Angeles (UTC-8)",
    "America/Sao_Paulo": "🇧🇷 São Paulo (UTC-3)",
    "Asia/Kolkata": "🇮🇳 India (UTC+5:30)",
    "Asia/Dubai": "🇦🇪 Dubai (UTC+4)",
    "Asia/Shanghai": "🇨🇳 Shanghai (UTC+8)",
    "Asia/Tokyo": "🇯🇵 Tokyo (UTC+9)",
    "Australia/Sydney": "🇦🇺 Sydney (UTC+10)",
}

SCHEDULE_PRESETS = {
    "default": {
        "label": "📌 Balanced (5x/day)",
        "times": ["07:30", "11:00", "14:30", "18:00", "21:00"],
    },
    "morning": {
        "label": "🌅 Morning Focus (3x)",
        "times": ["07:00", "09:00", "11:00"],
    },
    "evening": {
        "label": "🌙 Evening Focus (3x)",
        "times": ["15:00", "18:00", "21:00"],
    },
    "aggressive": {
        "label": "⚡ Aggressive (7x)",
        "times": ["07:00", "09:00", "11:00", "13:00", "16:00", "19:00", "21:00"],
    },
    "minimal": {
        "label": "🍃 Minimal (2x)",
        "times": ["09:00", "18:00"],
    },
}

TEMPLATES = {
    "tip": {
        "name": "💻 Code Tip",
        "fields": ["language", "tip_content", "code_example", "hashtags"],
        "prompts": [
            "What language/framework? (e.g., JavaScript, CSS, Python)",
            "What's the tip? (explain simply)",
            "Code example? (or 'skip')",
            "Hashtags? (e.g., #JavaScript #WebDev) or 'skip'",
        ],
        "template": "{language} tip:\n\n{tip_content}\n\n{code_example}\n\n{hashtags}",
    },
    "project": {
        "name": "🚀 Project Update",
        "fields": ["day_label", "progress", "tech_stack", "next_steps", "hashtags"],
        "prompts": [
            "Day/update label? (e.g., Day 14, Week 3)",
            "What did you accomplish?",
            "Tech stack used?",
            "What's next?",
            "Hashtags? or 'skip'",
        ],
        "template": "Building in public — {day_label}\n\n{progress}\n\nBuilt with: {tech_stack}\n\nNext: {next_steps}\n\n{hashtags}",
    },
    "opentowork": {
        "name": "💼 Open to Work",
        "fields": ["name", "role", "location", "looking_for", "stack", "closing"],
        "prompts": [
            "Your name?",
            "Your role? (e.g., Full-Stack Developer)",
            "Your location?",
            "What are you looking for?",
            "Your tech stack?",
            "Closing line? (e.g., DM me!)",
        ],
        "template": "👋 I'm {name}, a {role} based in {location}.\n\nOpen to:\n{looking_for}\n\nStack:\n{stack}\n\n{closing}\n\n#OpenToWork #Developer",
    },
    "question": {
        "name": "❓ Engagement Question",
        "fields": ["question", "my_answer", "hashtags"],
        "prompts": [
            "Your question for devs?",
            "Your own answer (lead by example)",
            "Hashtags? or 'skip'",
        ],
        "template": "{question}\n\nMy answer:\n{my_answer}\n\nWhat's yours? 👇\n\n{hashtags}",
    },
    "showcase": {
        "name": "🎨 Project Showcase",
        "fields": ["project_name", "description", "stack", "features", "link", "hashtags"],
        "prompts": [
            "Project name?",
            "One-line description?",
            "Tech stack?",
            "Key features? (list 2-4)",
            "Link? or 'skip'",
            "Hashtags? or 'skip'",
        ],
        "template": "Just shipped: {project_name} 🚀\n\n{description}\n\nBuilt with: {stack}\n\n{features}\n\n{link}\n\n{hashtags}",
    },
}

HASHTAG_SUGGESTIONS = {
    "javascript": ["#JavaScript", "#JS", "#WebDev", "#DevTips"],
    "css": ["#CSS", "#WebDev", "#FrontEnd", "#WebDesign"],
    "html": ["#HTML", "#WebDev", "#FrontEnd", "#A11y"],
    "react": ["#ReactJS", "#React", "#JavaScript", "#FrontEnd"],
    "nextjs": ["#NextJS", "#React", "#Vercel", "#FullStack"],
    "nodejs": ["#NodeJS", "#Backend", "#API", "#JavaScript"],
    "python": ["#Python", "#DevTips", "#Coding", "#Programming"],
    "general": ["#WebDev", "#DevLife", "#Programming", "#CodeNewbie"],
    "career": ["#OpenToWork", "#Developer", "#RemoteWork", "#TechJobs"],
    "building": ["#BuildInPublic", "#IndieHacker", "#SideProject"],
}

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("xbot")
logging.getLogger("httpx").setLevel(logging.WARNING)


# ════════════════════════════════════════════════════════════
# BOOT — Get Bot Token
# ════════════════════════════════════════════════════════════

def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_saved_config() -> dict:
    _ensure_data_dir()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(cfg: dict):
    _ensure_data_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def get_bot_token() -> str:
    global BOT_TOKEN

    if BOT_TOKEN and "paste" not in BOT_TOKEN.lower() and len(BOT_TOKEN) > 20:
        return BOT_TOKEN

    cfg = load_saved_config()
    if cfg.get("bot_token") and len(cfg["bot_token"]) > 20:
        BOT_TOKEN = cfg["bot_token"]
        return BOT_TOKEN

    print("=" * 55)
    print("  🤖 X Smart Bot — First Time Setup")
    print("=" * 55)
    print()
    print("  You need a Telegram Bot Token.")
    print()
    print("  How to get one (takes 1 minute):")
    print("  1. Open Telegram")
    print("  2. Search for @BotFather")
    print("  3. Send: /newbot")
    print("  4. Choose a name (e.g., 'X Content Bot')")
    print("  5. Choose a username (must end in 'bot')")
    print("  6. Copy the token BotFather gives you")
    print()
    print("=" * 55)

    while True:
        try:
            token = input("\n  Paste your bot token here: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            sys.exit(0)

        if not token:
            print("  ❌ Cannot be empty.")
            continue
        if ":" not in token:
            print("  ❌ Invalid token. It looks like: 7123456789:AAHxxxxxxxxxx")
            continue

        BOT_TOKEN = token
        cfg = load_saved_config()
        cfg["bot_token"] = token
        save_config(cfg)
        print(f"\n  ✅ Token saved! You won't need to enter it again.")
        print(f"  ℹ️  On Render, set TELEGRAM_BOT_TOKEN in Environment tab instead.\n")
        return token


# ════════════════════════════════════════════════════════════
# DATA STORAGE
# ════════════════════════════════════════════════════════════

def _user_file(chat_id) -> Path:
    return DATA_DIR / f"user_{chat_id}.json"


def _default_user(chat_id, name="") -> dict:
    return {
        "chat_id": str(chat_id),
        "name": name,
        "timezone": "Africa/Lagos",
        "schedule": ["07:30", "11:00", "14:30", "18:00", "21:00"],
        "joined": datetime.utcnow().isoformat(),
        "setup_complete": False,
        "paused": False,
        "posts": [],
        "drafts": [],
        "posted_ids": [],
        "stats": {
            "total_added": 0,
            "total_posted": 0,
            "daily_counts": {},
            "category_counts": {},
            "posting_times": [],
            "streak_current": 0,
            "streak_best": 0,
            "last_post_date": None,
        },
        "_last_reminder": "",
    }


def load_user(chat_id) -> dict | None:
    path = _user_file(chat_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        defaults = _default_user(chat_id)
        for k in defaults:
            if k not in data:
                data[k] = defaults[k]
        for k in defaults["stats"]:
            if k not in data.get("stats", {}):
                data["stats"][k] = defaults["stats"][k]
        return data
    except (json.JSONDecodeError, IOError):
        return None


def save_user(data: dict):
    _ensure_data_dir()
    path = _user_file(data.get("chat_id", "unknown"))
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Save user failed: {e}")


def delete_user_data(chat_id) -> bool:
    path = _user_file(chat_id)
    if path.exists():
        path.unlink()
        registry = load_user_registry()
        registry["users"] = [u for u in registry.get("users", []) if str(u.get("chat_id")) != str(chat_id)]
        save_user_registry(registry)
        return True
    return False


def load_user_registry() -> dict:
    _ensure_data_dir()
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"users": [], "total_signups": 0}


def save_user_registry(registry: dict):
    _ensure_data_dir()
    with open(USERS_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def register_user(chat_id, name):
    registry = load_user_registry()
    existing = [str(u.get("chat_id")) for u in registry.get("users", [])]
    if str(chat_id) not in existing:
        registry["users"].append({
            "chat_id": str(chat_id),
            "name": name,
            "joined": datetime.utcnow().isoformat(),
        })
        registry["total_signups"] = registry.get("total_signups", 0) + 1
        save_user_registry(registry)


def load_admin() -> dict:
    _ensure_data_dir()
    if ADMIN_FILE.exists():
        try:
            with open(ADMIN_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"admin_ids": []}


def save_admin(data: dict):
    _ensure_data_dir()
    with open(ADMIN_FILE, "w") as f:
        json.dump(data, f, indent=2)


def is_admin(chat_id) -> bool:
    return str(chat_id) in [str(x) for x in load_admin().get("admin_ids", [])]


def set_admin(chat_id):
    admin = load_admin()
    cid = str(chat_id)
    if cid not in [str(x) for x in admin.get("admin_ids", [])]:
        admin["admin_ids"].append(cid)
        save_admin(admin)


# ════════════════════════════════════════════════════════════
# USER DATA HELPERS
# ════════════════════════════════════════════════════════════

def get_user_tz(user):
    try:
        return pytz.timezone(user.get("timezone", "Africa/Lagos"))
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.timezone("Africa/Lagos")


def add_user_post(user, text, post_type="single", tweets=None, category="general"):
    post = {
        "id": uuid.uuid4().hex[:8],
        "type": post_type,
        "text": text if post_type == "single" else "",
        "tweets": tweets or [],
        "category": category,
        "created": datetime.now(get_user_tz(user)).isoformat(),
        "posted": False,
    }
    user["posts"].append(post)
    user["stats"]["total_added"] = user["stats"].get("total_added", 0) + 1
    save_user(user)
    return post


def get_user_unposted(user):
    posted = set(user.get("posted_ids", []))
    return [p for p in user.get("posts", []) if p["id"] not in posted and not p.get("posted")]


def pick_user_smart_post(user):
    unposted = get_user_unposted(user)
    if not unposted:
        return None

    recent_ids = user.get("posted_ids", [])[-10:]
    recent_cats = []
    for pid in recent_ids:
        for p in user.get("posts", []):
            if p["id"] == pid:
                recent_cats.append(p.get("category", "general"))
                break

    last_cat = recent_cats[-1] if recent_cats else None
    cat_counts = Counter(recent_cats)
    available = set(p.get("category", "general") for p in unposted)

    if "opentowork" in available and cat_counts.get("opentowork", 0) == 0 and len(recent_ids) >= 10:
        otw = [p for p in unposted if p.get("category") == "opentowork"]
        if otw:
            return random.choice(otw)

    preferred = [c for c in available if c != last_cat and cat_counts.get(c, 0) < 2]
    if preferred:
        pool = [p for p in unposted if p.get("category") in preferred]
        if pool:
            return random.choice(pool)

    if last_cat:
        diff = [p for p in unposted if p.get("category") != last_cat]
        if diff:
            return random.choice(diff)

    return random.choice(unposted)


def mark_user_posted(user, post_id):
    tz = get_user_tz(user)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    if post_id not in user["posted_ids"]:
        user["posted_ids"].append(post_id)

    cat = "general"
    for p in user["posts"]:
        if p["id"] == post_id:
            p["posted"] = True
            p["posted_date"] = now.isoformat()
            cat = p.get("category", "general")
            break

    s = user["stats"]
    s["total_posted"] = s.get("total_posted", 0) + 1
    s.setdefault("daily_counts", {})[today] = s["daily_counts"].get(today, 0) + 1
    s.setdefault("category_counts", {})[cat] = s["category_counts"].get(cat, 0) + 1
    s.setdefault("posting_times", []).append(now.strftime("%H:%M"))
    s["posting_times"] = s["posting_times"][-100:]

    last = s.get("last_post_date")
    if last:
        try:
            diff = (now.date() - datetime.fromisoformat(last).date()).days
            if diff == 0:
                pass
            elif diff == 1:
                s["streak_current"] = s.get("streak_current", 0) + 1
            else:
                s["streak_current"] = 1
        except (ValueError, TypeError):
            s["streak_current"] = 1
    else:
        s["streak_current"] = 1

    s["last_post_date"] = today
    if s.get("streak_current", 0) > s.get("streak_best", 0):
        s["streak_best"] = s["streak_current"]

    save_user(user)


def get_user_today_count(user):
    today = datetime.now(get_user_tz(user)).strftime("%Y-%m-%d")
    return user.get("stats", {}).get("daily_counts", {}).get(today, 0)


def get_user_streak(user):
    s = user.get("stats", {})
    current = s.get("streak_current", 0)
    best = s.get("streak_best", 0)
    last = s.get("last_post_date")
    if last:
        try:
            diff = (datetime.now(get_user_tz(user)).date() - datetime.fromisoformat(last).date()).days
            if diff > 1:
                current = 0
        except (ValueError, TypeError):
            pass
    return {"current": current, "best": best}


def delete_user_post(user, post_id):
    orig = len(user["posts"])
    user["posts"] = [p for p in user["posts"] if p["id"] != post_id]
    if len(user["posts"]) < orig:
        save_user(user)
        return True
    return False


def edit_user_post(user, post_id, new_text):
    for p in user["posts"]:
        if p["id"] == post_id:
            p["text"] = new_text
            p["edited"] = datetime.now(get_user_tz(user)).isoformat()
            save_user(user)
            return True
    return False


# ════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ════════════════════════════════════════════════════════════

def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def char_bar(length, limit=280):
    ratio = min(length / limit, 1.0)
    filled = int(ratio * 20)
    empty = 20 - filled
    if length <= limit * 0.8:
        c = "🟩"
    elif length <= limit:
        c = "🟨"
    else:
        c = "🟥"
    status = "✅" if length <= limit else "❌"
    return f"{c * filled}{'⬜' * empty} {length}/{limit} {status}"


def suggest_hashtags(text):
    tl = text.lower()
    found = set()
    kw = {
        "javascript": "javascript", "js ": "javascript", "const ": "javascript",
        "css": "css", "flexbox": "css", "html": "html", "react": "react",
        "component": "react", "next.js": "nextjs", "nextjs": "nextjs",
        "node": "nodejs", "express": "nodejs", "python": "python",
        "django": "python", "build": "building", "ship": "building",
        "hiring": "career", "job": "career", "intern": "career",
        "freelance": "career", "open to work": "career",
    }
    for k, topic in kw.items():
        if k in tl:
            found.update(HASHTAG_SUGGESTIONS.get(topic, [])[:3])
    if not found:
        found.update(HASHTAG_SUGGESTIONS.get("general", [])[:3])
    return " ".join(list(found)[:5])


def get_cat_info(category):
    return CATEGORIES.get(category, CATEGORIES["general"])


def get_cat_keyboard():
    buttons = []
    row = []
    for key, info in CATEGORIES.items():
        row.append(InlineKeyboardButton(f"{info['emoji']} {info['label']}", callback_data=f"cat:{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["📝 Add Post", "📤 Next Post", "📊 Stats"],
            ["📋 Queue", "🔥 Streak", "📋 Template"],
            ["📦 Bulk Add", "✏️ Draft", "⚙️ Settings"],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Tap a button or type a command...",
    )


def make_post_url(text):
    """Create X intent URL — opens X with tweet pre-filled. Official X feature."""
    encoded = url_encode(text, safe="")
    return f"https://x.com/intent/tweet?text={encoded}"


def get_suggestions(user):
    suggestions = []
    unposted = get_user_unposted(user)
    stats = user.get("stats", {})
    streak = get_user_streak(user)
    total_posted = stats.get("total_posted", 0)
    cat_posted = stats.get("category_counts", {})

    if total_posted > 15 and cat_posted.get("opentowork", 0) == 0:
        suggestions.append("💼 No 'Open to Work' posts yet! Try /template")
    if total_posted > 0 and cat_posted.get("opentowork", 0) / max(total_posted, 1) > 0.3:
        suggestions.append("⚠️ Over 30% are 'Open to Work'. Add more tips & projects.")
    if streak["current"] >= 7:
        suggestions.append(f"🔥 {streak['current']}-day streak! Amazing!")
    elif streak["current"] == 0:
        suggestions.append("💪 Start a posting streak today!")
    if len(unposted) < 3:
        suggestions.append(f"⚠️ Only {len(unposted)} posts left! Add more with /bulk or /template")
    elif len(unposted) > 30:
        suggestions.append(f"📦 {len(unposted)} queued — ~{len(unposted)//5} days of content!")
    return suggestions


# ════════════════════════════════════════════════════════════
# MIDDLEWARE
# ════════════════════════════════════════════════════════════

def require_setup(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user = load_user(chat_id)
        if not user or not user.get("setup_complete"):
            await update.message.reply_text("👋 Send /start to set up first!")
            return
        return await func(update, context)
    return wrapper


# ════════════════════════════════════════════════════════════
# SETUP FLOW
# ════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = load_user(chat_id)

    if user and user.get("setup_complete"):
        streak = get_user_streak(user)
        queue = len(get_user_unposted(user))
        today = get_user_today_count(user)
        s = f"🔥 {streak['current']}d streak" if streak["current"] > 0 else "💪 Start your streak"

        await update.message.reply_text(
            f"🤖 <b>X Smart Bot</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Welcome back, <b>{escape_html(user.get('name', 'friend'))}</b>!\n"
            f"{s} | 📋 {queue} queued | 📆 {today} today\n\n"
            f"Tap a button below or use / menu for all commands.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "👋 <b>Welcome to X Smart Bot!</b>\n\n"
        "I help developers manage their X (Twitter) posts.\n\n"
        "✅ No X API keys needed\n"
        "✅ No passwords stored\n"
        "✅ One-tap posting to X\n"
        "✅ Posting streaks & analytics\n\n"
        "Let's set you up! (30 seconds)\n\n"
        "<b>What's your name?</b>",
        parse_mode="HTML",
    )
    return SETUP_NAME


async def setup_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()[:50]
    if not name:
        await update.message.reply_text("Enter a valid name.")
        return SETUP_NAME

    context.user_data["setup_name"] = name

    buttons = []
    for tz_key, tz_label in TIMEZONE_OPTIONS.items():
        buttons.append([InlineKeyboardButton(tz_label, callback_data=f"tz:{tz_key}")])
    buttons.append([InlineKeyboardButton("🌐 Other (type manually)", callback_data="tz:custom")])

    await update.message.reply_text(
        f"Nice to meet you, <b>{escape_html(name)}</b>! 👋\n\n<b>Your timezone?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SETUP_TIMEZONE


async def setup_tz_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tz_key = query.data[3:]

    if tz_key == "custom":
        await query.edit_message_text(
            "🌐 Type your timezone.\nExample: Africa/Lagos, US/Eastern, Asia/Tokyo"
        )
        return SETUP_CUSTOM_TIMEZONE

    context.user_data["setup_tz"] = tz_key

    buttons = []
    for key, preset in SCHEDULE_PRESETS.items():
        buttons.append([InlineKeyboardButton(
            f"{preset['label']} — {', '.join(preset['times'])}",
            callback_data=f"sched:{key}"
        )])
    buttons.append([InlineKeyboardButton("⏰ Custom times", callback_data="sched:custom")])

    await query.edit_message_text(
        f"✅ Timezone set!\n\n<b>When should I remind you to post?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SETUP_SCHEDULE


async def setup_custom_tz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz_input = update.message.text.strip()
    try:
        pytz.timezone(tz_input)
    except pytz.exceptions.UnknownTimeZoneError:
        await update.message.reply_text(f"❌ Unknown: '{tz_input}'. Try 'Africa/Lagos' or 'US/Eastern'.")
        return SETUP_CUSTOM_TIMEZONE

    context.user_data["setup_tz"] = tz_input

    buttons = []
    for key, preset in SCHEDULE_PRESETS.items():
        buttons.append([InlineKeyboardButton(
            f"{preset['label']} — {', '.join(preset['times'])}",
            callback_data=f"sched:{key}"
        )])
    buttons.append([InlineKeyboardButton("⏰ Custom times", callback_data="sched:custom")])

    await update.message.reply_text(
        f"✅ Timezone: {tz_input}\n\n<b>Reminder schedule?</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return SETUP_SCHEDULE


async def setup_sched_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data[6:]

    if key == "custom":
        await query.edit_message_text(
            "⏰ Send comma-separated times (24h).\nExample: <code>08:00, 12:30, 17:00, 20:00</code>",
            parse_mode="HTML",
        )
        return SETUP_CUSTOM_SCHEDULE

    preset = SCHEDULE_PRESETS.get(key, SCHEDULE_PRESETS["default"])
    context.user_data["setup_schedule"] = preset["times"]
    await _finish_setup(query.message.chat.id, context, edit_message=query)
    return ConversationHandler.END


async def setup_custom_sched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    times = []
    for part in raw.replace(";", ",").split(","):
        t = part.strip()
        if ":" in t:
            try:
                h, m = map(int, t.split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    times.append(f"{h:02d}:{m:02d}")
            except ValueError:
                pass

    if not times:
        await update.message.reply_text("❌ No valid times. Use format: <code>08:00, 12:30</code>", parse_mode="HTML")
        return SETUP_CUSTOM_SCHEDULE

    context.user_data["setup_schedule"] = sorted(times)
    await _finish_setup(update.effective_chat.id, context, message=update.message)
    return ConversationHandler.END


async def _finish_setup(chat_id, context, edit_message=None, message=None):
    name = context.user_data.get("setup_name", "Friend")
    tz = context.user_data.get("setup_tz", "Africa/Lagos")
    schedule = context.user_data.get("setup_schedule", ["07:30", "11:00", "14:30", "18:00", "21:00"])

    user = _default_user(chat_id, name)
    user["timezone"] = tz
    user["schedule"] = schedule
    user["setup_complete"] = True
    save_user(user)
    register_user(chat_id, name)

    text = (
        f"✅ <b>You're all set, {escape_html(name)}!</b>\n\n"
        f"🕐 Timezone: {tz}\n"
        f"🔔 Reminders: {', '.join(schedule)}\n\n"
        f"<b>Quick start:</b>\n"
        f"• Tap '📝 Add Post' to add your first post\n"
        f"• Tap '📋 Template' for fill-in-the-blank posts\n"
        f"• Tap '📤 Next Post' to get a post to publish\n\n"
        f"🚀 Reminders start at the next scheduled time!"
    )

    if edit_message:
        await edit_message.edit_message_text(text, parse_mode="HTML")
        await edit_message.message.reply_text(
            "👇 Use these buttons anytime:",
            reply_markup=get_main_keyboard(),
        )
    elif message:
        await message.reply_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())

    context.user_data.clear()
    logger.info(f"New user: {name} ({chat_id})")


# ════════════════════════════════════════════════════════════
# ADD POST
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        text = " ".join(context.args)
        context.user_data["pending_text"] = text
        bar = char_bar(len(text))
        h = suggest_hashtags(text)
        msg = f"📝 <b>Choose category:</b>\n\n{bar}"
        if h:
            msg += f"\n💡 Suggested: <code>{h}</code>"
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_cat_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 <b>New Post</b>\n\nSend me the tweet text.\n/cancel to cancel.",
        parse_mode="HTML",
    )
    return ADDING_SINGLE


async def receive_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Empty. Try again or /cancel.")
        return ADDING_SINGLE

    context.user_data["pending_text"] = text
    bar = char_bar(len(text))
    h = suggest_hashtags(text)
    msg = f"📝 <b>Choose category:</b>\n\n{bar}"
    if h:
        msg += f"\n💡 Suggested: <code>{h}</code>"
    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=get_cat_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
# THREAD
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["thread_tweets"] = []
    await update.message.reply_text(
        "🧵 <b>New Thread</b>\n\nSend each tweet one by one.\n"
        "/preview — see thread\n/save — save\n/cancel — discard\n\n"
        "Send <b>Tweet 1</b>:",
        parse_mode="HTML",
    )
    return ADDING_THREAD_TWEETS


async def receive_thread_tweet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    tweets = context.user_data.get("thread_tweets", [])
    tweets.append(text)
    context.user_data["thread_tweets"] = tweets

    await update.message.reply_text(
        f"✅ <b>Tweet {len(tweets)}</b> ({len(text)} chars)\n{char_bar(len(text))}\n\n"
        f"Send Tweet {len(tweets)+1}, /save, or /cancel",
        parse_mode="HTML",
    )
    return ADDING_THREAD_TWEETS


async def preview_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tweets = context.user_data.get("thread_tweets", [])
    if not tweets:
        await update.message.reply_text("Empty. Send first tweet.")
        return ADDING_THREAD_TWEETS

    msg = f"🧵 <b>Preview ({len(tweets)})</b>\n{'━'*30}\n"
    for i, t in enumerate(tweets, 1):
        msg += f"\n<b>{i}.</b> ({len(t)}ch)\n{escape_html(t)}\n"
    msg += f"\n{'━'*30}\n/save or send more"
    await update.message.reply_text(msg, parse_mode="HTML")
    return ADDING_THREAD_TWEETS


async def save_thread(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tweets = context.user_data.get("thread_tweets", [])
    if len(tweets) < 2:
        await update.message.reply_text("Need 2+ tweets. Send more or /cancel.")
        return ADDING_THREAD_TWEETS

    user = load_user(update.effective_chat.id)
    post = add_user_post(user, tweets[0], "thread", tweets, "thread")
    context.user_data["thread_tweets"] = []

    await update.message.reply_text(
        f"✅ <b>Thread saved!</b> ({len(tweets)} tweets)\n"
        f"🆔 <code>{post['id']}</code> | Queue: {len(get_user_unposted(user))}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
# BULK
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 <b>Bulk Add</b>\n\nPaste multiple posts separated by <b>blank lines</b>.\n\n"
        "Example:\n<code>First tweet about CSS\n\nSecond about JS\n\nThird one</code>\n\n"
        "/cancel to cancel.",
        parse_mode="HTML",
    )
    return ADDING_BULK


async def receive_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    chunks = [c.strip() for c in raw.split("\n\n") if c.strip()]
    if not chunks:
        await update.message.reply_text("❌ No posts found. Separate with blank lines.")
        return ADDING_BULK

    user = load_user(update.effective_chat.id)
    warnings = []
    for i, chunk in enumerate(chunks, 1):
        add_user_post(user, chunk, category="general")
        if len(chunk) > 280:
            warnings.append(f"⚠️ Post {i}: {len(chunk)} chars")

    w = "\n".join(warnings)
    if w:
        w = "\n\n" + w

    await update.message.reply_text(
        f"✅ <b>{len(chunks)} posts added!</b>{w}\n\n"
        f"📊 Queue: {len(get_user_unposted(user))}\nSend more or /done.",
        parse_mode="HTML",
    )
    return ADDING_BULK


# ════════════════════════════════════════════════════════════
# TEMPLATE
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(t["name"], callback_data=f"tmpl:{k}")] for k, t in TEMPLATES.items()]
    await update.message.reply_text(
        "📋 <b>Post Templates</b>\n\nPick one to fill in:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def receive_template_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    key = context.user_data.get("tmpl_key", "")
    tmpl = TEMPLATES.get(key)
    if not tmpl:
        await update.message.reply_text("❌ Lost template. /template to restart.")
        return ConversationHandler.END

    idx = context.user_data.get("tmpl_idx", 0)
    field = tmpl["fields"][idx]
    context.user_data.setdefault("tmpl_fields", {})[field] = "" if answer.lower() == "skip" else answer

    idx += 1
    context.user_data["tmpl_idx"] = idx

    if idx < len(tmpl["fields"]):
        await update.message.reply_text(
            f"✅ Got it!\n\n<b>Q{idx+1}:</b> {tmpl['prompts'][idx]}",
            parse_mode="HTML",
        )
        return TEMPLATE_FILLING

    filled = context.user_data.get("tmpl_fields", {})
    try:
        text = tmpl["template"].format(**filled)
    except KeyError:
        text = tmpl["template"]
        for k, v in filled.items():
            text = text.replace(f"{{{k}}}", v)

    text = "\n".join(l for l in text.split("\n") if l.strip())

    user = load_user(update.effective_chat.id)
    cat = key if key in CATEGORIES else "general"
    post = add_user_post(user, text, category=cat)

    post_url = make_post_url(text)

    await update.message.reply_text(
        f"✅ <b>Post created!</b>\n\n{escape_html(text)}\n\n{char_bar(len(text))}\n"
        f"🆔 <code>{post['id']}</code> | Queue: {len(get_user_unposted(user))}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Post to X Now ↗", url=post_url)],
            [InlineKeyboardButton("✅ Posted!", callback_data=f"posted:{post['id']}")],
        ]),
    )

    for k in ("tmpl_key", "tmpl_fields", "tmpl_idx"):
        context.user_data.pop(k, None)
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
# DRAFTS
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        text = " ".join(context.args)
        user = load_user(update.effective_chat.id)
        draft = {"id": uuid.uuid4().hex[:8], "text": text, "created": datetime.utcnow().isoformat()}
        user.setdefault("drafts", []).append(draft)
        save_user(user)
        await update.message.reply_text(f"📝 Draft saved! (<code>{draft['id']}</code>)\n/drafts to view.", parse_mode="HTML")
        return ConversationHandler.END

    await update.message.reply_text("📝 Send your unfinished idea.\n/cancel to abort.")
    return ADDING_DRAFT


async def receive_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = load_user(update.effective_chat.id)
    draft = {"id": uuid.uuid4().hex[:8], "text": text, "created": datetime.utcnow().isoformat()}
    user.setdefault("drafts", []).append(draft)
    save_user(user)
    await update.message.reply_text(f"📝 Saved! (<code>{draft['id']}</code>)\nSend another or /done.", parse_mode="HTML")
    return ADDING_DRAFT


@require_setup
async def cmd_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    drafts = user.get("drafts", [])
    if not drafts:
        await update.message.reply_text("No drafts. Use /draft or ✏️ Draft button.")
        return
    msg = f"📝 <b>Drafts ({len(drafts)})</b>\n{'━'*30}\n\n"
    for d in drafts[:10]:
        msg += f"<code>{d['id']}</code>: {escape_html(d['text'][:50])}...\n\n"
    msg += "Promote: <code>/promote ID</code>\nDelete: <code>/deletedraft ID</code>"
    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: <code>/promote DRAFT_ID</code>", parse_mode="HTML")
        return
    did = context.args[0]
    user = load_user(update.effective_chat.id)
    draft = next((d for d in user.get("drafts", []) if d["id"] == did), None)
    if not draft:
        await update.message.reply_text("❌ Not found.")
        return
    post = add_user_post(user, draft["text"], category="general")
    user["drafts"] = [d for d in user["drafts"] if d["id"] != did]
    save_user(user)
    await update.message.reply_text(f"✅ Promoted! (<code>{post['id']}</code>)", parse_mode="HTML")


@require_setup
async def cmd_deletedraft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: <code>/deletedraft ID</code>", parse_mode="HTML")
        return
    did = context.args[0]
    user = load_user(update.effective_chat.id)
    orig = len(user.get("drafts", []))
    user["drafts"] = [d for d in user.get("drafts", []) if d["id"] != did]
    if len(user["drafts"]) < orig:
        save_user(user)
        await update.message.reply_text("🗑️ Deleted.")
    else:
        await update.message.reply_text("❌ Not found.")


# ════════════════════════════════════════════════════════════
# NEXT POST — One-Tap Posting
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    today = get_user_today_count(user)

    if today >= 10:
        await update.message.reply_text(f"🛑 Posted {today} times today. Rest! 💪", reply_markup=get_main_keyboard())
        return

    post = pick_user_smart_post(user)
    if not post:
        await update.message.reply_text("📭 Queue empty! Add posts first.", reply_markup=get_main_keyboard())
        return

    context.user_data["last_post_id"] = post["id"]
    cat = get_cat_info(post.get("category", "general"))

    if post["type"] == "thread":
        tweets = post.get("tweets", [])
        await update.message.reply_text(
            f"🧵 <b>Thread ({len(tweets)} tweets)</b> {cat['emoji']}\n"
            f"Post first tweet, then reply with each next one.\n{'━'*30}",
            parse_mode="HTML",
        )
        for i, t in enumerate(tweets, 1):
            url = make_post_url(t)
            await update.message.reply_text(
                f"━━ Tweet {i}/{len(tweets)} ━━\n\n{t}\n\n{char_bar(len(t))}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"📝 Post Tweet {i} ↗", url=url)
                ]]),
            )
        post_url = make_post_url(tweets[0])
    else:
        text = post.get("text", "")
        await update.message.reply_text(f"{cat['emoji']} <b>{cat['label']}</b>\n{'━'*30}", parse_mode="HTML")
        await update.message.reply_text(text)

        if "#" not in text:
            h = suggest_hashtags(text)
            if h:
                text_with_tags = text + "\n\n" + h
                await update.message.reply_text(f"💡 Adding hashtags: <code>{h}</code>", parse_mode="HTML")
                post_url = make_post_url(text_with_tags)
            else:
                post_url = make_post_url(text)
        else:
            post_url = make_post_url(text)

    remaining = len(get_user_unposted(user))
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Post to X ↗", url=post_url)],
        [InlineKeyboardButton("✅ Done! I Posted It", callback_data=f"posted:{post['id']}")],
        [
            InlineKeyboardButton("⏭️ Another", callback_data="another"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{post['id']}"),
        ],
    ])

    await update.message.reply_text(
        f"{'━'*30}\n"
        f"🆔 <code>{post['id']}</code> | Today: {today}/7 | Queue: {remaining}\n\n"
        f"👆 Tap <b>'Post to X'</b> — text is pre-filled!\n"
        f"Hit Post on X, then tap <b>'Done'</b> here.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ════════════════════════════════════════════════════════════
# QUEUE, FILTER, CALENDAR
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    unposted = get_user_unposted(user)
    if not unposted:
        await update.message.reply_text("📭 Empty. Tap '📝 Add Post'.", reply_markup=get_main_keyboard())
        return

    msg = f"📋 <b>Queue ({len(unposted)})</b>\n{'━'*30}\n\n"
    for i, p in enumerate(unposted[:15], 1):
        ci = get_cat_info(p.get("category", "general"))
        preview = (p.get("text", "") or p.get("tweets", [""])[0])[:40]
        t = "🧵" if p["type"] == "thread" else ""
        msg += f"{i}. {ci['emoji']}{t} <code>{p['id']}</code> {escape_html(preview)}...\n"
    if len(unposted) > 15:
        msg += f"\n<i>+{len(unposted)-15} more</i>"

    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    posts = user.get("posts", [])
    posted = set(user.get("posted_ids", []))
    if not posts:
        await update.message.reply_text("No posts yet.")
        return

    msg = f"📚 <b>All ({len(posts)})</b>\n{'━'*30}\n\n"
    for p in posts[-20:]:
        s = "✅" if p["id"] in posted else "📋"
        ci = get_cat_info(p.get("category", "general"))
        preview = (p.get("text", "") or p.get("tweets", [""])[0])[:35]
        msg += f"{s}{ci['emoji']} <code>{p['id']}</code> {escape_html(preview)}...\n"

    n = len(posted)
    msg += f"\n{'━'*30}\n✅ {n} posted | 📋 {len(posts)-n} remaining"
    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    unposted = get_user_unposted(user)

    if not context.args:
        cats = Counter(p.get("category", "general") for p in unposted)
        msg = "🔍 <b>Filter:</b>\n\n"
        for c, count in cats.most_common():
            ci = get_cat_info(c)
            msg += f"  {ci['emoji']} /filter {c} — {count}\n"
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    cat = context.args[0].lower()
    filtered = [p for p in unposted if p.get("category") == cat]
    if not filtered:
        await update.message.reply_text(f"No posts in '{cat}'.")
        return

    ci = get_cat_info(cat)
    msg = f"{ci['emoji']} <b>{ci['label']} ({len(filtered)})</b>\n{'━'*30}\n\n"
    for p in filtered[:10]:
        preview = (p.get("text", "") or p.get("tweets", [""])[0])[:50]
        msg += f"<code>{p['id']}</code> {escape_html(preview)}...\n\n"
    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    tz = get_user_tz(user)
    unposted = get_user_unposted(user)
    today = datetime.now(tz)
    ppd = 4

    msg = f"📅 <b>Content Calendar</b>\n{'━'*30}\n\n"
    for d in range(7):
        date = today + timedelta(days=d)
        label = "📌 " if d == 0 else ""
        day_posts = unposted[d*ppd:(d+1)*ppd]
        cats = " ".join(get_cat_info(p.get("category", "general"))["emoji"] for p in day_posts)
        msg += f"{label}<b>{date.strftime('%A %b %d')}</b>\n"
        msg += f"   {cats} ({len(day_posts)} posts)\n\n" if day_posts else "   ⚠️ No content\n\n"

    total_days = len(unposted) // max(ppd, 1)
    msg += f"{'━'*30}\n📊 {len(unposted)} posts ≈ {total_days} days"
    if total_days < 3:
        msg += "\n⚠️ Running low!"
    await update.message.reply_text(msg, parse_mode="HTML")


# ════════════════════════════════════════════════════════════
# STATS & ANALYTICS
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    tz = get_user_tz(user)
    stats = user.get("stats", {})
    streak = get_user_streak(user)
    unposted = get_user_unposted(user)
    today = get_user_today_count(user)
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    msg = (
        f"📊 <b>Stats — {escape_html(user.get('name', ''))}</b>\n"
        f"{'━'*30}\n🕐 {now}\n\n"
        f"🔥 Streak: {streak['current']}d (best: {streak['best']})\n"
        f"📝 Total: {len(user.get('posts', []))} | Posted: {stats.get('total_posted', 0)} | Queue: {len(unposted)}\n"
        f"📆 Today: {today} | Drafts: {len(user.get('drafts', []))}\n\n"
    )

    cc = stats.get("category_counts", {})
    if cc:
        msg += "<b>Categories:</b>\n"
        for c, n in sorted(cc.items(), key=lambda x: -x[1]):
            ci = get_cat_info(c)
            msg += f"  {ci['emoji']} {ci['label']}: {n}\n"
        msg += "\n"

    daily = stats.get("daily_counts", {})
    if daily:
        recent = sorted(daily.items())[-7:]
        msg += "<b>Last 7 days:</b>\n"
        for day, count in recent:
            bar = "█" * count + "░" * (7 - count)
            short = datetime.strptime(day, "%Y-%m-%d").strftime("%a")
            msg += f"  {short}: {bar} {count}\n"

    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    streak = get_user_streak(user)
    today = get_user_today_count(user)
    flames = "🔥" * min(streak["current"], 30) or "💤"
    trophy = " 🏆" if streak["current"] >= streak["best"] and streak["current"] > 0 else ""

    milestones = {0: "Start today!", 1: "Day 1! 🌱", 3: "3 days! 💪", 7: "One week! 🔥",
                  14: "Two weeks! ⚡", 30: "ONE MONTH! 🏆", 100: "💎 LEGENDARY!"}
    m = milestones.get(0)
    for t, msg in sorted(milestones.items()):
        if streak["current"] >= t:
            m = msg

    warn = "\n⚠️ <b>Post today to keep streak!</b>" if today == 0 else "\n✅ Streak safe!"

    await update.message.reply_text(
        f"🔥 <b>Streak</b>\n{'━'*30}\n\n"
        f"Current: <b>{streak['current']}d</b>{trophy}\nBest: <b>{streak['best']}d</b>\n\n"
        f"{flames}\n\n{m}{warn}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard(),
    )


@require_setup
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    unposted = get_user_unposted(user)
    cq = Counter(p.get("category", "general") for p in unposted)
    cp = user.get("stats", {}).get("category_counts", {})
    tq = sum(cq.values())
    tp = sum(cp.values())

    msg = f"⚖️ <b>Content Balance</b>\n{'━'*30}\n\n<b>Queued:</b>\n"
    for c, n in cq.most_common():
        ci = get_cat_info(c)
        pct = n / max(tq, 1) * 100
        msg += f"  {ci['emoji']} {ci['label']}: {'█'*int(pct/5)} {n} ({pct:.0f}%)\n"

    if cp:
        msg += f"\n<b>Posted:</b>\n"
        for c, n in sorted(cp.items(), key=lambda x: -x[1]):
            ci = get_cat_info(c)
            pct = n / max(tp, 1) * 100
            msg += f"  {ci['emoji']} {ci['label']}: {'█'*int(pct/5)} {n} ({pct:.0f}%)\n"

    msg += f"\n{'━'*30}\n💡 <b>Ideal:</b> 40% tips, 25% projects, 15% questions, 10% career, 10% personal"
    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    s = get_suggestions(user)
    if not s:
        await update.message.reply_text("✅ Everything looks good!")
        return
    msg = f"💡 <b>Suggestions</b>\n{'━'*30}\n\n"
    for i, item in enumerate(s, 1):
        msg += f"{i}. {item}\n\n"
    await update.message.reply_text(msg, parse_mode="HTML")


@require_setup
async def cmd_hashtags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        topic = context.args[0].lower()
        tags = HASHTAG_SUGGESTIONS.get(topic)
        if tags:
            await update.message.reply_text(f"🏷️ <b>{topic}:</b>\n<code>{' '.join(tags)}</code>", parse_mode="HTML")
        else:
            await update.message.reply_text(f"Unknown. Available: {', '.join(HASHTAG_SUGGESTIONS.keys())}")
        return

    msg = f"🏷️ <b>Hashtags</b>\n{'━'*30}\n\n"
    for topic, tags in HASHTAG_SUGGESTIONS.items():
        msg += f"<b>{topic}:</b> <code>{' '.join(tags)}</code>\n\n"
    await update.message.reply_text(msg, parse_mode="HTML")


# ════════════════════════════════════════════════════════════
# SETTINGS & ACCOUNT
# ════════════════════════════════════════════════════════════

@require_setup
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    sched = ", ".join(user.get("schedule", []))

    await update.message.reply_text(
        f"⚙️ <b>Settings</b>\n{'━'*30}\n\n"
        f"👤 Name: {escape_html(user.get('name', '?'))}\n"
        f"🕐 Timezone: {user.get('timezone', '?')}\n"
        f"🔔 Reminders: {sched}\n"
        f"⏸️ Paused: {'Yes' if user.get('paused') else 'No'}\n\n"
        f"Change:\n/setname [name]\n/settimes 08:00, 12:00, 18:00\n/pause or /resume",
        parse_mode="HTML",
    )


@require_setup
async def cmd_setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /setname Your Name")
        return
    name = " ".join(context.args)[:50]
    user = load_user(update.effective_chat.id)
    user["name"] = name
    save_user(user)
    await update.message.reply_text(f"✅ Name: {escape_html(name)}")


@require_setup
async def cmd_settimes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: <code>/settimes 07:30, 11:00, 18:00</code>", parse_mode="HTML")
        return
    raw = " ".join(context.args)
    times = []
    for part in raw.replace(";", ",").split(","):
        t = part.strip()
        if ":" in t:
            try:
                h, m = map(int, t.split(":"))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    times.append(f"{h:02d}:{m:02d}")
            except ValueError:
                pass
    if not times:
        await update.message.reply_text("❌ No valid times.")
        return
    user = load_user(update.effective_chat.id)
    user["schedule"] = sorted(times)
    save_user(user)
    await update.message.reply_text(f"✅ Reminders: {', '.join(sorted(times))}")


@require_setup
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    user["paused"] = True
    save_user(user)
    await update.message.reply_text("⏸️ Paused. /resume to restart.", reply_markup=get_main_keyboard())


@require_setup
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    user["paused"] = False
    save_user(user)
    await update.message.reply_text("▶️ Resumed!", reply_markup=get_main_keyboard())


@require_setup
async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: <code>/edit ID new text</code>", parse_mode="HTML")
        return
    pid = context.args[0]
    new_text = " ".join(context.args[1:])
    user = load_user(update.effective_chat.id)
    if edit_user_post(user, pid, new_text):
        await update.message.reply_text(f"✅ Updated!\n{char_bar(len(new_text))}")
    else:
        await update.message.reply_text("❌ Not found.")


@require_setup
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: <code>/delete ID</code>", parse_mode="HTML")
        return
    pid = context.args[0]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Delete", callback_data=f"del:{pid}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ]])
    await update.message.reply_text(f"Delete <code>{pid}</code>?", parse_mode="HTML", reply_markup=keyboard)


@require_setup
async def cmd_posted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pid = context.args[0] if context.args else context.user_data.get("last_post_id")
    if not pid:
        await update.message.reply_text("Usage: <code>/posted ID</code> or tap ✅ after /next", parse_mode="HTML")
        return
    user = load_user(update.effective_chat.id)
    mark_user_posted(user, pid)
    streak = get_user_streak(user)
    today = get_user_today_count(user)
    ms = ""
    if streak["current"] in [7, 14, 21, 30, 60, 100]:
        ms = f"\n\n🎉 <b>{streak['current']}-DAY MILESTONE!</b>"
    await update.message.reply_text(
        f"✅ <b>Posted!</b>\n🔥 {streak['current']}d | Today: {today} | Queue: {len(get_user_unposted(user))}{ms}",
        parse_mode="HTML", reply_markup=get_main_keyboard(),
    )


@require_setup
async def cmd_clearposted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Reset", callback_data="clearhistory"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ]])
    await update.message.reply_text("⚠️ Reset posting history?", reply_markup=keyboard)


@require_setup
async def cmd_deleteaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    n = len(user.get("posts", []))
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ DELETE EVERYTHING", callback_data="confirmdeleteaccount"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
    ]])
    await update.message.reply_text(
        f"⚠️ <b>DELETE ACCOUNT?</b>\n\nThis removes:\n• {n} posts\n• All stats & streaks\n• All settings\n\n<b>Cannot be undone.</b>",
        parse_mode="HTML", reply_markup=keyboard,
    )


# ════════════════════════════════════════════════════════════
# ADMIN
# ════════════════════════════════════════════════════════════

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin = load_admin()
    if not admin.get("admin_ids"):
        set_admin(chat_id)
        await update.message.reply_text(
            "👑 <b>You are now admin!</b>\n\n/adminstats — All users\n/broadcast MSG — Message all\n/adminuser ID — Inspect user\n/addadmin ID — Add admin",
            parse_mode="HTML",
        )
        return
    if not is_admin(chat_id):
        await update.message.reply_text("🔒 Admin only.")
        return
    await update.message.reply_text(
        "👑 <b>Admin</b>\n\n/adminstats\n/broadcast MSG\n/adminuser ID\n/addadmin ID",
        parse_mode="HTML",
    )


async def cmd_adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("🔒")
        return
    reg = load_user_registry()
    users = reg.get("users", [])
    msg = f"👑 <b>Admin</b>\n{'━'*30}\n👥 {len(users)} users | {reg.get('total_signups', 0)} signups\n\n"
    for u in users[-20:]:
        cid = u.get("chat_id", "?")
        name = u.get("name", "?")
        ud = load_user(cid)
        if ud:
            streak = get_user_streak(ud)
            posts = len(ud.get("posts", []))
            msg += f"👤 {escape_html(name)} (<code>{cid}</code>) — {posts}p 🔥{streak['current']}d\n"
        else:
            msg += f"👤 {escape_html(name)} (<code>{cid}</code>)\n"
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("🔒")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message")
        return
    message = " ".join(context.args)
    reg = load_user_registry()
    sent = failed = 0
    for u in reg.get("users", []):
        cid = u.get("chat_id")
        if not cid:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(cid),
                text=f"📢 <b>Announcement</b>\n{'━'*30}\n\n{escape_html(message)}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
        if sent % 20 == 0:
            _time.sleep(1)
    await update.message.reply_text(f"📢 Sent to {sent} ({failed} failed).")


async def cmd_adminuser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /adminuser CHAT_ID")
        return
    ud = load_user(context.args[0])
    if not ud:
        await update.message.reply_text("Not found.")
        return
    streak = get_user_streak(ud)
    await update.message.reply_text(
        f"👤 <b>{escape_html(ud.get('name', '?'))}</b>\n"
        f"ID: <code>{context.args[0]}</code>\nTZ: {ud.get('timezone')}\n"
        f"Posts: {len(ud.get('posts', []))} | Posted: {ud.get('stats', {}).get('total_posted', 0)}\n"
        f"Queue: {len(get_user_unposted(ud))} | Streak: {streak['current']}d\n"
        f"Paused: {ud.get('paused')} | Schedule: {', '.join(ud.get('schedule', []))}",
        parse_mode="HTML",
    )


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addadmin CHAT_ID")
        return
    set_admin(context.args[0])
    await update.message.reply_text(f"✅ Admin added: {context.args[0]}")


# ════════════════════════════════════════════════════════════
# BUTTON CALLBACKS
# ════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data.startswith("cat:"):
        cat = data[4:]
        text = context.user_data.get("pending_text", "")
        if not text:
            await query.edit_message_text("❌ Text lost. Try /add again.")
            return
        user = load_user(chat_id)
        if not user:
            return
        ci = get_cat_info(cat)
        post = add_user_post(user, text, category=cat)
        context.user_data.pop("pending_text", None)
        post_url = make_post_url(text)

        await query.edit_message_text(
            f"✅ <b>Saved!</b> {ci['emoji']} {ci['label']}\n"
            f"🆔 <code>{post['id']}</code> | {char_bar(len(text))}\n"
            f"Queue: {len(get_user_unposted(user))}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Post to X Now ↗", url=post_url)],
                [InlineKeyboardButton("✅ Posted!", callback_data=f"posted:{post['id']}")],
            ]),
        )

    elif data.startswith("posted:"):
        pid = data[7:]
        user = load_user(chat_id)
        if user:
            mark_user_posted(user, pid)
            streak = get_user_streak(user)
            today = get_user_today_count(user)
            ms = ""
            if streak["current"] in [7, 14, 21, 30, 60, 100]:
                ms = f"\n🎉 <b>{streak['current']}-DAY MILESTONE!</b>"
            await query.edit_message_text(
                f"✅ <b>Posted!</b>\n🔥 {streak['current']}d | Today: {today} | Queue: {len(get_user_unposted(user))}{ms}",
                parse_mode="HTML",
            )

    elif data == "another":
        user = load_user(chat_id)
        if not user:
            return
        post = pick_user_smart_post(user)
        if not post:
            await query.edit_message_text("📭 Queue empty!")
            return

        context.user_data["last_post_id"] = post["id"]
        cat = get_cat_info(post.get("category", "general"))

        if post["type"] == "thread":
            tweets = post.get("tweets", [])
            for i, t in enumerate(tweets, 1):
                url = make_post_url(t)
                await query.message.reply_text(
                    f"🧵 {i}/{len(tweets)}:\n\n{t}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📝 Tweet {i} ↗", url=url)]]),
                )
            post_url = make_post_url(tweets[0])
        else:
            text = post.get("text", "")
            await query.message.reply_text(text)
            post_url = make_post_url(text)

        remaining = len(get_user_unposted(user))
        await query.message.reply_text(
            f"{cat['emoji']} <code>{post['id']}</code> | Queue: {remaining}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Post to X ↗", url=post_url)],
                [InlineKeyboardButton("✅ Done!", callback_data=f"posted:{post['id']}")],
                [InlineKeyboardButton("⏭️ Another", callback_data="another")],
            ]),
        )

    elif data.startswith("skip:"):
        pid = data[5:]
        user = load_user(chat_id)
        if user:
            mark_user_posted(user, pid)
            await query.edit_message_text(f"⏭️ Skipped. /next for another.")

    elif data.startswith("del:"):
        pid = data[4:]
        user = load_user(chat_id)
        if user and delete_user_post(user, pid):
            await query.edit_message_text(f"🗑️ Deleted {pid}")
        else:
            await query.edit_message_text("❌ Not found.")

    elif data == "clearhistory":
        user = load_user(chat_id)
        if user:
            user["posted_ids"] = []
            for p in user["posts"]:
                p["posted"] = False
                p.pop("posted_date", None)
            user["stats"]["daily_counts"] = {}
            user["stats"]["total_posted"] = 0
            user["stats"]["streak_current"] = 0
            save_user(user)
            await query.edit_message_text(f"🔄 Reset! {len(get_user_unposted(user))} posts available.")

    elif data == "confirmdeleteaccount":
        if delete_user_data(chat_id):
            await query.edit_message_text(
                "🗑️ <b>Account deleted.</b>\n\nAll data removed.\n/start to create a new account.",
                parse_mode="HTML",
            )

    elif data.startswith("tmpl:"):
        key = data[5:]
        tmpl = TEMPLATES.get(key)
        if not tmpl:
            await query.edit_message_text("❌ Not found.")
            return
        context.user_data["tmpl_key"] = key
        context.user_data["tmpl_fields"] = {}
        context.user_data["tmpl_idx"] = 0
        await query.edit_message_text(
            f"📋 <b>{tmpl['name']}</b>\n\nAnswer each question. 'skip' to leave empty.\n\n<b>Q1:</b> {tmpl['prompts'][0]}",
            parse_mode="HTML",
        )
        # Note: template filling is handled by the ConversationHandler

    elif data == "quick_save":
        text = context.user_data.get("pending_text", "")
        if text:
            await query.edit_message_text("📝 Choose category:", reply_markup=get_cat_keyboard())
        else:
            await query.edit_message_text("❌ Text lost. /add again.")

    elif data == "quick_draft":
        text = context.user_data.get("pending_text", "")
        if text:
            user = load_user(chat_id)
            if user:
                draft = {"id": uuid.uuid4().hex[:8], "text": text, "created": datetime.utcnow().isoformat()}
                user.setdefault("drafts", []).append(draft)
                save_user(user)
                context.user_data.pop("pending_text", None)
                await query.edit_message_text(f"📋 Draft saved! (<code>{draft['id']}</code>)", parse_mode="HTML")
        else:
            await query.edit_message_text("❌ Text lost.")

    elif data == "cancel":
        context.user_data.pop("pending_text", None)
        await query.edit_message_text("👍 Cancelled.")


# ════════════════════════════════════════════════════════════
# TEXT HANDLER — Buttons + Plain Text
# ════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = load_user(chat_id)

    if not user or not user.get("setup_complete"):
        await update.message.reply_text("👋 Send /start to set up!")
        return

    text = update.message.text.strip()

    # Handle persistent keyboard buttons
    button_map = {
        "📝 Add Post": cmd_add,
        "📤 Next Post": cmd_next,
        "📊 Stats": cmd_stats,
        "📋 Queue": cmd_queue,
        "🔥 Streak": cmd_streak,
        "📋 Template": cmd_template,
        "📦 Bulk Add": cmd_bulk,
        "✏️ Draft": cmd_draft,
        "⚙️ Settings": cmd_settings,
    }

    handler = button_map.get(text)
    if handler:
        await handler(update, context)
        return

    # Short text — just help
    if len(text) < 10:
        await update.message.reply_text("💡 Tap a button below or use / menu.", reply_markup=get_main_keyboard())
        return

    # Long text — offer to save
    context.user_data["pending_text"] = text
    post_url = make_post_url(text)
    bar = char_bar(len(text))
    h = suggest_hashtags(text)

    msg = f"💬 {len(text)} chars\n{bar}"
    if h:
        msg += f"\n💡 <code>{h}</code>"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Save as Post", callback_data="quick_save"),
            InlineKeyboardButton("📋 Draft", callback_data="quick_draft"),
        ],
        [InlineKeyboardButton("📝 Post to X Right Now ↗", url=post_url)],
        [InlineKeyboardButton("❌ Ignore", callback_data="cancel")],
    ])

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)


# ════════════════════════════════════════════════════════════
# SCHEDULED REMINDERS
# ════════════════════════════════════════════════════════════

async def global_reminder_check(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 60 seconds. Checks all users for reminder times."""
    registry = load_user_registry()

    for u_info in registry.get("users", []):
        cid = u_info.get("chat_id")
        if not cid:
            continue

        user = load_user(cid)
        if not user or not user.get("setup_complete") or user.get("paused"):
            continue

        tz = get_user_tz(user)
        now = datetime.now(tz)
        current_time = now.strftime("%H:%M")

        if current_time not in user.get("schedule", []):
            continue

        reminder_key = f"{now.strftime('%Y-%m-%d')}_{current_time}"
        if user.get("_last_reminder") == reminder_key:
            continue

        user["_last_reminder"] = reminder_key
        save_user(user)

        today_count = get_user_today_count(user)
        if today_count >= 10:
            continue

        post = pick_user_smart_post(user)
        if not post:
            continue

        try:
            cat = get_cat_info(post.get("category", "general"))
            streak = get_user_streak(user)
            s = f"🔥 {streak['current']}d" if streak["current"] > 0 else "💪 Start streak"

            await context.bot.send_message(
                chat_id=int(cid),
                text=(
                    f"🔔 <b>Time to post!</b> ({current_time})\n"
                    f"{s} | Today: {today_count}\n{'━'*30}\n"
                    f"{cat['emoji']} {cat['label']}\n\n📋 Copy or tap Post to X:"
                ),
                parse_mode="HTML",
            )

            if post["type"] == "thread":
                tweets = post.get("tweets", [])
                for i, t in enumerate(tweets, 1):
                    url = make_post_url(t)
                    await context.bot.send_message(
                        chat_id=int(cid),
                        text=f"🧵 {i}/{len(tweets)}:\n\n{t}\n\n{char_bar(len(t))}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"📝 Tweet {i} ↗", url=url)]]),
                    )
                tweet_text = tweets[0]
            else:
                tweet_text = post.get("text", "")
                await context.bot.send_message(chat_id=int(cid), text=tweet_text)

            if "#" not in tweet_text:
                h = suggest_hashtags(tweet_text)
                if h:
                    tweet_text = tweet_text + "\n\n" + h
                    await context.bot.send_message(chat_id=int(cid), text=f"💡 <code>{h}</code>", parse_mode="HTML")

            post_url = make_post_url(tweet_text)
            remaining = len(get_user_unposted(user))

            await context.bot.send_message(
                chat_id=int(cid),
                text=(
                    f"{'━'*30}\n🆔 <code>{post['id']}</code> | Queue: {remaining}\n\n"
                    f"👆 Tap <b>'Post to X'</b> — text ready!\nThen tap <b>'Done'</b>."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Post to X ↗", url=post_url)],
                    [InlineKeyboardButton("✅ Done!", callback_data=f"posted:{post['id']}")],
                    [InlineKeyboardButton("⏭️ Another", callback_data="another")],
                ]),
            )

            logger.info(f"Reminder → {cid} at {current_time}")

        except Exception as e:
            logger.warning(f"Reminder failed {cid}: {e}")


async def weekly_report_check(context: ContextTypes.DEFAULT_TYPE):
    """Runs every 60s. Sends weekly report Sunday 20:00."""
    registry = load_user_registry()
    for u_info in registry.get("users", []):
        cid = u_info.get("chat_id")
        if not cid:
            continue
        user = load_user(cid)
        if not user or not user.get("setup_complete"):
            continue

        tz = get_user_tz(user)
        now = datetime.now(tz)
        if now.weekday() != 6 or now.strftime("%H:%M") != "20:00":
            continue

        rkey = f"weekly_{now.strftime('%Y-%m-%d')}"
        if user.get("_last_weekly") == rkey:
            continue
        user["_last_weekly"] = rkey
        save_user(user)

        stats = user.get("stats", {})
        streak = get_user_streak(user)
        daily = stats.get("daily_counts", {})

        total = 0
        chart = ""
        for i in range(6, -1, -1):
            d = now - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            count = daily.get(ds, 0)
            total += count
            chart += f"  {d.strftime('%a')}: {'█'*count}{'░'*(7-count)} {count}\n"

        try:
            await context.bot.send_message(
                chat_id=int(cid),
                text=(
                    f"📊 <b>Weekly Report</b>\n{'━'*30}\n\n"
                    f"🔥 Streak: {streak['current']}d (best: {streak['best']})\n"
                    f"📝 This week: {total}\n"
                    f"📋 Queue: {len(get_user_unposted(user))}\n\n"
                    f"<b>Daily:</b>\n{chart}\nKeep going! 💪"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Weekly report failed {cid}: {e}")


# ════════════════════════════════════════════════════════════
# FLASK HEALTH
# ════════════════════════════════════════════════════════════

flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    reg = load_user_registry()
    return jsonify({
        "status": "running",
        "bot": "X Smart Content Bot v3",
        "users": len(reg.get("users", [])),
    })


@flask_app.route("/health")
def health():
    return "OK", 200


def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


# ════════════════════════════════════════════════════════════
# CANCEL & DONE
# ════════════════════════════════════════════════════════════

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=get_main_keyboard())
    return ConversationHandler.END


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = load_user(update.effective_chat.id)
    q = len(get_user_unposted(user)) if user else 0
    await update.message.reply_text(f"👍 {q} posts in queue.", reply_markup=get_main_keyboard())
    return ConversationHandler.END


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main():
    global BOT_TOKEN
    BOT_TOKEN = get_bot_token()

    print("=" * 50)
    print("  X Smart Bot v3 — Multi-User Edition")
    print("=" * 50)
    print(f"  Token: ...{BOT_TOKEN[-8:]}")
    print(f"  Port:  {PORT}")
    reg = load_user_registry()
    print(f"  Users: {len(reg.get('users', []))}")
    print("=" * 50)

    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # Post-init: set bot commands menu
    async def post_init(application):
        cmds = [
            ("add", "📝 Add a new post"),
            ("thread", "🧵 Create a thread"),
            ("bulk", "📦 Add many posts at once"),
            ("template", "📋 Use a post template"),
            ("next", "📤 Get next post to publish"),
            ("queue", "📋 See your queue"),
            ("calendar", "📅 Weekly plan"),
            ("stats", "📊 Statistics"),
            ("streak", "🔥 Posting streak"),
            ("balance", "⚖️ Content analysis"),
            ("suggest", "💡 Suggestions"),
            ("draft", "✏️ Save a draft"),
            ("drafts", "📝 View drafts"),
            ("hashtags", "🏷️ Hashtag ideas"),
            ("settings", "⚙️ Settings"),
            ("help", "❓ All commands"),
        ]
        await application.bot.set_my_commands([BotCommand(c, d) for c, d in cmds])
        try:
            await application.bot.set_my_description(
                "🤖 X Smart Bot — Manage X posts from Telegram.\n"
                "✅ One-tap posting\n✅ Streaks & analytics\n✅ No API keys needed\n\nTap Start!"
            )
            await application.bot.set_my_short_description(
                "Manage your X/Twitter posts from Telegram. One-tap posting. 🚀"
            )
        except Exception:
            pass
        logger.info("Bot commands set.")

    app.post_init = post_init

    # Conversations
    setup_conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            SETUP_NAME: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, setup_name)],
            SETUP_TIMEZONE: [CallbackQueryHandler(setup_tz_selected, pattern="^tz:")],
            SETUP_CUSTOM_TIMEZONE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, setup_custom_tz)],
            SETUP_SCHEDULE: [CallbackQueryHandler(setup_sched_selected, pattern="^sched:")],
            SETUP_CUSTOM_SCHEDULE: [CommandHandler("cancel", cancel), MessageHandler(filters.TEXT & ~filters.COMMAND, setup_custom_sched)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", cmd_add)],
        states={ADDING_SINGLE: [
            CommandHandler("done", done), CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_single),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    thread_conv = ConversationHandler(
        entry_points=[CommandHandler("thread", cmd_thread)],
        states={ADDING_THREAD_TWEETS: [
            CommandHandler("save", save_thread), CommandHandler("preview", preview_thread),
            CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_thread_tweet),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    bulk_conv = ConversationHandler(
        entry_points=[CommandHandler("bulk", cmd_bulk)],
        states={ADDING_BULK: [
            CommandHandler("done", done), CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bulk),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    template_conv = ConversationHandler(
        entry_points=[CommandHandler("template", cmd_template)],
        states={TEMPLATE_FILLING: [
            CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_template_field),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    draft_conv = ConversationHandler(
        entry_points=[CommandHandler("draft", cmd_draft)],
        states={ADDING_DRAFT: [
            CommandHandler("done", done), CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_draft),
        ]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
    )

    app.add_handler(setup_conv)
    app.add_handler(add_conv)
    app.add_handler(thread_conv)
    app.add_handler(bulk_conv)
    app.add_handler(template_conv)
    app.add_handler(draft_conv)

    for cmd, func in {
        "help": cmd_start, "next": cmd_next, "queue": cmd_queue, "all": cmd_all,
        "filter": cmd_filter, "calendar": cmd_calendar, "stats": cmd_stats,
        "streak": cmd_streak, "balance": cmd_balance, "suggest": cmd_suggest,
        "hashtags": cmd_hashtags, "settings": cmd_settings, "setname": cmd_setname,
        "settimes": cmd_settimes, "pause": cmd_pause, "resume": cmd_resume,
        "posted": cmd_posted, "edit": cmd_edit, "delete": cmd_delete,
        "clearposted": cmd_clearposted, "deleteaccount": cmd_deleteaccount,
        "drafts": cmd_drafts, "promote": cmd_promote, "deletedraft": cmd_deletedraft,
        "admin": cmd_admin, "adminstats": cmd_adminstats, "broadcast": cmd_broadcast,
        "adminuser": cmd_adminuser, "addadmin": cmd_addadmin,
    }.items():
        app.add_handler(CommandHandler(cmd, func))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Scheduled jobs
    job_queue = app.job_queue
    job_queue.run_repeating(global_reminder_check, interval=60, first=10)
    job_queue.run_repeating(weekly_report_check, interval=60, first=30)

    print("\n  ✅ Bot running!")
    print("  📱 Open Telegram → find your bot → /start")
    print("  👑 First /admin becomes admin\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    import asyncio

    # Python 3.14+ removed auto-creation of event loops
    # This ensures one exists before the bot starts
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    main()

