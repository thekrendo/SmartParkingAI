## main.py
import sys
from PySide6.QtWidgets import QApplication
import qdarktheme
from main_window import ParkFinderApp

def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    parkfinder = ParkFinderApp()
    parkfinder.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()