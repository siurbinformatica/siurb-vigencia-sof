
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from time import sleep

class ConfirmPage():

    def __init__(self,driver):
        
        self.driver = driver    
        self.wait = WebDriverWait(self.driver, 30)

    def confirm(self):
        
        sleep(12)

        button = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'field-input')]"))
        )

        self.driver.execute_script("arguments[0].click()", button)
        sleep(10)
        