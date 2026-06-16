import os
from pathlib import Path

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "123456789").split(",") if x.strip()]

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "habesha_bet.db"
AUDIO_DIR = BASE_DIR / "audio"

ROOMS = {
    10: {"fee": 10, "label_en": "10 ETB", "label_am": "10 ብር"},
    20: {"fee": 20, "label_en": "20 ETB", "label_am": "20 ብር"},
    50: {"fee": 50, "label_en": "50 ETB", "label_am": "50 ብር"},
    100: {"fee": 100, "label_en": "100 ETB", "label_am": "100 ብር"},
}

CARDS_PER_ROOM = 200
MAX_CARDS_PER_PLAYER = 5
HOUSE_COMMISSION = 0.20
CALL_INTERVAL = 2
MAX_NUMBERS = 75
COUNTDOWN_SECONDS = 60

MIN_DEPOSIT = 20
MIN_WITHDRAWAL = 30
MIN_TRANSFER = 10
TRANSFER_COOLDOWN = 3600

DEPOSIT_ACCOUNTS = [
    {"name": "Abebe K.", "phone": "0911000001", "last4": "0001"},
    {"name": "Bekele T.", "phone": "0911000002", "last4": "0002"},
    {"name": "Chaltu A.", "phone": "0911000003", "last4": "0003"},
]
DEPOSIT_ACCOUNT_ROTATION_INTERVAL = 20

REFERRAL_BONUS = 5
REFERRAL_BONUS_PERCENT = 0.05