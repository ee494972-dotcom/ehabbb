#!/usr/bin/env python3
"""Connect Four Telegram bot.

Private chat: play the computer. Groups: rated challenges between two players.
Channels: one posted board where every reader opens a private game.
"""
import os
import time

import cards
import engine
import storage
import telegram_api as tg

TOKEN = os.environ.get("CONNECT4_TOKEN", "")
OWNER_ID = int(os.environ.get("CONNECT4_OWNER_ID", "8555191642"))
ELO_K = 32
DAY = 24 * 60 * 60
MAX_VIEWERS = 12
PLAY_WORDS = {"connect4", "connect four", "Connect4", "Connect Four",
              "اربعة", "أربعة", "اربعه", "أربعه", "اربعة في صف", "أربعة في صف"}
GROUP_TYPES = ("group", "supergroup")
# Ephemeral commands stay hidden from the rest of a group, and the bot may answer
# them ephemerally within 15 seconds without being a group administrator.
COMMANDS = [
    {"command": "play", "description": "Start a Connect Four game", "is_ephemeral": True},
    {"command": "cpu", "description": "Play the computer", "is_ephemeral": True},
    {"command": "top", "description": "Leaderboard", "is_ephemeral": True},
    {"command": "me", "description": "Your rating and rank", "is_ephemeral": True},
    {"command": "group", "description": "Add the bot to a group", "is_ephemeral": True},
    {"command": "channel", "description": "Post a board in your channel"},
    {"command": "help", "description": "How to play", "is_ephemeral": True},
]
HELP = (
    "🔴🟡 Connect Four\n\n"
    "Take turns dropping a disc into a column – it falls to the lowest free space. "
    "The first to connect 4 of their colour in a row (across, down or diagonally) wins.\n\n"
    "• /play in private: play the computer\n"
    "• /play in a group: open a challenge anyone can accept. Reply to someone's message to challenge only them\n"
    "• /cpu in a group: play the computer\n"
    "• /top: leaderboard\n"
    "• /me: your rating and rank\n"
    "• /group: add the bot to a group\n"
    "• /channel: post a board in your channel\n\n"
    f"In challenges each player has {cards.TURN_SECONDS} seconds per move – run out of time and you lose."
)

state = storage.load()
me = {"id": None, "username": ""}


def save():
    storage.save(state)


def game_key(chat, game_id):
    return f"{chat}:{game_id}"


def display_name(user):
    name = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part)
    return name.strip() or user.get("username") or "Player"


def player(uid):
    return state["players"].setdefault(str(uid), {
        "name": "Player", "rating": cards.START_RATING, "wins": 0, "losses": 0, "draws": 0})


def remember(user, chat_id=None):
    player(user["id"])["name"] = display_name(user)
    if chat_id is not None:
        members = state["chat_players"].setdefault(str(chat_id), [])
        if str(user["id"]) not in members:
            members.append(str(user["id"]))


# ---------------------------------------------------------------- game state

def reset_board(game):
    game.update(board=engine.new_board(), turn=engine.RED, history=[], last=None,
                win_line=None, winner=None, reason=None, phase="play", turn_started=time.time())
    game.pop("rating_change", None)


def create_game(chat_id, mode, owner_id, **fields):
    state["next_game"] += 1
    game = {"chat": str(chat_id), "id": str(state["next_game"]), "mode": mode,
            "owner": str(owner_id), "updated": time.time()}
    reset_board(game)
    game.update(fields)
    state["games"][game_key(game["chat"], game["id"])] = game
    return game


def create_cpu_game(chat_id, user):
    remember(user)
    return create_game(chat_id, "cpu", user["id"], level="normal",
                       players={engine.RED: str(user["id"]), engine.YELLOW: "cpu"},
                       names={engine.RED: display_name(user), engine.YELLOW: cards.COMPUTER_NAME})


