
from util.DateUtil import DateUtil
from datetime import date
from config.settings import LOG_PATH
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
        
        if (archive == []):
            self.logger.info("Não foi possivel deletar o arquivo")
            return
        
        os.remove(archive[0])
        
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

    def is_remove_archive_in_path(self) -> bool:
        path_archive = os.path.join(self.PATH_DOWNLOAD, "SFN064R.csv")
        if (os.path.exists(path_archive)): return False
        return True
