from PyQt5.QtCore import QThread, pyqtSignal
import sqlite3, time

class SISQuieis(QThread):
    result_feadback = pyqtSignal(list)
    pic_feadback = pyqtSignal(list)

    def __init__(self, query, flag, parent):
        super().__init__(parent)
        self.query = query
        self.finished.connect(self.deleteLater)
        self.flag = flag

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
            for each in self.query:
                while True:
                    try:
                        result = con.cursor().execute(each).fetchall()
                        print('{} operate done.'.format(each))
                        break
                    except sqlite3.OperationalError:
                        print('Databases busy now, please wait.')
                        time.sleep(3)
                if result and self.flag:
                    if self.flag == 1:
                        self.result_feadback.emit(result)
                    elif self.flag == 2:
                        self.pic_feadback.emit(result)
                con.commit()
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
