import sys
import ctypes
import re
import requests
from PyQt5.QtWidgets import QApplication, QWidget, QTextBrowser, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt, pyqtSlot, QPoint, QThread, pyqtSignal

class LinkPreviewThread(QThread):
    """Fetches link preview data in background"""
    preview_ready = pyqtSignal(str, str, str)  # url, title, description
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.daemon = True
    
    def run(self):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=5)
            response.raise_for_status()
            
            html = response.text
            
            # Extract title
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1)[:100] if title_match else "Link Preview"
            
            # Extract description from og:description or meta description
            desc_match = re.search(
                r'<meta\s+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
                html, re.IGNORECASE
            )
            if not desc_match:
                desc_match = re.search(
                    r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
                    html, re.IGNORECASE
                )
            description = desc_match.group(1)[:150] if desc_match else ""
            
            self.preview_ready.emit(self.url, title, description)
        except Exception as e:
            pass

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
        self.message_map = {}  # Maps message_id -> html snippet
        self.link_preview_threads = {}  # Maps url -> thread
        self.show_link_previews = True
        self.next_msg_id = 0

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
        print(f"OVERLAY received: {html[:50]}...")
        msg_id = self.next_msg_id
        self.next_msg_id += 1
        
        # Wrap message in a div with ID for removal
        wrapped_html = f'<div id="msg_{msg_id}">{html}</div>'
        self.message_map[msg_id] = wrapped_html
        
        # Check for URLs and fetch previews if enabled
        if self.show_link_previews:
            url_pattern = r'https?://[^\s<>]+'
            urls = re.findall(url_pattern, html)
            for url in urls[:1]:  # Limit to 1 preview per message
                if url not in self.link_preview_threads:
                    thread = LinkPreviewThread(url)
                    thread.preview_ready.connect(lambda u, t, d: self._insert_link_preview(u, t, d))
                    thread.start()
                    self.link_preview_threads[url] = thread
        
        self.chat_display.append(wrapped_html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def _insert_link_preview(self, url, title, description):
        """Insert a link preview after URL is fetched"""
        if not title or not description:
            return
        preview_html = (
            f'<div style="margin-left: 20px; padding: 8px; background-color: rgba(100,100,100,0.3); '
            f'border-left: 3px solid #888; font-size: 11px; margin-top: 4px;">'
            f'<b>{title}</b><br/>{description}'
            f'</div>'
        )
        self.chat_display.append(preview_html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def remove_message(self, msg_id):
        """Remove a message by ID (for moderator deletions)"""
        if msg_id not in self.message_map:
            return
        # Get the HTML document
        doc = self.chat_display.document()
        # Find and remove the message div
        cursor = self.chat_display.textCursor()
        cursor.select(self.chat_display.textCursor().Document)
        html = self.chat_display.toHtml()
        # Remove the message div
        pattern = f'<div id="msg_{msg_id}">[^<]*(?:<[^>]*>[^<]*)*</div>'
        html = re.sub(pattern, '', html, flags=re.DOTALL)
        self.chat_display.setHtml(html)
        del self.message_map[msg_id]

    def remove_message_by_user(self, username):
        """Remove all messages from a specific user (for mod action)"""
        pattern = f'<span[^>]*><b>{re.escape(username)}</b></span>'
        html = self.chat_display.toHtml()
        original_length = len(html)
        html = re.sub(pattern + '[^<]*(?:<[^>]*>[^<]*)*(?=<div|$)', '', html, flags=re.DOTALL)
        if len(html) != original_length:
            self.chat_display.setHtml(html)

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