"""python main.py          -> GUI only (project feeds it frames)
   python main.py --demo   -> GUI with fake camera data"""
import sys

from PySide6.QtWidgets import QApplication

from controller import GestureGui
from theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    gui = GestureGui()
    gui.quitRequested.connect(app.quit)
    app.aboutToQuit.connect(gui.save_now)
    gui.show()
    if "--demo" in sys.argv:
        from demo import Demo
        gui._demo = Demo(gui)
    else:
        gui.start_backend()                       # calls skinDetect.py / classic_detector.py functions
        app.aboutToQuit.connect(gui.stop_backend)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
