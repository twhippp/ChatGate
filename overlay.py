import sys
import ctypes
from PyQt5.QtWidgets import QApplication, QWidget, QTextBrowser, QVBoxLayout, QLabel
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

        # DRAG HANDLE (Visible only when setting up)
        self.drag_handle = QLabel("⁝⁝ DRAG TO MOVE ⁝⁝")
        self.drag_handle.setAlignment(Qt.AlignCenter)
        self.drag_handle.setStyleSheet("""
            background-color: rgba(145, 70, 255, 180); 
            color: white; 
            font-weight: bold; 
            padding: 5px;
        """)
        self.drag_handle.hide() # Hidden by default
        
        self.chat_display = QTextBrowser()
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_display.setStyleSheet("background: transparent; border: none;")
        
        self.layout.addWidget(self.drag_handle)
        self.layout.addWidget(self.chat_display)
        
        self.resize(400, 600)
        self.old_pos = None

    def set_click_through(self, enabled):
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        if enabled:
            self.drag_handle.hide()
            # Win32: make the window layered + transparent to input
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            # Qt: also mark child widgets so Qt doesn't eat mouse events
            self.chat_display.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.drag_handle.show()
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style & ~0x20)
            self.chat_display.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    # Mouse logic to allow dragging the frameless window
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
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def update_style(self, font_size, opacity):
        rgba = f"rgba(0, 0, 0, {int(opacity * 255)})"
        self.chat_display.setStyleSheet(f"""
            QTextBrowser {{
                background-color: {rgba};
                color: white;
                font-size: {font_size}px;
                font-family: 'Segoe UI';
                font-weight: bold;
                border: none;
            }}
        """)