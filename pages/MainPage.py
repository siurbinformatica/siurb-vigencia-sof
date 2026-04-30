
from config.settings import PATH_DOWNLOAD
from config.logger import get_logger
from util.DateUtil import DateUtil
from util.EditFile import EditFile

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementNotInteractableException,ElementNotVisibleException,ElementClickInterceptedException,TimeoutException
from time import sleep

import os


class MainPage():

    def __init__(self,driver):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 30)
        self.dateutil = DateUtil()
        self.logger = get_logger(__name__)
        self.edit_file = EditFile(PATH_DOWNLOAD)

    def enterDetailedReservation(self): 
        try:

            bttExecution = self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//i[contains(@class, 'fa-running')]"))
            )

            bttExecution.click()
            
            bttMenuBars = self.driver.find_elements(by=By.XPATH, value="//div[contains(text(), 'Relatório') and contains(@class, 'menubaritem')]")

            bttMenuBars[4].click()

            bttMenuCategory = self.driver.find_elements(by=By.XPATH, value="//div[text()='Reserva']")

            bttMenuCategory[1].click()

            bttMenuItem = self.driver.find_elements(by=By.XPATH, value="//div[text()='Reserva Detalhada']")

            bttMenuItem[0].click()
        
        except TimeoutException as e:
            raise TimeoutException(f"Erro de timeout em enterDetailedReservation, {e}")
        except ElementClickInterceptedException:
            raise ElementClickInterceptedException("Não foi possivel clicar no elemento")
        except ElementNotInteractableException:
            raise ElementNotInteractableException("Não foi possivel interar com o elemento")
        except ElementNotVisibleException:
            raise ElementNotVisibleException("Não foi possivel visualizar o elemento")
        except Exception as e:
            raise Exception(f"Erro inesperado: {e}")

    def downloadExcel(self):
        try:
            
            yesterday = self.dateutil.previousDate()
            today = self.dateutil.todayDate()
            
            periodInitials = self.wait.until(
                EC.presence_of_all_elements_located((By.ID, "UCData"))
            )

            #Coloca a data anterior e atual
            periodInitials[0].send_keys(yesterday)
            periodInitials[1].click()
            periodInitials[1].send_keys(today)

            #Clica no botão reserva
            selectRadioReserve = self.driver.find_element(by=By.XPATH, value="//div[@class='v-input--selection-controls__ripple']")
            selectRadioReserve.click()

            #Clica no radio do executor
            selectRadioExecute = self.driver.find_elements(by=By.XPATH, value="//div[@class='v-input--selection-controls__ripple']")
            selectRadioExecute[2].click()

            self.driver.execute_script("""
                window._fileBase64 = null;
                const origOpen = XMLHttpRequest.prototype.open;
                const origSend = XMLHttpRequest.prototype.send;

                XMLHttpRequest.prototype.open = function(method, url) {
                    this._url = url;
                    return origOpen.apply(this, arguments);
                };

                XMLHttpRequest.prototype.send = function() {
                    if (this._url && this._url.includes('SFN064R')) {
                        this.responseType = 'blob';
                        this.addEventListener('load', function() {
                            const reader = new FileReader();
                            reader.onloadend = function() {
                                window._fileBase64 = reader.result.split(',')[1];
                            };
                            reader.readAsDataURL(this.response);
                        });
                    }
                    return origSend.apply(this, arguments);
                };
            """)

            self.download_archive(today)

        except TimeoutException as e:
            raise TimeoutException(f"Erro de timeout em downloadExcel, {e}")
        except ElementClickInterceptedException:
            raise ElementClickInterceptedException("Não foi possivel clicar no elemento")
        except ElementNotInteractableException:
            raise ElementNotInteractableException("Não foi possivel interar com o elemento")
        except ElementNotVisibleException:
            raise ElementNotVisibleException("Não foi possivel visualizar o elemento")
        except Exception as e:
            raise Exception(f"Erro inesperado: {e}")
    
    def download_archive(self,today):

        #clica no botão de download
        selectExcel = self.driver.find_elements(by=By.XPATH, value="//button[@class='ma-2 v-btn v-btn--outlined v-btn--tile theme--light v-size--default indigo--text']")
        self.driver.execute_script("arguments[0].click();", selectExcel[2])

        sleep(15)

        if (self.edit_file.hasArchiveInPathArchive()): return

        # Aguarda o XHR completar e o base64 ficar disponível
        file_base64 = None
        for _ in range(30):
            sleep(0.5)
            file_base64 = self.driver.execute_script("return window._fileBase64;")
            if file_base64:
                break

        if file_base64:
            import base64
            filename = f"SFN064R__{today.replace("/","-")}.csv"
            filepath = os.path.join(PATH_DOWNLOAD, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(file_base64))

        sleep(15)

    def exit(self):
        try:
            exit = self.driver.find_element(by=By.XPATH, value="//i[@class='vsm--icon fas fa-door-open']")
            exit.click()
            sleep(4)
        except Exception as e:
            self.logger.error("Não foi possivel sair da conta")
            