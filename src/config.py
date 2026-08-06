import os
from pathlib import Path

import _bootstrap

_bootstrap.ensure_scrapekit()

from scrapekit.env import imap_settings, load_env_file

ROOT = Path(__file__).resolve().parent.parent
LOCAL_ENV_PATH = Path(__file__).resolve().parent / ".env.local"

# Audi TT Mk2 (8J) engines commonly listed for 2006–2010.
ENGINE_OPTIONS = [
    {"id": "1.8_tfsi", "label": "1.8 TFSI", "patterns": ["1.8", "1,8", "18 tfsi", "1.8 tfsi"]},
    {"id": "2.0_tfsi", "label": "2.0 TFSI", "patterns": ["2.0 tfsi", "2,0 tfsi", "20 tfsi", "2.0tsi", "2.0 tsi"]},
    {"id": "2.0_tdi", "label": "2.0 TDI", "patterns": ["2.0 tdi", "2,0 tdi", "20 tdi", "tdi"]},
    {"id": "3.2_v6", "label": "3.2 V6", "patterns": ["3.2", "3,2", "v6", "3.2 v6"]},
    {"id": "tts", "label": "TTS", "patterns": ["tts"]},
    {"id": "ttrs", "label": "TT RS", "patterns": ["tt rs", "ttrs", "tt-rs", "2.5"]},
]

load_env_file(LOCAL_ENV_PATH)

DATA_DIR = Path(os.environ.get("AUDIT_DATA_DIR", str(ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

LISTINGS_JSON_PATH = ROOT / "docs" / "data" / "listings.json"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_imap = imap_settings()
IMAP_EMAIL_ACCOUNT = _imap["account"]
IMAP_EMAIL_PASSWORD = _imap["password"]
IMAP_SERVER = _imap["server"]
IMAP_PORT = _imap["port"]
IMAP_MAILBOX = _imap["mailbox"]
IMAP_MAX_EMAILS = _imap["max_emails"]

FILTERS = {
    "year_min": 2006,
    "year_max": 2010,
    "engines": [e["id"] for e in ENGINE_OPTIONS],
    "price_max": 25000,
    "keywords": ["audi", "tt"],
}