def play_column(game, col):
    """Drop the side-to-move's disc. Returns False when the column is full."""
    dropped = engine.drop(game["board"], col, game["turn"])
    if not dropped:
        return False
    game["board"], row = dropped
    game["history"].append(col)
    game["last"] = engine.idx(row, col)
    line = engine.winning_line(game["board"], game["last"])
    if line:
        finish(game, game["turn"], line=line)
    elif engine.is_full(game["board"]):
        finish(game, None)
    else:
        game["turn"] = engine.other(game["turn"])
        game["turn_started"] = time.time()
    return True


def finish(game, winner, line=None, reason=None):
    game.update(phase="over", winner=winner, win_line=list(line) if line else None, reason=reason)
    if game["mode"] == "pvp":
        game["rating_change"] = settle_ratings(game)


def settle_ratings(game):
    """Apply an Elo update to both players and return red's rating change."""
    red = player(game["players"][engine.RED])
    yellow = player(game["players"][engine.YELLOW])
    expected = 1 / (1 + 10 ** ((yellow["rating"] - red["rating"]) / 400))
    score = {engine.RED: 1.0, engine.YELLOW: 0.0}.get(game["winner"], 0.5)
    change = round(ELO_K * (score - expected))
    red["rating"] += change
    yellow["rating"] -= change
    if game["winner"] is None:
        red["draws"] += 1
        yellow["draws"] += 1
    else:
        winner, loser = (red, yellow) if game["winner"] == engine.RED else (yellow, red)
        winner["wins"] += 1
        loser["losses"] += 1
    return change


def computer_reply(game):
    col = engine.best_move(game["board"], game["turn"], game.get("level", "normal"))
    if col is not None:
        play_column(game, col)


def undo(game):
    """Take back the player's last move and the computer's answer."""
    moves = game["history"][:-2]
    reset_board(game)
    for col in moves:
        play_column(game, col)


def parse_column(value):
    try:
        col = int(value)
    except (TypeError, ValueError):
        return None
    return col if 0 <= col < engine.COLS else None


# ------------------------------------------------------------------ messages

def render(game, premium=False):
    return cards.render(game, state["players"], premium)


def is_private(chat_id):
    # Custom emoji show in regular messages only in private chats (positive ids);
    # in groups and channels they show only in ephemeral views.
    return int(chat_id) > 0


def post(game):
    sent = tg.rich_send(game["chat"], render(game, is_private(game["chat"])))
    game["message_id"] = ((sent or {}).get("result") or {}).get("message_id")
    save()


def refresh(game, chat_id=None, message_id=None, user_id=None):
    """Edit the card everywhere it is shown."""
    game["updated"] = time.time()
    if game["mode"] == "pvp":
        # One public card for the group plus each viewer's ephemeral premium board.
        if game.get("message_id"):
            tg.rich_edit(game["chat"], game["message_id"], render(game))
        for viewer, ephemeral_id in game.get("views", {}).items():
            tg.rich_ephemeral_edit(game["chat"], int(viewer), ephemeral_id, render(game, True))
        return
    ephemeral_id = game.get("ephemeral_message_id")
    if ephemeral_id and user_id:
        tg.rich_ephemeral_edit(chat_id or game["chat"], user_id, ephemeral_id, render(game, True))
        return
    if message_id:
        target = chat_id or game["chat"]
    elif game.get("message_id"):
        target, message_id = game["chat"], game["message_id"]
    else:
        return
    tg.rich_edit(target, message_id, render(game, is_private(target)))


def start_challenge(chat_id, creator, invited=None):
    remember(creator, chat_id)
    fields = {"phase": "waiting",
              "players": {engine.RED: str(creator["id"]), engine.YELLOW: None},
              "names": {engine.RED: display_name(creator), engine.YELLOW: None}}
    if invited:
        fields["invited"], fields["invited_name"] = invited
    post(create_game(chat_id, "pvp", creator["id"], **fields))


def start_cpu(chat_id, user):
    post(create_cpu_game(chat_id, user))


def start_lobby(chat_id, owner_id):
    post(create_game(chat_id, "lobby", owner_id, phase="lobby"))


def ordinal(position):
    return ("🥇", "🥈", "🥉")[position] if position < 3 else f"{position + 1}."


