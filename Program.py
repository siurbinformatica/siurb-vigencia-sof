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
            self.logger.info(f"PATH_DOWNLOAD: {self.editFile.PATH_DOWNLOAD}")
            self.login()
            self.downloadArchive()
            self.mainPage.exit() 
            self.logger.info("Bot terminou sua tarefa")
        except Exception as e:
            self.logger.error(f"Erro inesperado: {e}", exc_info=False)

    def login(self):
        try:
            self.loginPage.login()
            isLogged = self.loginPage.isLogged()
            if (not isLogged[0]):
                raise Exception(isLogged[1])
            self.editFile.remove()
            self.confirmPage.confirm()
        except Exception as e:
            self.logger.error(e, exc_info=True)
            raise Exception(e)

    def downloadArchive(self):
        
        try:
            self.mainPage.enterContract()
            self.mainPage.downloadExcel()
            if not self.editFile.wait_for_download(timeout=60):
                raise Exception("Timeout: arquivo SFN064R__*.csv não encontrado após 60s")
            self.editFile.rename()
        except Exception as e:
            self.mainPage.exit()
            self.logger.error(e, exc_info=True)
            raise Exception(e)