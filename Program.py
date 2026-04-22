from config.settings import PATH_DOWNLOAD
from config.logger import get_logger
from manager.BrowserManager import BrowserManager
from pages.ConfirmPage import ConfirmPage
from pages.LoginPage import LoginPage
from pages.MainPage import MainPage
from util.EditFile import EditFile

class Program:
    
    def __init__(self):
        self.browser = BrowserManager()
        self.confirmPage = ConfirmPage(self.browser.driver)
        self.loginPage = LoginPage(self.browser.driver)
        self.mainPage = MainPage(self.browser.driver)
        self.editFile = EditFile(PATH_DOWNLOAD)
        self.logger = get_logger(__name__)

    def run(self):
        try:    
            self.logger.info("Bot iniciado")
            self.loginPage.login()
            self.confirmPage.confirm()
            self.mainPage.enterDetailedReservation()
            self.mainPage.downloadExcel()
            self.editFile.remove()
            self.editFile.rename()
            self.mainPage.exit() 
            self.logger.info("Bot terminou sua tarefa")
        except Exception as e:
            self.logger.error(f"Erro inesperado: {e}", exc_info=True)
            self.mainPage.exit() 
        finally:
            self.browser.quit()
        