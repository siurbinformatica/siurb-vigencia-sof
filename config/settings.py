import dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

dotenv.load_dotenv(BASE_DIR / ".env")

APP_USER = os.getenv("APP_USER")
PATH_PASSWORD = os.getenv("PATH_PASSWORD")
SITE_URL = os.getenv("SITE_URL")
PATH_DOWNLOAD = os.getenv("PATH_DOWNLOAD")
LOG_PATH = os.getenv("LOG_PATH")