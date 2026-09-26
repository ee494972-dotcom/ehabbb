"""Rich-message cards for every screen of the game."""
import engine

TURN_SECONDS = 60
START_RATING = 1000
COMPUTER_NAME = "Computer"
DISC = {engine.RED: "🔴", engine.YELLOW: "🟡", engine.EMPTY: "⚫"}
WIN_DISC = {engine.RED: "🟥", engine.YELLOW: "🟨"}
COLUMN_KEYS = ("1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣")
LEVEL_NAMES = {"easy": "Easy", "normal": "Normal", "hard": "Hard"}
TITLES = ((1500, "Legend 👑"), (1300, "Expert 💎"), (1150, "Pro 🔥"), (1000, "Amateur ⭐"))
# Optional Telegram custom emoji ids (the owner's /inspect command lists them).
# Leave a value empty to keep the standard emoji shown above.
CUSTOM_EMOJI = {
    engine.RED: "", engine.YELLOW: "", engine.EMPTY: "",
    engine.RED + "_win": "", engine.YELLOW + "_win": "",
}


def rank_title(rating):
    for floor, name in TITLES:
        if rating >= floor:
            return name
    return "Beginner 🌱"


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


def disc_view(disc, winning=False):
    fallback = WIN_DISC[disc] if winning else DISC[disc]
    custom_id = CUSTOM_EMOJI.get(disc + ("_win" if winning else ""))
    if custom_id:
        return {"type": "custom_emoji", "custom_emoji_id": custom_id, "alternative_text": fallback}
    return fallback


def board_table(game, interactive, lobby=False):
    """Numbered drop buttons above a shaded grid; discs fall to the lowest free space."""
    base = prefix(game)
    winning = set(game.get("win_line") or ())
    keys = []
    for col in range(engine.COLS):
        label = COLUMN_KEYS[col]
        if interactive:
            action = f"lobbycol:{col}" if lobby else f"col:{col}"
            label = {"type": "button", "button": button(label, base + action, "link")}
        keys.append(cell(label))
    rows = [keys]
    for row in range(engine.ROWS):
        rows.append([cell(disc_view(game["board"][engine.idx(row, col)], engine.idx(row, col) in winning), True)
                     for col in range(engine.COLS)])
    return {"type": "table", "cells": rows, "is_bordered": False, "is_striped": False, "is_compact": True}


def move_details(game):
    history = game["history"]
    lines = []
    for start in range(0, len(history), 2):
        pair = [f"{DISC[disc]} {col + 1}" for disc, col in zip((engine.RED, engine.YELLOW), history[start:start + 2])]
        lines.append(f"{start // 2 + 1}. " + " · ".join(pair))
    return {"type": "details", "summary": f"Moves ({len(history)})",
            "blocks": [paragraph("\n".join(lines))]}


def render(game, players):
    if game["mode"] == "lobby":
        return lobby_card(game)
    if game["mode"] == "cpu":
        return cpu_card(game)
    return pvp_card(game, players)


def lobby_card(game):
    return {"blocks": [
        paragraph(bold("🔴🟡 Connect Four")),
        board_table(game, interactive=True, lobby=True),
        quote("Tap a number to play the computer. The game is yours alone – "
              "everyone else here sees this board, not your moves."),
        button_row(button("▶️ Play Game", prefix(game) + "play", "primary")),
    ]}


