"""Thin Telegram Bot API client using only the standard library."""
import json
import urllib.error
import urllib.parse
import urllib.request

_token = ""
last_error = ""


def configure(token):
    global _token
    _token = token


def api(method, params=None, timeout=45):
    global last_error
    last_error = ""
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
        last_error = detail
        print(f"api {method} failed: HTTP {exc.code}: {detail}", flush=True)
        return None
    except Exception as exc:
        print(f"api {method} failed: {exc}", flush=True)
        return None


def with_reply(params, reply):
    """Add reply options: message_id or ephemeral_message_id to reply to, and receiver_user_id
    to make the message ephemeral (visible only to that user in a group)."""
    if not reply:
        return params
    target = {key: reply[key] for key in ("message_id", "ephemeral_message_id") if reply.get(key)}
    if target:
        params["reply_parameters"] = {**target, "allow_sending_without_reply": True}
    if reply.get("receiver_user_id"):
        params["ephemeral_message_parameters"] = {"receiver_user_id": reply["receiver_user_id"]}
    return params


def rich_send(chat_id, rich, reply_markup=None, reply=None):
    params = {"chat_id": chat_id, "rich_message": rich}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return api("sendRichMessage", with_reply(params, reply))


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


def text_send(chat_id, text, reply_markup=None, reply=None):
    params = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        params["reply_markup"] = reply_markup
    return api("sendMessage", with_reply(params, reply))


def answer(query_id, text="", alert=False):
    api("answerCallbackQuery", {"callback_query_id": query_id, "text": text, "show_alert": alert})
