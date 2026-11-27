"""python main.py          -> GUI fed by skinDetect.py / classic_detector.py
   python main.py --demo   -> GUI with fake camera data"""
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Src")
sys.path.insert(0, SRC)                                  # params.py, skinDetect.py, classic_detector.py

from PySide6.QtWidgets import QApplication

from Gui.controller import GestureGui
from Gui.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    gui = GestureGui()
    gui.quitRequested.connect(app.quit)
    app.aboutToQuit.connect(gui.save_now)
    gui.show()
    gui.start_backend()                       # calls skinDetect.py / classic_detector.py functions
    app.aboutToQuit.connect(gui.stop_backend)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
