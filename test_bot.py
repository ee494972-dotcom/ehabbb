import json
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
        self.assertIn("Ali wins – four down!", bot.cards.pvp_result(game))
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


    def test_every_cell_drops_into_its_column(self):
        self.say(ALI, "/start")
        table = bot.render(self.latest_game())["blocks"][1]
        self.assertEqual(len(table["cells"]), engine.ROWS)
        for row in table["cells"]:
            columns = [c["text"]["button"]["callback_data"].rsplit(":", 1)[1] for c in row]
            self.assertEqual(columns, [str(col) for col in range(engine.COLS)])
        game = self.latest_game()
        self.press(ALI, game, "col:2")
        self.assertEqual(game["board"][engine.idx(engine.ROWS - 1, 2)], engine.RED)

    def owner_says(self, text, **extra):
        bot.handle_message({"from": {"id": bot.OWNER_ID}, "chat": {"id": bot.OWNER_ID, "type": "private"},
                            "text": text, **extra})
        return self.tg.calls[-1][1]["text"]

    def test_owner_can_inspect_a_replied_message(self):
        reply = {"text": "🔴", "entities": [{"type": "custom_emoji", "offset": 0, "length": 2,
                                             "custom_emoji_id": "555"}]}
        self.assertIn("🔴  555", self.owner_says("/inspect", reply_to_message=reply))

    def test_owner_can_inspect_emoji_sent_with_the_word(self):
        entities = [{"type": "custom_emoji", "offset": 4, "length": 2, "custom_emoji_id": "777"}]
        self.assertIn("🔴  777", self.owner_says("فحص 🔴", entities=entities))

    def test_owner_can_inspect_emoji_sent_alone(self):
        entities = [{"type": "custom_emoji", "offset": 0, "length": 2, "custom_emoji_id": "1"},
                    {"type": "custom_emoji", "offset": 2, "length": 2, "custom_emoji_id": "2"}]
        reply = self.owner_says("🔴🟡", entities=entities)
        self.assertIn("🔴  1", reply)
        self.assertIn("🟡  2", reply)

    def test_premium_emoji_only_where_telegram_keeps_them(self):
        with mock.patch.dict(bot.cards.CUSTOM_EMOJI, {engine.EMPTY: "900"}):
            self.say(ALI, "/start")
            self.assertIn('"900"', json.dumps(self.tg.calls[-1][1]["rich_message"]))
            self.say(ALI, "/cpu", GROUP)
            self.assertIn('"900"', json.dumps(self.tg.calls[-1][1]["rich_message"]))
            self.say(ALI, "/play", GROUP)
            self.assertNotIn('"900"', json.dumps(self.tg.calls[-1][1]["rich_message"]))
            game = self.latest_game()
            self.press(MONA, game, "join")
            edits = [p for m, p in self.tg.calls if m == "editMessageText"]
            self.assertNotIn('"900"', json.dumps(edits[-1]["rich_message"]))
            views = [p for m, p in self.tg.calls if m == "sendRichMessage" and "ephemeral_message_parameters" in p]
            self.assertIn('"900"', json.dumps(views[-1]["rich_message"]))

    def test_refused_premium_edit_falls_back_to_standard_emoji(self):
        real = self.tg

        def telegram(method, params=None, timeout=45):
            if method == "editMessageText" and '"900"' in json.dumps(params["rich_message"]):
                real.calls.append((method, params))
                tg.last_error = "Bad Request: custom emoji not allowed"
                return None
            return real(method, params, timeout)

        with mock.patch.dict(bot.cards.CUSTOM_EMOJI, {engine.EMPTY: "900"}):
            self.say(ALI, "/start")
            game = self.latest_game()
            with mock.patch.object(tg, "api", telegram):
                self.press(ALI, game, "col:3")
        edits = [p for m, p in self.tg.calls if m == "editMessageText"]
        self.assertIn('"900"', json.dumps(edits[-2]["rich_message"]))
        self.assertNotIn('"900"', json.dumps(edits[-1]["rich_message"]))

    def non_admin_telegram(self):
        """Ephemeral sends without the receiver's own button press are refused, as for a non-admin bot."""
        real = self.tg

        def telegram(method, params=None, timeout=45):
            ephemeral = (params or {}).get("ephemeral_message_parameters")
            if ephemeral and not ephemeral.get("callback_query_id"):
                real.calls.append((method, params))
                return None
            return real(method, params, timeout)
        return telegram

    def test_challenge_boards_turn_premium_on_accept_and_first_move(self):
        with mock.patch.dict(bot.cards.CUSTOM_EMOJI, {engine.EMPTY: "900"}), \
                mock.patch.object(tg, "api", self.non_admin_telegram()):
            self.say(ALI, "/play", GROUP)
            game = self.latest_game()
            self.press(MONA, game, "join")
            self.assertEqual(list(game["views"]), ["22"])
            self.press(ALI, game, "col:3")
            self.assertEqual(sorted(game["views"]), ["11", "22"])
            self.press(MONA, game, "col:3", ephemeral_id=game["views"]["22"])
            edits = [p for m, p in self.tg.calls if m == "editEphemeralMessageText"]
            self.assertEqual({p["receiver_user_id"] for p in edits[-2:]}, {11, 22})
            self.assertIn('"900"', json.dumps(edits[-1]["rich_message"]))
            self.assertEqual(len(game["history"]), 2)

    def test_admin_bot_gives_the_creator_a_premium_board_on_accept(self):
        with mock.patch.dict(bot.cards.CUSTOM_EMOJI, {engine.EMPTY: "900"}):
            self.say(ALI, "/play", GROUP)
            game = self.latest_game()
            self.press(MONA, game, "join")
            self.assertEqual(sorted(game["views"]), ["11", "22"])

    def test_group_cpu_posts_a_shared_board(self):
        self.say(ALI, "/cpu", GROUP)
        self.assertEqual(self.latest_game()["mode"], "lobby")

    def test_owner_sets_the_discs_from_a_pack_link(self):
        stickers = [{"emoji": "🔴", "custom_emoji_id": "11"}, {"emoji": "⚫️", "custom_emoji_id": "12"},
                    {"emoji": "🟨", "custom_emoji_id": "13"}, {"emoji": "😀", "custom_emoji_id": "14"}]
        real = self.tg

        def telegram(method, params=None, timeout=45):
            if method == "getStickerSet":
                real.calls.append((method, params))
                return {"ok": True, "result": {"stickers": stickers}} if params["name"] == "C4Pack" else None
            return real(method, params, timeout)

        with mock.patch.object(tg, "api", telegram), mock.patch.dict(bot.cards.CUSTOM_EMOJI):
            reply = self.owner_says("تعيين الايموجي https://t.me/addemoji/C4Pack")
            self.assertIn("3", reply)
            self.assertEqual(bot.cards.CUSTOM_EMOJI[engine.RED], "11")
            self.assertEqual(bot.cards.CUSTOM_EMOJI[engine.EMPTY], "12")
            self.assertEqual(bot.cards.CUSTOM_EMOJI[engine.YELLOW + "_win"], "13")
            self.assertEqual(bot.state["custom_emoji"][engine.RED], "11")
            self.assertIn("🔴  11", self.owner_says("فحص t.me/addemoji/C4Pack"))
            self.owner_says("حذف الايموجي")
            self.assertEqual(bot.cards.CUSTOM_EMOJI[engine.RED], "")

    def test_group_gate_is_an_ephemeral_reply_to_an_ephemeral_command(self):
        bot.state["channel"] = "news"
        with mock.patch.object(bot, "subscribed", return_value=False):
            bot.handle_message({"from": ALI, "chat": GROUP, "text": "/play", "message_id": 7,
                                "ephemeral_message_id": 70})
        method, params = self.tg.calls[-1]
        self.assertEqual(method, "sendRichMessage")
        self.assertEqual(params["reply_parameters"]["ephemeral_message_id"], 70)
        self.assertEqual(params["ephemeral_message_parameters"], {"receiver_user_id": 11})
        self.assertNotIn("style", json.dumps(params["rich_message"]))
        self.assertEqual(bot.state["games"], {})

    def test_group_gate_falls_back_to_a_normal_reply_when_ephemeral_is_refused(self):
        bot.state["channel"] = "news"
        real = self.tg

        def telegram(method, params=None, timeout=45):
            if "ephemeral_message_parameters" in (params or {}):
                real.calls.append((method, params))
                return None
            return real(method, params, timeout)

        with mock.patch.object(bot, "subscribed", return_value=False), mock.patch.object(tg, "api", telegram):
            bot.handle_message({"from": ALI, "chat": GROUP, "text": "/play", "message_id": 7})
        first, second = self.tg.calls[-2][1], self.tg.calls[-1][1]
        self.assertEqual(first["ephemeral_message_parameters"], {"receiver_user_id": 11})
        self.assertNotIn("ephemeral_message_parameters", second)
        self.assertEqual(second["reply_parameters"]["message_id"], 7)

    def test_ephemeral_commands_get_ephemeral_answers(self):
        bot.handle_message({"from": ALI, "chat": GROUP, "text": "/top", "message_id": 8,
                            "ephemeral_message_id": 80})
        params = self.tg.calls[-1][1]
        self.assertEqual(params["ephemeral_message_parameters"], {"receiver_user_id": 11})
        self.assertEqual(params["reply_parameters"]["ephemeral_message_id"], 80)

    def test_pack_with_wrong_tags_is_read_in_upload_order(self):
        stickers = [{"emoji": "🔴", "custom_emoji_id": "e"}, {"emoji": "🔴", "custom_emoji_id": "r"},
                    {"emoji": "🟥", "custom_emoji_id": "rw"}, {"emoji": "🟡", "custom_emoji_id": "y"},
                    {"emoji": "🟨", "custom_emoji_id": "yw"}]
        real = self.tg

        def telegram(method, params=None, timeout=45):
            if method == "getStickerSet":
                return {"ok": True, "result": {"stickers": stickers}}
            return real(method, params, timeout)

        with mock.patch.object(tg, "api", telegram), mock.patch.dict(bot.cards.CUSTOM_EMOJI):
            self.owner_says("تعيين الايموجي t.me/addemoji/PlayConnectX")
            self.assertEqual(bot.state["custom_emoji"], {engine.EMPTY: "e", engine.RED: "r",
                                                          engine.RED + "_win": "rw", engine.YELLOW: "y",
                                                          engine.YELLOW + "_win": "yw"})

    def test_pack_emoji_keep_their_uploaded_emoji_as_fallback(self):
        stickers = [{"emoji": "🔴", "custom_emoji_id": "e"}, {"emoji": "😀", "custom_emoji_id": "r"},
                    {"emoji": "🟥", "custom_emoji_id": "rw"}, {"emoji": "🟡", "custom_emoji_id": "y"},
                    {"emoji": "🟨", "custom_emoji_id": "yw"}]
        real = self.tg

        def telegram(method, params=None, timeout=45):
            if method == "getStickerSet":
                return {"ok": True, "result": {"stickers": stickers}}
            return real(method, params, timeout)

        with mock.patch.object(tg, "api", telegram), mock.patch.dict(bot.cards.CUSTOM_EMOJI), \
                mock.patch.dict(bot.cards.CUSTOM_ALT, clear=True):
            self.owner_says("تعيين الايموجي t.me/addemoji/PlayConnectX")
            self.say(ALI, "/start")
            cells = bot.render(self.latest_game(), True)["blocks"][1]["cells"]
            empty = cells[0][0]["text"]["button"]["text"]
            self.assertEqual((empty["custom_emoji_id"], empty["alternative_text"]), ("e", "🔴"))

    def test_flood_control_retries_the_premium_edit(self):
        real, refused = self.tg, []

        def telegram(method, params=None, timeout=45):
            if method == "editMessageText" and not refused:
                refused.append(params)
                tg.last_error = '{"ok":false,"error_code":429,"parameters":{"retry_after":1}}'
                return None
            return real(method, params, timeout)

        with mock.patch.dict(bot.cards.CUSTOM_EMOJI, {engine.EMPTY: "900"}):
            self.say(ALI, "/start")
            game = self.latest_game()
            with mock.patch.object(tg, "api", telegram), mock.patch.object(bot.time, "sleep") as sleep:
                self.press(ALI, game, "level:hard")
        sleep.assert_called_once_with(1)
        edits = [p for m, p in self.tg.calls if m == "editMessageText"]
        self.assertIn('"900"', json.dumps(edits[-1]["rich_message"]))

if __name__ == "__main__":
    unittest.main()
