import sys
import ctypes
from PyQt5.QtWidgets import QWidget, QTextBrowser, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSlot, QPoint

class ChatOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.drag_handle = QLabel("⁝⁝ DRAG TO MOVE ⁝⁝")
        self.drag_handle.setAlignment(Qt.AlignCenter)
        self.drag_handle.setStyleSheet("background-color: #9146FF; color: white; font-weight: bold; padding: 8px;")
        self.drag_handle.hide() 
        
        self.chat_display = QTextBrowser()
        self.chat_display.setReadOnly(True)
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_display.setStyleSheet("background-color: rgba(15, 15, 18, 255); border: none;")
        
        self.layout.addWidget(self.drag_handle)
        self.layout.addWidget(self.chat_display)
        self.resize(400, 600)
        self.old_pos = None

    def set_click_through(self, enabled):
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        if enabled:
            self.drag_handle.hide()
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
        else:
            self.drag_handle.show()
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style & ~0x20)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    @pyqtSlot(str)
    def add_message(self, html):
        self.chat_display.append(html)
        scroll_bar = self.chat_display.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def update_style(self, font_size, opacity):
        self.setWindowOpacity(max(0.01, opacity))
        self.chat_display.setStyleSheet(f"""
            QTextBrowser {{
                background-color: rgba(15, 15, 18, 255); 
                color: white;
                font-size: {font_size}px;
                font-family: 'Segoe UI';
                font-weight: bold;
                border: none;
                padding: 10px;
            }}
        """)