def leaderboard(chat_id, chat_type):
    if chat_type in GROUP_TYPES:
        ids, title = state["chat_players"].get(str(chat_id), []), "🏆 Group leaderboard"
    else:
        ids, title = list(state["players"]), "🏆 Top players"
    rows = [state["players"][uid] for uid in ids if uid in state["players"]]
    rows = [p for p in rows if p["wins"] + p["losses"] + p["draws"]]
    if not rows:
        return f"{title}\n\nNo challenges played yet. Start one with /play in any group."
    rows.sort(key=lambda p: p["rating"], reverse=True)
    lines = [f"{ordinal(n)} {p['name']} – {p['rating']} ({p['wins']}W · {p['losses']}L · {p['draws']}D)"
             for n, p in enumerate(rows[:10])]
    return title + "\n\n" + "\n".join(lines)


def my_stats(user):
    remember(user)
    stats = player(user["id"])
    ranked = sorted(state["players"].values(), key=lambda p: p["rating"], reverse=True)
    position = next(n for n, p in enumerate(ranked, 1) if p is stats)
    return (f"👤 {stats['name']}\n"
            f"Rating: {stats['rating']} · {cards.rank_title(stats['rating'])}\n"
            f"Wins: {stats['wins']} · Losses: {stats['losses']} · Draws: {stats['draws']}\n"
            f"Rank: #{position} of {len(ranked)}")


# ------------------------------------------------------ subscription + admin

def subscribed(user_id):
    channel = state.get("channel")
    if not channel:
        return True
    result = tg.api("getChatMember", {"chat_id": "@" + channel, "user_id": user_id})
    member = result and result.get("result")
    if not member or member.get("status") in ("left", "kicked"):
        return False
    return not (member.get("status") == "restricted" and member.get("is_member") is False)


def reply_to(msg, private=False):
    """Reply options for msg. In a group the reply is ephemeral (only the sender sees it)
    when private is set or when msg itself is an ephemeral command."""
    reply = {}
    if msg.get("ephemeral_message_id"):
        reply["ephemeral_message_id"] = msg["ephemeral_message_id"]
    elif msg.get("message_id"):
        reply["message_id"] = msg["message_id"]
    sender = (msg.get("from") or {}).get("id")
    in_group = (msg.get("chat") or {}).get("type") in GROUP_TYPES
    if in_group and sender and (private or msg.get("ephemeral_message_id")):
        reply["receiver_user_id"] = sender
    return reply


def gate(msg):
    chat_id = msg["chat"]["id"]
    rich = {"blocks": [
        {"type": "paragraph", "text": "≋ عليك الاشتراك في قناة البوت لاستخدام الأوامر"},
        {"type": "buttons", "buttons": [{"text": "الاشتراك في القناة", "url": "https://t.me/" + state["channel"]}]},
    ]}
    reply = reply_to(msg, private=True)
    if tg.rich_send(chat_id, rich, reply=reply) or "receiver_user_id" not in reply:
        return
    # Telegram refused the ephemeral reply (the bot is not an admin and the command was
    # typed as a regular message), so answer with a normal reply instead.
    tg.rich_send(chat_id, rich, reply={"message_id": msg.get("message_id")})


