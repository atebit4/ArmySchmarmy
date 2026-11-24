import os
import sys
from pathlib import Path

# Suppress the Wayland text-input warning seen on some Linux desktops.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.wayland.textinput.warning=false")

from PyQt6 import uic
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi(str(Path(__file__).with_name("mainscreen.ui")), self)

        # button sits above both panels instead of inside either layout.
        self.build_button = QPushButton("Build\nArmy", self.centralwidget)
        self.build_button.setObjectName("buildButton")
        self.build_button.setFixedSize(120, 120)
        self.build_button.setStyleSheet("""
            QPushButton {
                border-radius: 60px;
                border: 3px solid #d5b879;
                background-color: #59442a;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #80613a; }
            QPushButton:pressed { background-color: #3e301f; }
        """)
        self.build_button.clicked.connect(self.build_army)
        self.sendButton.clicked.connect(self.send_message)
        self.messageInput.returnPressed.connect(self.send_message)
        self.addUnitButton.clicked.connect(self.add_unit)
        self.statusBar().showMessage("Ready")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        #wait until Qt has laid out both panels before reading their positions
        QTimer.singleShot(0, self.position_build_button)

    def position_build_button(self):
        #follow the divider as the window changes size, about one third down
        divider = self.armyPanel.mapTo(self.centralwidget, self.armyPanel.rect().topLeft()).x()
        x = divider - self.build_button.width() // 2
        y = self.centralwidget.height() // 3 - self.build_button.height() // 2
        self.build_button.move(x, y)
        self.build_button.raise_()

    def build_army(self):
        self.statusBar().showMessage("Army building will be connected here.", 5000)

    def send_message(self):
        message = self.messageInput.text().strip()
        if message:
            self.chatHistory.insertPlainText("You: " + message + "\n")
            self.messageInput.clear()
            self.statusBar().showMessage("AI chat is not connected yet.", 5000)

    def add_unit(self):
        self.statusBar().showMessage("Manual unit selection will be added here.", 5000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