def cpu_card(game):
    base = prefix(game)
    playing = game["phase"] == "play"
    history = game["history"]
    level = game.get("level", "normal")
    blocks = [
        paragraph(bold(f"🔴 {game['names'][engine.RED]}  vs  🟡 {COMPUTER_NAME}"),
                  f"\nLevel: {LEVEL_NAMES[level]}"),
        board_table(game, interactive=playing),
    ]
    if not playing:
        blocks.append(quote(cpu_result(game)))
        if history:
            blocks.append(move_details(game))
        blocks.append(button_row(button("🔁 Play Again", base + "rematch", "success")))
        return {"blocks": blocks}
    if game["turn"] != engine.RED:
        status = "Computer is thinking…"
    elif not history:
        status = ("Tap a number to drop your disc into that column – it falls to the lowest free space.\n"
                  "Connect 4 in a row (across, down or diagonally) to win.")
    else:
        status = f"Computer dropped in column {history[-1] + 1}. Your turn."
    blocks.append(quote(status))
    if history:
        blocks.append(move_details(game))
    else:
        blocks.append(button_row(*(button(LEVEL_NAMES[name], base + "level:" + name,
                                          "primary" if name == level else None)
                                   for name in engine.LEVELS)))
    blocks.append(button_row(button("↩️ Undo", base + "undo", disabled=len(history) < 2),
                             button("🏳️ Resign", base + "resign", disabled=not history)))
    return {"blocks": blocks}


def cpu_result(game):
    if game["winner"] == engine.RED:
        return "🎉 You win!"
    if game["winner"] == engine.YELLOW:
        if game.get("reason") == "resign":
            return "🏳️ You resigned. The computer wins."
        return "🤖 The computer wins this time. Try again!"
    return "🤝 Draw – the board is full."


def pvp_card(game, players):
    base = prefix(game)
    names, seats = game["names"], game["players"]
    red = f"🔴 {names[engine.RED]} ({rating_of(players, seats[engine.RED])})"
    if game["phase"] == "waiting":
        line = (f"\n{red} challenges {game['invited_name']}" if game.get("invited")
                else f"\n{red} is waiting for an opponent")
        return {"blocks": [
            paragraph(bold("⚔️ Connect Four Challenge"), line),
            board_table(game, interactive=False),
            quote(f"{TURN_SECONDS} seconds per move. Connect 4 in a row to win and climb the leaderboard."),
            button_row(button("✅ Accept Challenge", base + "join", "primary")),
            button_row(button("🤖 Play the Computer", base + "cpu"), button("❌ Cancel", base + "cancel")),
        ]}
    if game.get("reason") == "cancelled":
        return {"blocks": [paragraph(bold("❌ Challenge cancelled"),
                                     f"\n{names[engine.RED]} cancelled the challenge.")]}
    yellow = f"🟡 {names[engine.YELLOW]} ({rating_of(players, seats[engine.YELLOW])})"
    playing = game["phase"] == "play"
    blocks = [paragraph(bold(f"{red}  vs  {yellow}")), board_table(game, interactive=playing)]
    if playing:
        turn, history = game["turn"], game["history"]
        status = f"{DISC[turn]} {names[turn]}'s turn · ⏱ {TURN_SECONDS}s per move"
        status += (f"\nLast move: column {history[-1] + 1}" if history
                   else "\nTap a number to drop a disc into that column.")
        blocks.append(quote(status))
        if history:
            blocks.append(move_details(game))
        blocks.append(button_row(button("🏳️ Resign", base + "resign")))
    else:
        blocks.append(quote(pvp_result(game)))
        if game["history"]:
            blocks.append(move_details(game))
        blocks.append(button_row(button("🔁 Rematch", base + "rematch", "success")))
    return {"blocks": blocks}


def pvp_result(game):
    names, change, winner = game["names"], game.get("rating_change", 0), game["winner"]
    if winner is None:
        return (f"🤝 Draw – the board is full.\n"
                f"{names[engine.RED]}: {change:+d} · {names[engine.YELLOW]}: {-change:+d}")
    loser = engine.other(winner)
    gained = change if winner == engine.RED else -change
    how = {"timeout": f"\n⏱ {names[loser]} ran out of time.",
           "resign": f"\n🏳️ {names[loser]} resigned."}.get(game.get("reason"), "")
    return f"🏆 {names[winner]} wins! (+{gained})\n{names[loser]}: -{gained}{how}"