def admin_message(chat_id, uid, text):
    if uid != OWNER_ID:
        return False
    pending = state["pending"]
    if text in ("اضف اشتراك", "اضف قناة الاشتراك", "تعيين قناة الاشتراك"):
        pending[str(uid)] = True
        save()
        tg.text_send(chat_id, "• ابعت يوزرنيم قناة الاشتراك مثل: @channel")
        return True
    if text in ("حذف الاشتراك", "تعطيل الاشتراك"):
        state["channel"] = state["channel_name"] = ""
        pending.pop(str(uid), None)
        save()
        tg.text_send(chat_id, "• تم تعطيل الاشتراك الإجباري")
        return True
    if text == "حالة الاشتراك":
        tg.text_send(chat_id, "• الاشتراك مفعل على: @" + state["channel"] if state["channel"]
                     else "• الاشتراك الإجباري غير مفعل")
        return True
    if not pending.get(str(uid)):
        return False
    if text in ("الغاء", "إلغاء"):
        pending.pop(str(uid), None)
        save()
        tg.text_send(chat_id, "• تم إلغاء الإعداد")
        return True
    if not text.startswith("@") or len(text) < 2:
        tg.text_send(chat_id, "• أرسل يوزرنيم قناة صحيح يبدأ بـ @")
        return True
    channel = text[1:]
    info = tg.api("getChat", {"chat_id": "@" + channel})
    member = tg.api("getChatMember", {"chat_id": "@" + channel, "user_id": me["id"]})
    if not info or info.get("result", {}).get("type") != "channel":
        tg.text_send(chat_id, "• المعرف ليس قناة عامة صحيحة")
        return True
    if (member or {}).get("result", {}).get("status") not in ("administrator", "creator"):
        tg.text_send(chat_id, "• لازم تضيف البوت أدمن في القناة أولاً")
        return True
    state["channel"], state["channel_name"] = channel, info["result"].get("title", "@" + channel)
    pending.pop(str(uid), None)
    save()
    tg.text_send(chat_id, "• تم تفعيل الاشتراك الإجباري على @" + channel)
    return True


INSPECT_WORDS = ("/inspect", "/فحص", "فحص")


def custom_emoji_found(msg):
    """Return {custom emoji id: the emoji it stands for} from text entities and rich blocks."""
    found = {}

    def walk(value):
        if isinstance(value, dict):
            if value.get("type") == "custom_emoji" and value.get("custom_emoji_id"):
                found.setdefault(str(value["custom_emoji_id"]), value.get("alternative_text") or "")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(msg)
    for text_key, entities_key in (("text", "entities"), ("caption", "caption_entities")):
        raw = (msg.get(text_key) or "").encode("utf-16-le")
        for entity in msg.get(entities_key) or []:
            if entity.get("type") == "custom_emoji" and entity.get("custom_emoji_id"):
                # Entity offsets count UTF-16 code units.
                start, end = entity["offset"] * 2, (entity["offset"] + entity["length"]) * 2
                found[str(entity["custom_emoji_id"])] = raw[start:end].decode("utf-16-le", "replace")
    return found


SET_PACK_WORDS = ("/setpack", "تعيين الايموجي", "تعيين الإيموجي")
RESET_PACK_WORDS = ("/resetpack", "حذف الايموجي", "حذف الإيموجي")
# Which card slot each emoji of the pack fills, keyed by the emoji it was uploaded with.
PACK_SLOTS = {"🔴": engine.RED, "🟡": engine.YELLOW, "⚫": engine.EMPTY,
              "🟥": engine.RED + "_win", "🟨": engine.YELLOW + "_win"}


def pack_name(text):
    """Pack short name from 't.me/addemoji/NAME', 't.me/addstickers/NAME' or a bare name."""
    word = text.strip().rstrip("/").split("/")[-1].split("?")[0]
    return word if word and all(ch.isalnum() or ch == "_" for ch in word) else ""


def fetch_pack(name):
    result = tg.api("getStickerSet", {"name": name})
    return ((result or {}).get("result") or {}).get("stickers") or []


def apply_custom_emoji():
    for slot in cards.CUSTOM_EMOJI:
        cards.CUSTOM_EMOJI[slot] = state["custom_emoji"].get(slot, "")


def set_pack(chat_id, argument):
    name = pack_name(argument)
    stickers = fetch_pack(name) if name else []
    if not stickers:
        tg.text_send(chat_id, "• ابعت لينك الباكدج بعد الأمر، مثل:\nتعيين الايموجي t.me/addemoji/اسم_الباكدج")
        return
    chosen = {}
    for sticker in stickers:
        slot = PACK_SLOTS.get((sticker.get("emoji") or "").replace("️", ""))
        if slot and sticker.get("custom_emoji_id") and slot not in chosen:
            chosen[slot] = sticker["custom_emoji_id"]
    if not chosen:
        tg.text_send(chat_id, "• مفيش ولا إيموجي في الباكدج دي متربط بـ 🔴 🟡 ⚫ 🟥 🟨")
        return
    state["custom_emoji"] = chosen
    save()
    apply_custom_emoji()
    missing = [slot for slot in cards.CUSTOM_EMOJI if slot not in chosen]
    tg.text_send(chat_id, f"• تم تعيين {len(chosen)} إيموجي من الباكدج"
                 + (f"\n• لسه عادي: {', '.join(missing)}" if missing else ""))


