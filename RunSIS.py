import SISUI
import sys
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
    app = QApplication(sys.argv)
    sis = SISUI.SISMainWindow()
    sis.show()
    app.exec_()
    del sis
