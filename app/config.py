from pathlib import Path

APP_NAME = "OpenAI API Communicator"
APP_SLUG = "openai-api-communicator"

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path.home() / f".{APP_SLUG}"
LEGACY_CONFIG_DIR = Path.home() / ".vibetalk"

CONFIG_PATH = CONFIG_DIR / "config.json"
HISTORY_PATH = CONFIG_DIR / "history.json"
LEGACY_CONFIG_PATH = LEGACY_CONFIG_DIR / "config.json"
LEGACY_HISTORY_PATH = LEGACY_CONFIG_DIR / "history.json"

PROMPTS_PATH = APP_DIR / "system-prompts.json"
WRAPPER_PROMPT_PATH = APP_DIR / "wrapper-prompt.json"
MODEL_CATALOG_PATH = APP_DIR / "model-catalog.json"

KEYRING_SERVICE = APP_NAME
KEYRING_USERNAME = "api_key"

CATEGORY_ORDER = [
    "All (Oldest->Newest)",
    "Reasoning",
    "GPT-5",
    "GPT-4",
    "GPT-3.5",
    "Chat",
    "Multimodal",
    "Voice",
    "Audio",
    "Image",
    "Embeddings",
    "Moderation",
    "Fine-tuned",
    "Legacy",
    "Other",
]