def reset_pack(chat_id):
    state["custom_emoji"] = {}
    save()
    apply_custom_emoji()
    tg.text_send(chat_id, "• رجعت الرقعة للإيموجي العادي")


def inspect_pack(chat_id, name):
    stickers = fetch_pack(name)
    if not stickers:
        tg.text_send(chat_id, "• مش لاقي باكدج بالاسم ده")
        return
    lines = [f"{s.get('emoji') or '•'}  {s['custom_emoji_id']}" for s in stickers if s.get("custom_emoji_id")]
    tg.text_send(chat_id, "Custom emoji IDs:\n\n" + "\n".join(lines))


def inspect_message(msg, chat_id):
    argument = (msg.get("text") or "").split(maxsplit=1)
    name = pack_name(argument[1]) if len(argument) > 1 and "/" in argument[1] else ""
    if name and not msg.get("reply_to_message"):
        inspect_pack(chat_id, name)
        return
    target = msg.get("reply_to_message") or msg
    found = custom_emoji_found(target)
    if not found:
        tg.text_send(chat_id, "مفيش إيموجي بريميوم في الرسالة دي.\n"
                              "ابعت الإيموجي نفسه، أو ابعته مع كلمة فحص، أو اعمل رد بـ فحص على رسالة فيها إيموجي.")
        return
    lines = [f"{char or '•'}  {emoji_id}" for emoji_id, char in found.items()]
    tg.text_send(chat_id, "Custom emoji IDs:\n\n" + "\n".join(lines))


# ------------------------------------------------------------- group/channel

def send_group_help(chat_id, reply=None):
    url = f"https://t.me/{me['username']}?startgroup=play"
    tg.rich_send(chat_id, {"blocks": [{"type": "paragraph", "text": [
        "Add this bot to any of your groups, then send /play.\nOr just follow this link – ",
        {"type": "url", "text": f"t.me/{me['username']}?startgroup=play", "url": url},
    ]}]}, reply=reply)


def send_channel_help(chat_id):
    picker = {"keyboard": [[{
        "text": "Choose a channel",
        "request_chat": {
            "request_id": 1,
            "chat_is_channel": True,
            "user_administrator_rights": {"can_manage_chat": True, "can_post_messages": True},
            "bot_administrator_rights": {"can_post_messages": True},
        },
    }]], "resize_keyboard": True, "one_time_keyboard": True}
    tg.rich_send(chat_id, {"blocks": [{"type": "paragraph", "text":
        "Pick a channel and I will post a board in it. Everyone reading it gets their own game "
        "against the computer, and nobody sees anyone else's moves.\n\nYou need to be able to post "
        "there yourself. All I ask for is the right to post – the board is never edited once it is up."}]}, reply_markup=picker)


def handle_shared_channel(msg):
    shared = msg.get("chat_shared") or {}
    channel_id = shared.get("chat_id")
    user_id = (msg.get("from") or {}).get("id")
    private_chat = (msg.get("chat") or {}).get("id")
    if not channel_id or not user_id or not private_chat:
        return
    member = ((tg.api("getChatMember", {"chat_id": channel_id, "user_id": me["id"]}) or {})
              .get("result") or {})
    status = member.get("status")
    if status not in ("administrator", "creator") or (
            status == "administrator" and not member.get("can_post_messages", False)):
        tg.text_send(private_chat, "The bot must be an administrator with permission to post messages in that channel.",
                     {"remove_keyboard": True})
        return
    info = tg.api("getChat", {"chat_id": channel_id})
    title = (info or {}).get("result", {}).get("title") or shared.get("title") or "channel"
    state["channel_targets"][str(user_id)] = {"chat_id": str(channel_id), "title": title}
    save()
    tg.text_send(private_chat, f"Channel selected: {title}. Posting the board now.", {"remove_keyboard": True})
    start_lobby(channel_id, user_id)


