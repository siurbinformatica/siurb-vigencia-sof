
from util.DateUtil import DateUtil
from datetime import date
from config.settings import LOG_PATH
import time
import glob
import os

class EditFile:

    def __init__(self, PATH_DOWNLOAD):
        from config.logger import get_logger
        from config.logger import get_logger_save_archive
    
        self.PATH_DOWNLOAD = PATH_DOWNLOAD
        self.logger_archive = get_logger_save_archive()
        self.logger = get_logger(__name__)
        self.date_util = DateUtil()

    def rename(self):
        archive = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R__*.csv"))

        if archive:
            filepath_origin = archive[0]
            filepath_new = os.path.join(self.PATH_DOWNLOAD, "SFN064R.csv")
            os.rename(filepath_origin,filepath_new)
            self.delete_last_log()
            self.logger_archive.info("Arquivo criado com sucesso!")
            return

        raise Exception("Não foi possivel alterar o nome")
    
    def remove(self):

        archive = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R.csv"))
        
        if not archive:
            self.logger.info("Arquivo SFN064R.csv não encontrado, nada a remover.")
            return
        
        os.remove(archive[0])
        self.logger.info("Arquivo SFN064R.csv removido com sucesso.")

    def delete_last_log(self):

        yesterday = self.date_util.previousDateLog("%Y-%m-%d")
        path = os.path.join(LOG_PATH, f"log-archive-{yesterday}.log")

        if (os.path.exists(path)):
            os.remove(path)
        else:
            self.logger.info("arquivo nao encontrado")

    def hasArchiveInPathArchive(self) -> bool:
        archives = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R__*.csv"))
        if (archives == []): return False
        return True

    def wait_for_download(self, timeout: int = 30) -> bool:

        elapsed = 0
        last_size = -1

        while elapsed < timeout:
            time.sleep(1)
            elapsed += 1

            if not self.hasArchiveInPathArchive():
                continue

            # Garante que não há arquivo temporário do Chrome ainda ativo
            tmp_files = (
                glob.glob(os.path.join(self.PATH_DOWNLOAD, "*.crdownload")) +
                glob.glob(os.path.join(self.PATH_DOWNLOAD, "*.tmp"))
            )
            if tmp_files:
                continue

            # Garante que o tamanho do arquivo está estável (não está sendo escrito)
            archives = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R__*.csv"))
            current_size = os.path.getsize(archives[0])

            if current_size == last_size and current_size > 0:
                return True

            last_size = current_size

        return False