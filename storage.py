"""JSON state file with atomic saves."""
import json
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / "state.json"
DEFAULTS = {
    "games": dict, "players": dict, "chat_players": dict, "channel_targets": dict,
    "pending": dict, "next_game": int, "offset": int, "channel": str, "channel_name": str,
}


def load(path=None):
    path = path or STATE_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    for key, factory in DEFAULTS.items():
        value.setdefault(key, factory())
    return value


def save(state, path=None):
    path = path or STATE_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
