import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPainterPath
from PyQt5.QtCore import Qt
import app.database as db
from app.main_window import MainWindow
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'X-ScoreHub.png')


def main():
    db.init_db()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    if os.path.exists(ICON_FILE):
        src = QPixmap(ICON_FILE).scaled(256, 256, Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)
        # Render with rounded-rect mask for macOS-style icon
        rounded = QPixmap(src.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        r = src.width() * 0.2  # corner radius ~20% of icon size
        path.addRoundedRect(0, 0, src.width(), src.height(), r, r)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src)
        painter.end()
        app.setWindowIcon(QIcon(rounded))

    # Apply basic stylesheet
    app.setStyleSheet('''
        QMainWindow { background-color: #f5f5f5; }
        QListWidget { font-size: 14px; }
        QListWidget::item { padding: 4px; }
        QListWidget::item:selected { background-color: #4a90d9; color: white; }
        QLineEdit { padding: 4px; font-size: 13px; }
        QComboBox { padding: 2px; font-size: 13px; }
        QPushButton { padding: 4px 12px; font-size: 13px; }
    ''')

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
