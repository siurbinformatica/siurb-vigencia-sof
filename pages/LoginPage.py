from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from time import sleep

from config.settings import SITE_URL,APP_PASSWD,APP_USER

class LoginPage():

    def __init__(self,driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver,30)

    def login(self):
    
        self.driver.get(SITE_URL)

        userLogin = self.wait.until(
            EC.presence_of_element_located((By.ID, "usuario"))
        )

        sleep(0.25)

        userPasswd = self.driver.find_element(by=By.ID, value="senha")
        button = self.wait.until(
            EC.element_to_be_clickable((By.ID, "confirmar"))
        )
          
        userLogin.send_keys(APP_USER)
        userPasswd.send_keys(APP_PASSWD)
        button.click()
