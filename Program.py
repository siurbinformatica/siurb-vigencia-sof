from config.settings import PATH_DOWNLOAD
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

    def run(self):
        try:    
            self.loginPage.login()
            self.confirmPage.confirm()
            self.mainPage.enterDetailedReservation()
            self.mainPage.downloadExcel()
            self.editFile.remove()
            self.editFile.rename()
        except Exception as e:
            print(e)
        finally:
            self.mainPage.exit() 
        