def command_of(text):
    """Return the command name, or '' when the text is not a command for this bot."""
    first = text.split(maxsplit=1)[0] if text else ""
    if not first.startswith("/"):
        return ""
    name, _, target = first.partition("@")
    if target and target.lower() != me["username"].lower():
        return ""
    return name.lower()


def handle_message(msg, channel_post=False):
    if msg.get("chat_shared"):
        handle_shared_channel(msg)
        return
    text = (msg.get("text") or "").strip()
    user = msg.get("from") or {}
    uid = user.get("id") or OWNER_ID
    chat = msg.get("chat") or {}
    chat_id, chat_type = chat.get("id"), chat.get("type")
    if not chat_id or not text:
        return
    if admin_message(chat_id, uid, text):
        return
    command = command_of(text)
    first_word = text.split(maxsplit=1)[0]
    is_owner = user.get("id") == OWNER_ID
    set_word = next((w for w in SET_PACK_WORDS if text == w or text.startswith(w + " ")), None)
    if is_owner and set_word:
        set_pack(chat_id, text[len(set_word):])
    elif is_owner and (command in RESET_PACK_WORDS or text in RESET_PACK_WORDS):
        reset_pack(chat_id)
    elif is_owner and (command in INSPECT_WORDS or first_word in INSPECT_WORDS
                       or (chat_type == "private" and not command and custom_emoji_found(msg))):
        inspect_message(msg, chat_id)
    elif command == "/group":
        send_group_help(chat_id, reply_to(msg))
    elif command == "/channel":
        send_channel_help(chat_id)
    elif command == "/help":
        tg.text_send(chat_id, HELP, reply=reply_to(msg))
    elif command == "/top":
        tg.text_send(chat_id, leaderboard(chat_id, chat_type), reply=reply_to(msg))
    elif command == "/me" and user.get("id"):
        tg.text_send(chat_id, my_stats(user), reply=reply_to(msg))
    elif command in ("/start", "/play", "/connect4", "/cpu") or text in PLAY_WORDS:
        if not subscribed(uid):
            gate(msg)
        elif channel_post or chat_type == "channel" or (chat_type in GROUP_TYPES and command == "/cpu"):
            # A shared board: each presser plays their own game in an ephemeral view.
            start_lobby(chat_id, uid)
        elif chat_type in GROUP_TYPES and command != "/cpu":
            replied = (msg.get("reply_to_message") or {}).get("from") or {}
            invited = None
            if replied.get("id") and not replied.get("is_bot") and replied["id"] != user.get("id"):
                invited = (str(replied["id"]), display_name(replied))
            start_challenge(chat_id, user, invited)
        elif user.get("id"):
            start_cpu(chat_id, user)


# ----------------------------------------------------------------- callbacks

def handle_callback(query):
    qid = query["id"]
    user = query.get("from") or {}
    message = query.get("message") or {}
    parts = (query.get("data") or "").split(":")
    if len(parts) < 4 or parts[0] != "c4":
        tg.answer(qid)
        return
    _, chat, game_id, kind = parts[:4]
    value = parts[4] if len(parts) > 4 else ""
    game = state["games"].get(game_key(chat, game_id))
    if not game:
        tg.answer(qid, "This game has ended. Start a new one with /play", True)
        return
    view = {"chat_id": (message.get("chat") or {}).get("id"),
            "message_id": message.get("message_id"), "user_id": user.get("id")}
    if game["mode"] == "lobby":
        lobby_press(qid, game, kind, value, user, view)
        return
    if message.get("ephemeral_message_id"):
        if game["mode"] == "pvp":
            game.setdefault("views", {})[str(user.get("id"))] = message["ephemeral_message_id"]
        else:
            game["ephemeral_message_id"] = message["ephemeral_message_id"]
    if game["mode"] == "cpu":
        cpu_press(qid, game, kind, value, user, view)
    else:
        pvp_press(qid, game, kind, value, user, view)


