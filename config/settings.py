import dotenv
import os

PATH = os.path.join("/root/SiurbAutoSOF/", ".env")

dotenv.load_dotenv(PATH)

APP_USER = os.getenv("APP_USER")
APP_PASSWD = os.getenv("APP_PASSWD")
SITE_URL = os.getenv("SITE_URL")
PATH_DOWNLOAD = os.getenv("PATH_DOWNLOAD")
