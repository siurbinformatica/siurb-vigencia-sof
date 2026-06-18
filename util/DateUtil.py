from datetime import date
from datetime import timedelta

class DateUtil:

    data = date

    def previousDate(self) -> str:
        
        yesterday = "01/01/2026"
        
        # if (str(self.data.today().strftime('%A')) == "Monday"):
        #     yesterday = (self.data.today() - timedelta(days=+3)).strftime("%d/%m/%G")
        # else:
        #     yesterday = (self.data.today() - timedelta(days=+1)).strftime("%d/%m/%G")

        return str(yesterday)
    
    def previousDateLog(self,format_date) -> str:
        
        yesterday = ""
        yesterday = (self.data.today() - timedelta(days=+1)).strftime(format_date)
        return str(yesterday)
    
    def year(self) -> str:

        today = self.data.today().strftime("%G")

        return str(today)