def lobby_press(qid, game, kind, value, user, view):
    """Open the reader's own game from a channel board, keeping the board untouched."""
    if kind not in ("play", "lobbycol"):
        tg.answer(qid)
        return
    target_chat = view["chat_id"] or game["chat"]
    user_game = create_cpu_game(target_chat, user)
    col = parse_column(value) if kind == "lobbycol" else None
    if col is not None:
        play_column(user_game, col)
        computer_reply(user_game)
    rich = render(user_game, True)
    sent = tg.rich_ephemeral_send(target_chat, user["id"], qid, rich)
    ephemeral_id = ((sent or {}).get("result") or {}).get("ephemeral_message_id")
    if ephemeral_id:
        user_game["ephemeral_message_id"] = ephemeral_id
        save()
        tg.answer(qid)
        return
    # Channels may refuse ephemeral messages; fall back to the private chat.
    private = tg.rich_send(user["id"], rich)
    if private and private.get("result"):
        user_game["message_id"] = private["result"].get("message_id")
        save()
        tg.answer(qid, "Game opened in your private chat")
        return
    del state["games"][game_key(user_game["chat"], user_game["id"])]
    tg.answer(qid, "Open the bot privately first, then press Play Game", True)


def cpu_press(qid, game, kind, value, user, view):
    if str(user.get("id")) != game["owner"]:
        tg.answer(qid, "This game is not yours. Start your own with /play", True)
        return
    playing = game["phase"] == "play"
    if kind == "col":
        col = parse_column(value)
        if not playing or col is None:
            tg.answer(qid)
            return
        if game["turn"] != engine.RED:
            tg.answer(qid, "Wait for the computer")
            return
        if game["board"][col] != engine.EMPTY:
            tg.answer(qid, "That column is full – pick another")
            return
        # Answer before the computer thinks so the button spinner stops at once.
        tg.answer(qid)
        play_column(game, col)
        if game["phase"] == "play":
            refresh(game, **view)
            computer_reply(game)
    elif kind == "level" and playing and not game["history"] and value in engine.LEVELS:
        tg.answer(qid, "Level: " + cards.LEVEL_NAMES[value])
        game["level"] = value
    elif kind == "undo" and playing and len(game["history"]) >= 2:
        tg.answer(qid)
        undo(game)
    elif kind == "resign" and playing and game["history"]:
        tg.answer(qid)
        finish(game, engine.YELLOW, reason="resign")
    elif kind == "rematch" and not playing:
        tg.answer(qid)
        reset_board(game)
    else:
        tg.answer(qid)
        return
    save()
    refresh(game, **view)


def open_view(qid, game, user, view):
    """Show the pressing user a premium copy of the board that follows every move."""
    uid = str(user.get("id"))
    views = game.setdefault("views", {})
    if game["phase"] != "play":
        tg.answer(qid)
        return
    if uid not in views and len(views) >= MAX_VIEWERS:
        tg.answer(qid, "Too many people are watching this game right now", True)
        return
    sent = tg.rich_ephemeral_send(view["chat_id"] or game["chat"], user["id"], qid, render(game, True))
    ephemeral_id = ((sent or {}).get("result") or {}).get("ephemeral_message_id")
    if not ephemeral_id:
        tg.answer(qid, "Could not open the board here. Please try again.", True)
        return
    views[uid] = ephemeral_id
    save()
    tg.answer(qid)


