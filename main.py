import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from robot import SimBridge
from gui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    sim = SimBridge()
    window = MainWindow(sim=sim)
    window.show()

    QTimer.singleShot(200, sim.start_sim)

    ret = app.exec_()
    sim.stop()
    sys.exit(ret)


if __name__ == "__main__":
    main()
