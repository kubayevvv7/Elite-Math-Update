import os
import logging
from dotenv import load_dotenv
import telebot

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN .env da topilmadi")

try:
    from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
    HAS_TOOLBELT = True
except Exception:
    HAS_TOOLBELT = False

# Config
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_FILE = os.getenv("DB_FILE", "data.db")
VIDEOS_FOLDER = os.getenv("VIDEOS_FOLDER", "videos")
POLLING = os.getenv("BOT_POLLING", "1") == "1"

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Bot instance
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Global state
user_state = {}
user_profiles = {}

# Create videos folder if not exists
if VIDEOS_FOLDER and not os.path.exists(VIDEOS_FOLDER):
    os.makedirs(VIDEOS_FOLDER, exist_ok=True)

