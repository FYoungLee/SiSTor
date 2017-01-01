import SISUI
import sys
from PyQt5.QtWidgets import QApplication

if __name__ == '__main__':
	try:
		app = QApplication(sys.argv)    
		sis = SISUI.SISMainWindow()
		sis.show()
		app.exec_()
	except BaseException as err:
		print(err)
	finally:
	    del sis
