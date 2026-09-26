import tempfile
import unittest
from pathlib import Path
from unittest import mock

import connect4_bot as bot
import engine
import storage
import telegram_api as tg

GROUP = {"id": -100500, "type": "supergroup"}
ALI = {"id": 11, "first_name": "Ali"}
MONA = {"id": 22, "first_name": "Mona"}
SARA = {"id": 33, "first_name": "Sara"}


class FakeTelegram:
    def __init__(self):
        self.calls = []
        self.counter = 1000

    def __call__(self, method, params=None, timeout=45):
        params = params or {}
        self.calls.append((method, params))
        self.counter += 1
        if method == "sendRichMessage" and "ephemeral_message_parameters" in params:
            return {"ok": True, "result": {"ephemeral_message_id": self.counter}}
        return {"ok": True, "result": {"message_id": self.counter}}

    def methods(self):
        return [method for method, _ in self.calls]

    def alerts(self):
        return [p.get("text") for m, p in self.calls if m == "answerCallbackQuery" and p.get("text")]


class BotTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(storage, "STATE_FILE", Path(tmp.name) / "state.json")
        patcher.start()
        self.addCleanup(patcher.stop)
        bot.state = storage.load()
        bot.me.update(id=1, username="Connect4Bot")
        self.tg = FakeTelegram()
        patcher = mock.patch.object(tg, "api", self.tg)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.query_id = 0

    def say(self, user, text, chat=None, reply_to=None):
        msg = {"from": user, "chat": chat or {"id": user["id"], "type": "private"}, "text": text}
        if reply_to:
            msg["reply_to_message"] = {"from": reply_to}
        bot.handle_message(msg)

    def press(self, user, game, action, chat_id=None, ephemeral_id=None):
        self.query_id += 1
        message = {"chat": {"id": chat_id or int(game["chat"])}, "message_id": game.get("message_id")}
        if ephemeral_id:
            message["ephemeral_message_id"] = ephemeral_id
        bot.handle_callback({"id": str(self.query_id), "from": user, "message": message,
                             "data": f"c4:{game['chat']}:{game['id']}:{action}"})

    def latest_game(self):
        return list(bot.state["games"].values())[-1]

    def test_group_challenge_is_rated(self):
        self.say(ALI, "/play", GROUP)
        game = self.latest_game()
        self.assertEqual(game["phase"], "waiting")
        self.press(MONA, game, "join")
        self.assertEqual(game["phase"], "play")
        for user, col in [(ALI, 0), (MONA, 1), (ALI, 0), (MONA, 1), (ALI, 0), (MONA, 1), (ALI, 0)]:
            self.press(user, game, f"col:{col}")
        self.assertEqual(game["winner"], engine.RED)
        ali, mona = bot.state["players"]["11"], bot.state["players"]["22"]
        self.assertEqual((ali["rating"], mona["rating"]), (1016, 984))
        self.assertEqual((ali["wins"], mona["losses"]), (1, 1))
        self.assertIn("Ali", bot.leaderboard(GROUP["id"], "supergroup"))

    def test_only_the_player_to_move_can_drop(self):
        self.say(ALI, "/play", GROUP)
        game = self.latest_game()
        self.press(MONA, game, "join")
        self.press(MONA, game, "col:3")
        self.press(SARA, game, "col:3")
        self.assertEqual(game["history"], [])
        self.assertIn("Not your turn – wait for your opponent", self.tg.alerts())

    def test_reply_challenge_is_reserved_for_the_invited_player(self):
        self.say(ALI, "/play@Connect4Bot", GROUP, reply_to=MONA)
        game = self.latest_game()
        self.press(SARA, game, "join")
        self.assertEqual(game["phase"], "waiting")
        self.press(MONA, game, "join")
        self.assertEqual(game["players"][engine.YELLOW], "22")

    def test_commands_for_other_bots_are_ignored(self):
        self.say(ALI, "/play@SomeOtherBot", GROUP)
        self.assertEqual(bot.state["games"], {})

    def test_running_out_of_time_loses(self):
        self.say(ALI, "/play", GROUP)
        game = self.latest_game()
        self.press(MONA, game, "join")
        game["turn_started"] -= 61
        bot.expire_turns()
        self.assertEqual((game["winner"], game["reason"]), (engine.YELLOW, "timeout"))
        self.assertEqual(bot.state["players"]["22"]["wins"], 1)

    def test_private_game_against_the_computer(self):
        self.say(ALI, "/start")
        game = self.latest_game()
        self.assertEqual(game["mode"], "cpu")
        self.press(ALI, game, "level:hard")
        self.press(ALI, game, "col:3")
        self.assertEqual(len(game["history"]), 2)
        self.assertEqual(game["turn"], engine.RED)
        self.press(ALI, game, "undo")
        self.assertEqual(game["history"], [])
        self.press(MONA, game, "col:3")
        self.assertEqual(game["history"], [])

    def test_channel_board_opens_a_private_game_per_reader(self):
        bot.handle_message({"chat": {"id": -100900, "type": "channel"}, "text": "/play"}, channel_post=True)
        lobby = self.latest_game()
        self.assertEqual(lobby["mode"], "lobby")
        self.press(ALI, lobby, "lobbycol:3")
        own = self.latest_game()
        self.assertEqual((own["mode"], own["owner"], len(own["history"])), ("cpu", "11", 2))
        self.assertIsNotNone(own.get("ephemeral_message_id"))
        self.assertEqual(lobby["board"], engine.new_board())
        self.press(ALI, own, "col:3", chat_id=-100900, ephemeral_id=own["ephemeral_message_id"])
        self.assertEqual(self.tg.methods()[-1], "editEphemeralMessageText")

    def test_subscription_gate_blocks_non_members(self):
        bot.state["channel"] = "news"
        with mock.patch.object(bot, "subscribed", return_value=False):
            self.say(ALI, "/play")
        self.assertEqual(bot.state["games"], {})

    def test_cards_render_for_every_screen(self):
        self.say(ALI, "/play", GROUP)
        game = self.latest_game()
        for step in ("waiting", "play", "over"):
            with self.subTest(step):
                self.assertTrue(bot.render(game)["blocks"])
                if step == "waiting":
                    self.press(MONA, game, "join")
                elif step == "play":
                    self.press(ALI, game, "resign")


    def test_only_the_numbered_row_is_pressable(self):
        self.say(ALI, "/start")
        table = bot.render(self.latest_game())["blocks"][1]
        callbacks = [c["text"]["button"].get("callback_data") for row in table["cells"] for c in row
                     if isinstance(c["text"], dict) and c["text"].get("type") == "button"]
        self.assertEqual(len(callbacks), engine.COLS)
        self.assertTrue(all(":col:" in data for data in callbacks))

    def test_owner_can_inspect_custom_emoji(self):
        reply = {"text": "x", "entities": [{"type": "custom_emoji", "custom_emoji_id": "555"}]}
        bot.handle_message({"from": {"id": bot.OWNER_ID}, "chat": {"id": 5, "type": "private"},
                            "text": "/inspect", "reply_to_message": reply})
        self.assertIn("555", self.tg.calls[-1][1]["text"])

if __name__ == "__main__":
    unittest.main()
