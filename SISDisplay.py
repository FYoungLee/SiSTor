from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime
import sqlite3

class SISQuieis(QThread):
    result_feadback = pyqtSignal(list)

    def __init__(self, query, parent):
        super().__init__(parent)
        self.query = query

    def run(self):
        # dateList = [datetime(2100, 1, 1).timestamp()]
        # for each in range(2020, 2020, -2):
        #     dateList.append(datetime(each, 1, 1).timestamp())
        # dateList.append(datetime(1971, 1, 1).timestamp())
        # queries = []
        # kw = 'WHERE'
        # if 'WHERE' in self.query:
        #     kw = 'AND'
        # for each in range(1, len(dateList)):
        #     queries.append(self.query + ' {} date<={} AND date>{}'.format(kw, dateList[each - 1], dateList[each]))
        con = sqlite3.connect('SISDB.sqlite')
        try:
            result = con.cursor().execute(self.query).fetchall()
            if result:
                self.result_feadback.emit(result)
        finally:
            con.close()
        # for each in queries:
        #     try:
        #         result = con.cursor().execute(each).fetchall()
        #     except sqlite3.OperationalError as err:
        #         print(err)
        #         continue
        #     if len(result) == 0:
        #         continue
        #     self.result_feadback.emit(result)
