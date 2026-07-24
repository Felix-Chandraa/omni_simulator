import sys
import threading

from PyQt6.QtWidgets import QApplication

from src.main_window import MainWindow
from src.server import start_server


def main():
    threading.Thread(target=start_server, daemon=True, name="StaticFileServer").start()

    app = QApplication(sys.argv)
    app.setApplicationName("Feather FLight")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
