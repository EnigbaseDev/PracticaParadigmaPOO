import sys
from PyQt6.QtWidgets import QApplication
from ui_app import AppWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())