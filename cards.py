"""Rich-message cards for every screen of the game."""
import engine

TURN_SECONDS = 60
START_RATING = 1000
COMPUTER_NAME = "الكمبيوتر"
DISC = {engine.RED: "🔴", engine.YELLOW: "🟡", engine.EMPTY: "⚪"}
WIN_DISC = {engine.RED: "🟥", engine.YELLOW: "🟨"}
LEVEL_NAMES = {"easy": "سهل", "normal": "متوسط", "hard": "صعب"}
TITLES = ((1500, "أسطورة 👑"), (1300, "خبير 💎"), (1150, "محترف 🔥"), (1000, "هاوي ⭐"))


def rank_title(rating):
    for floor, name in TITLES:
        if rating >= floor:
            return name
    return "مبتدئ 🌱"


def button(text, callback=None, style=None, disabled=False):
    value = {"text": text}
    if callback and not disabled:
        value["callback_data"] = callback
    if style:
        value["style"] = style
    if disabled:
        value["disabled"] = {}
    return value


def cell(content, header=False):
    return {"text": content, "is_header": header, "align": "center", "valign": "middle"}


def bold(text):
    return {"type": "bold", "text": text}


def paragraph(*parts):
    return {"type": "paragraph", "text": list(parts)}


def quote(text):
    return {"type": "blockquote", "blocks": [paragraph(text)]}


def button_row(*items):
    return {"type": "buttons", "buttons": list(items)}


def prefix(game):
    return f"c4:{game['chat']}:{game['id']}:"


def rating_of(players, uid):
    return players.get(str(uid), {}).get("rating", START_RATING)


def board_table(game, interactive, lobby=False):
    base = prefix(game)
    winning = set(game.get("win_line") or ())
    rows = [[cell(str(col + 1), True) for col in range(engine.COLS)]]
    for row in range(engine.ROWS):
        cells = []
        for col in range(engine.COLS):
            i = engine.idx(row, col)
            disc = game["board"][i]
            content = WIN_DISC[disc] if i in winning else DISC[disc]
            if interactive:
                action = f"lobbycol:{col}" if lobby else f"col:{col}"
                content = {"type": "button", "button": button(content, base + action, "link")}
            cells.append(cell(content))
        rows.append(cells)
    return {"type": "table", "cells": rows, "is_bordered": False, "is_striped": False, "is_compact": True}


def render(game, players):
    if game["mode"] == "lobby":
        return lobby_card(game)
    if game["mode"] == "cpu":
        return cpu_card(game)
    return pvp_card(game, players)


def lobby_card(game):
    return {"blocks": [
        paragraph(bold("🔴🟡 أربعة في صف")),
        board_table(game, interactive=True, lobby=True),
        quote("اضغط على أي عمود عشان تلعب ضد الكمبيوتر. اللعبة ليك لوحدك، ومحدش هنا هيشوف حركاتك."),
        button_row(button("▶️ ابدأ اللعب", prefix(game) + "play", "primary")),
    ]}


def cpu_card(game):
    base = prefix(game)
    playing = game["phase"] == "play"
    moves = len(game["history"])
    level = game.get("level", "normal")
    blocks = [
        paragraph(bold(f"🔴 {game['names'][engine.RED]}  ضد  🟡 {COMPUTER_NAME}"),
                  f"\nالمستوى: {LEVEL_NAMES[level]} · {moves} حركة"),
        board_table(game, interactive=playing),
    ]
    if not playing:
        blocks.append(quote(cpu_result(game)))
        blocks.append(button_row(button("🔁 العب تاني", base + "rematch", "success")))
        return {"blocks": blocks}
    status = "دورك: اضغط على العمود اللي عايز تنزّل فيه." if game["turn"] == engine.RED else "الكمبيوتر بيفكر..."
    if not moves:
        status += "\nكمّل 4 من لونك في صف، أفقي أو رأسي أو مايل، عشان تكسب."
    blocks.append(quote(status))
    if not moves:
        blocks.append(button_row(*(button(LEVEL_NAMES[name], base + "level:" + name,
                                          "primary" if name == level else None)
                                   for name in engine.LEVELS)))
    blocks.append(button_row(button("↩️ تراجع", base + "undo", disabled=moves < 2),
                             button("🏳️ استسلام", base + "resign", disabled=not moves)))
    return {"blocks": blocks}


def cpu_result(game):
    if game["winner"] == engine.RED:
        return "🎉 مبروك، كسبت!"
    if game["winner"] == engine.YELLOW:
        if game.get("reason") == "resign":
            return "🏳️ استسلمت، والكمبيوتر كسب."
        return "🤖 الكمبيوتر كسب المرة دي. جرّب تاني!"
    return "🤝 تعادل، الرقعة اتملت."


def pvp_card(game, players):
    base = prefix(game)
    names, seats = game["names"], game["players"]
    red = f"🔴 {names[engine.RED]} ({rating_of(players, seats[engine.RED])})"
    if game["phase"] == "waiting":
        line = (f"\n{red} بيتحدى {game['invited_name']}" if game.get("invited")
                else f"\n{red} مستني منافس")
        return {"blocks": [
            paragraph(bold("⚔️ تحدي أربعة في صف"), line),
            board_table(game, interactive=False),
            quote(f"كل لاعب ليه {TURN_SECONDS} ثانية للحركة. اللي يكمّل 4 في صف يكسب ويزوّد نقاطه."),
            button_row(button("✅ اقبل التحدي", base + "join", "primary")),
            button_row(button("🤖 العب ضد الكمبيوتر", base + "cpu"), button("❌ إلغاء", base + "cancel")),
        ]}
    if game.get("reason") == "cancelled":
        return {"blocks": [paragraph(bold("❌ التحدي اتلغى"), f"\n{names[engine.RED]} لغى التحدي.")]}
    yellow = f"🟡 {names[engine.YELLOW]} ({rating_of(players, seats[engine.YELLOW])})"
    playing = game["phase"] == "play"
    blocks = [paragraph(bold(f"{red}  ضد  {yellow}")), board_table(game, interactive=playing)]
    if playing:
        turn = game["turn"]
        blocks.append(quote(f"الدور على {DISC[turn]} {names[turn]}\n"
                            f"⏱ {TURN_SECONDS} ثانية للحركة، واللي وقته يخلص يخسر."))
        blocks.append(button_row(button("🏳️ استسلام", base + "resign")))
    else:
        blocks.append(quote(pvp_result(game)))
        blocks.append(button_row(button("🔁 تحدي تاني", base + "rematch", "success")))
    return {"blocks": blocks}


def pvp_result(game):
    names, change, winner = game["names"], game.get("rating_change", 0), game["winner"]
    if winner is None:
        return (f"🤝 تعادل، الرقعة اتملت.\n"
                f"{names[engine.RED]}: {change:+d} · {names[engine.YELLOW]}: {-change:+d}")
    loser = engine.other(winner)
    gained = change if winner == engine.RED else -change
    how = {"timeout": f"\n⏱ وقت {names[loser]} خلص.",
           "resign": f"\n🏳️ {names[loser]} استسلم."}.get(game.get("reason"), "")
    return f"🏆 {names[winner]} كسب! (+{gained} نقطة)\n{names[loser]}: -{gained} نقطة{how}"