def pvp_press(qid, game, kind, value, user, view):
    uid = str(user.get("id"))
    seats, names = game["players"], game["names"]
    seated = uid in (seats[engine.RED], seats[engine.YELLOW])
    if kind == "view":
        open_view(qid, game, user, view)
        return
    if game["phase"] == "waiting":
        if kind == "join":
            if uid == seats[engine.RED]:
                tg.answer(qid, "Waiting for someone to accept your challenge")
                return
            if game.get("invited") and uid != game["invited"]:
                tg.answer(qid, f"This challenge is for {game['invited_name']} only", True)
                return
            remember(user, game["chat"])
            seats[engine.YELLOW], names[engine.YELLOW] = uid, display_name(user)
            game["phase"], game["turn_started"] = "play", time.time()
            tg.answer(qid, "Game on! 🔴 moves first")
        elif kind in ("cpu", "cancel"):
            if uid != seats[engine.RED]:
                tg.answer(qid, "Only the player who opened the challenge can do that", True)
                return
            tg.answer(qid)
            if kind == "cancel":
                game["phase"], game["reason"] = "over", "cancelled"
            else:
                game.pop("invited", None)
                seats[engine.YELLOW], names[engine.YELLOW] = "cpu", cards.COMPUTER_NAME
                game.update(mode="cpu", level="normal", phase="play")
        else:
            tg.answer(qid)
            return
    elif game["phase"] == "play":
        if not seated:
            tg.answer(qid, f"This game is between {names[engine.RED]} and {names[engine.YELLOW]}. "
                           "Start your own with /play", True)
            return
        if kind == "col":
            col = parse_column(value)
            if col is None:
                tg.answer(qid)
                return
            if uid != seats[game["turn"]]:
                tg.answer(qid, "Not your turn – wait for your opponent")
                return
            if game["board"][col] != engine.EMPTY:
                tg.answer(qid, "That column is full – pick another")
                return
            tg.answer(qid)
            play_column(game, col)
        elif kind == "resign":
            tg.answer(qid, "You resigned")
            mine = engine.RED if uid == seats[engine.RED] else engine.YELLOW
            finish(game, engine.other(mine), reason="resign")
        else:
            tg.answer(qid)
            return
    else:
        if kind == "rematch" and seated and game.get("reason") != "cancelled":
            tg.answer(qid)
            rival = engine.YELLOW if uid == seats[engine.RED] else engine.RED
            start_challenge(game["chat"], user, (seats[rival], names[rival]))
        else:
            tg.answer(qid)
        return
    save()
    refresh(game, **view)


# ------------------------------------------------------------------ run loop

def expire_turns(now=None):
    """End challenges where the player to move ran out of time."""
    now = now or time.time()
    changed = False
    for game in list(state["games"].values()):
        if (game.get("mode") == "pvp" and game.get("phase") == "play"
                and now - game.get("turn_started", now) > cards.TURN_SECONDS):
            finish(game, engine.other(game["turn"]), reason="timeout")
            refresh(game)
            changed = True
    if changed:
        save()


def prune(now=None):
    """Drop old games; channel boards stay because readers keep pressing them."""
    now = now or time.time()
    for key, game in list(state["games"].items()):
        age = now - game.get("updated", now)
        if game.get("mode") != "lobby" and (age > 7 * DAY or (game.get("phase") == "over" and age > 2 * DAY)):
            del state["games"][key]
    save()


def main():
    if not TOKEN:
        raise SystemExit("CONNECT4_TOKEN is required")
    tg.configure(TOKEN)
    info = (tg.api("getMe") or {}).get("result")
    if not info:
        raise SystemExit("Could not reach Telegram. Check CONNECT4_TOKEN.")
    me.update(id=info["id"], username=info.get("username", ""))
    apply_custom_emoji()
    tg.api("deleteWebhook", {"drop_pending_updates": False})
    tg.api("setMyCommands", {"commands": COMMANDS})
    print(f"@{me['username']} is running", flush=True)
    last_prune = 0
    while True:
        # A short poll keeps the move timer accurate to about ten seconds.
        result = tg.api("getUpdates", {"offset": state["offset"] + 1, "timeout": 10, "limit": 50})
        for update in (result or {}).get("result", []):
            state["offset"] = update["update_id"]
            save()
            try:
                if update.get("message"):
                    handle_message(update["message"])
                elif update.get("channel_post"):
                    handle_message(update["channel_post"], channel_post=True)
                elif update.get("callback_query"):
                    handle_callback(update["callback_query"])
            except Exception as exc:
                print(f"update failed: {exc!r}", flush=True)
        expire_turns()
        if time.time() - last_prune > 3600:
            prune()
            last_prune = time.time()
        if not result:
            time.sleep(1)


if __name__ == "__main__":
    main()
