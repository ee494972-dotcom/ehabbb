"""Thin Telegram Bot API client using only the standard library."""
import json
import urllib.error
import urllib.parse
import urllib.request

_token = ""


def configure(token):
    global _token
    _token = token


def api(method, params=None, timeout=45):
    payload = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
               for key, value in (params or {}).items()}
    request = urllib.request.Request(f"https://api.telegram.org/bot{_token}/{method}",
                                     data=urllib.parse.urlencode(payload).encode())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode())
        return result if result.get("ok") else None
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        print(f"api {method} failed: HTTP {exc.code}: {detail}", flush=True)
        return None
    except Exception as exc:
        print(f"api {method} failed: {exc}", flush=True)
        return None


def rich_send(chat_id, rich, reply_markup=None):
    params = {"chat_id": chat_id, "rich_message": rich}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return api("sendRichMessage", params)


def rich_edit(chat_id, message_id, rich):
    return api("editMessageText", {"chat_id": chat_id, "message_id": message_id, "rich_message": rich})


def rich_ephemeral_send(chat_id, user_id, callback_query_id, rich):
    return api("sendRichMessage", {
        "chat_id": chat_id,
        "rich_message": rich,
        "ephemeral_message_parameters": {
            "receiver_user_id": user_id,
            "callback_query_id": callback_query_id,
            "replace_callback_query_message": True,
        },
    })


def rich_ephemeral_edit(chat_id, user_id, ephemeral_message_id, rich):
    return api("editEphemeralMessageText", {
        "chat_id": chat_id,
        "receiver_user_id": user_id,
        "ephemeral_message_id": ephemeral_message_id,
        "rich_message": rich,
    })


def text_send(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return api("sendMessage", params)


def answer(query_id, text="", alert=False):
    api("answerCallbackQuery", {"callback_query_id": query_id, "text": text, "show_alert": alert})
