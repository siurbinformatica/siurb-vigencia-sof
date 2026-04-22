from selenium import webdriver
from config.settings import PATH_DOWNLOAD
import os
class BrowserManager:

    def __init__(self):
        if not hasattr(self, "driver"):
            self.driver = webdriver.Chrome(options=self._config())
            # self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            #     "behavior": "allow",
            #     "downloadPath": PATH_DOWNLOAD,
            #     "eventsEnabled": True,
            # })

    def _config(self):

        option = webdriver.ChromeOptions()
        option.add_argument("--headless=new")
        option.add_argument("--disable-gpu")
        option.add_argument("--no-sandbox")
        option.add_argument("--disable-dev-shm-usage")
        option.add_argument("--window-size=1920,1080")
        option.add_argument("--disable-blink-features=AutomationControlled")
        option.add_argument("--ignore-certificate-errors")
        option.add_experimental_option("prefs", {
            "download.default_directory": PATH_DOWNLOAD,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })

        return option

    def quit(self):
        self.driver.quit()
        self.driver = None