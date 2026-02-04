import json
import os
import time
import uuid

try:
    import keyring
except Exception:
    keyring = None

from .config import (
    CONFIG_DIR,
    CONFIG_PATH,
    HISTORY_PATH,
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    LEGACY_CONFIG_PATH,
    LEGACY_HISTORY_PATH,
)


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def _save_json(path, data):
    _ensure_config_dir()
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def normalize_models_cache(raw):
    updated_at = ""
    if isinstance(raw, dict) and "models" in raw:
        models = raw.get("models", [])
        updated_at = raw.get("updated_at", "")
    elif isinstance(raw, list):
        models = raw
    elif isinstance(raw, dict):
        model_ids = set()
        for value in raw.values():
            if isinstance(value, list):
                model_ids.update(value)
        models = [{"id": model_id} for model_id in sorted(model_ids)]
    else:
        models = []

    normalized = []
    for item in models:
        if isinstance(item, str):
            model_id = item
            created = None
        elif isinstance(item, dict):
            model_id = item.get("id")
            created = item.get("created")
        else:
            continue
        if model_id:
            normalized.append({"id": model_id, "created": created})
    return {"models": normalized, "updated_at": updated_at}


def load_config():
    data = _read_json(CONFIG_PATH)
    if data is None:
        data = _read_json(LEGACY_CONFIG_PATH) or {}
    cache = normalize_models_cache(data.get("models_cache"))
    config = {
        "api_key": data.get("api_key", ""),
        "use_keyring": data.get("use_keyring", False),
        "use_wrapper_prompt": data.get("use_wrapper_prompt"),
        "system_prompt": data.get("system_prompt", ""),
        "prompt_id": data.get("prompt_id", ""),
        "category": data.get("category", "All (Oldest->Newest)"),
        "model": data.get("model", ""),
        "models_cache": cache["models"],
        "models_cache_updated_at": data.get(
            "models_cache_updated_at", cache["updated_at"]
        ),
    }
    return config


def save_config(config):
    _save_json(CONFIG_PATH, config)


def _derive_title(messages):
    for message in messages:
        if message.get("role") == "user":
            content = (message.get("content") or "").strip()
            if not content:
                continue
            title = content.splitlines()[0].strip()
            if len(title) > 60:
                return f"{title[:57]}..."
            return title
    return "New Chat"


def new_conversation(model=""):
    now = _now_iso()
    convo = {
        "id": uuid.uuid4().hex,
        "title": "New Chat",
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "model": model,
        "models_used": [model] if model else [],
    }
    return convo


def _normalize_conversation(convo):
    if not isinstance(convo, dict):
        return None
    if not convo.get("id"):
        convo["id"] = uuid.uuid4().hex
    convo.setdefault("title", "New Chat")
    convo.setdefault("created_at", _now_iso())
    convo.setdefault("updated_at", convo.get("created_at", _now_iso()))
    messages = convo.get("messages")
    if not isinstance(messages, list):
        convo["messages"] = []
    convo.setdefault("model", "")
    models_used = convo.get("models_used")
    if not isinstance(models_used, list):
        convo["models_used"] = []
    return convo


def load_conversations(config=None):
    data = _read_json(HISTORY_PATH)
    if data is None:
        data = _read_json(LEGACY_HISTORY_PATH)

    conversations = []
    active_id = ""

    if isinstance(data, dict) and "conversations" in data:
        conversations = data.get("conversations", []) or []
        active_id = data.get("active_conversation_id", "")
    elif isinstance(data, dict) and "messages" in data:
        model = ""
        if config:
            model = config.get("model", "")
        convo = new_conversation(model=model)
        messages = data.get("messages", []) or []
        convo["messages"] = messages
        convo["title"] = _derive_title(messages)
        convo["updated_at"] = data.get("updated_at", _now_iso())
        conversations = [convo]
        active_id = convo["id"]

    if not isinstance(conversations, list):
        conversations = []

    normalized = []
    for convo in conversations:
        normalized_convo = _normalize_conversation(convo)
        if normalized_convo:
            normalized.append(normalized_convo)

    conversations = normalized

    return conversations, active_id


def save_conversations(conversations, active_id=""):
    payload = {
        "version": 2,
        "updated_at": _now_iso(),
        "active_conversation_id": active_id,
        "conversations": conversations,
    }
    _save_json(HISTORY_PATH, payload)


def get_keyring_api_key():
    if keyring is None:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ""
    except Exception:
        return ""


def store_api_key(config, api_key):
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)
            config["use_keyring"] = True
            config["api_key"] = ""
            save_config(config)
            return "keyring"
        except Exception:
            pass
    config["use_keyring"] = False
    config["api_key"] = api_key
    save_config(config)
    return "config"


def resolve_api_key(config, override="", prefer_env=True):
    if override:
        return override.strip()
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if prefer_env and env_key:
        return env_key
    config_key = config.get("api_key", "").strip()
    use_keyring = config.get("use_keyring")
    if use_keyring is True:
        keyring_key = get_keyring_api_key()
        if keyring_key:
            return keyring_key
    if config_key:
        return config_key
    keyring_key = get_keyring_api_key()
    if keyring_key:
        return keyring_key
    if not prefer_env and env_key:
        return env_key
    return ""
