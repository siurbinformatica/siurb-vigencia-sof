import dotenv
import os

PATH = os.path.join("C:/Project/AutomaticSOF/", ".env")

dotenv.load_dotenv(PATH)

USER = os.getenv("USER")
PASSWD = os.getenv("PASSWD")
SITE_URL = os.getenv("SITE_URL")
PATH_DOWNLOAD = os.getenv("PATH_DOWNLOAD")
