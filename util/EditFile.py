import glob
import os

class EditFile:

    def __init__(self, PATH_DOWNLOAD):
        self.PATH_DOWNLOAD = PATH_DOWNLOAD


    def rename(self):
        archive = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R__*.csv"))

        if archive:
            filepath_origin = archive[0]
            filepath_new = os.path.join(self.PATH_DOWNLOAD, "SFN064R.csv")
            os.rename(filepath_origin,filepath_new)
            return

        raise Exception("Não foi possivel alterar o nome")
    
    def remove(self):

        archive = glob.glob(os.path.join(self.PATH_DOWNLOAD, "SFN064R.csv"))

        if (archive != [] and os.path.exists(archive[0])):
            os.remove(archive[0])
        
        raise Exception("Não foi possivel deletar o arquivo")
