import sys
import ctypes
import re
import requests
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSlot, QPoint, QThread, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QColor


class TransparentWebEnginePage(QWebEnginePage):
    """Custom webpage that supports transparent background"""
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        return True
    
    def javaScriptConsoleMessage(self, level, message, line, source):
        pass


class ChatOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        # Don't use WA_TranslucentBackground with WebEngine - it can cause issues
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.drag_handle = QLabel("DRAG TO MOVE")
        self.drag_handle.setAlignment(Qt.AlignCenter)
        self.drag_handle.setFixedHeight(20)
        self.drag_handle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.drag_handle.setStyleSheet("""
            background-color: rgba(145, 70, 255, 180); 
            color: white; 
            font-weight: bold; 
            font-size: 10px;
        """)
        self.drag_handle.hide()
        
        self.chat_display = QWebEngineView()
        self.page = TransparentWebEnginePage()
        self.chat_display.setPage(self.page)
        
        self.chat_display.setStyleSheet("background: transparent;")
        self.chat_display.page().setBackgroundColor(QColor(0, 0, 0, 0))
        
        self.layout.addWidget(self.drag_handle)
        self.layout.addWidget(self.chat_display)
        
        self.resize(400, 600)
        self.old_pos = None
        self.message_map = {}
        self.link_preview_threads = {}
        self.show_link_previews = True
        self.next_msg_id = 0
        
        self._html_content = ""
        self._font_size = 14
        self._opacity = 0.5
        
        self._set_html("")

    def setWindowOpacity(self, opacity):
        super().setWindowOpacity(opacity)
        # Force repaint
        self.update()
        self.chat_display.repaint()

    def update_style(self, font_size, opacity):
        self._font_size = font_size
        self._opacity = opacity
        self._set_html(self._html_content)

    def set_click_through(self, enabled):
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        if enabled:
            self.drag_handle.hide()
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            self.chat_display.page().runJavaScript("document.body.style.pointerEvents = 'none';")
        else:
            self.drag_handle.show()
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style & ~0x20)
            self.chat_display.page().runJavaScript("document.body.style.pointerEvents = 'auto';")

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

    def _set_html(self, html):
        self._html_content = html
        font_size = getattr(self, '_font_size', 14)
        opacity = getattr(self, '_opacity', 0.5)
        rgba = f"rgba(0, 0, 0, {int(opacity * 255)})"
        
        base_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            html, body {{
                background-color: {rgba};
                color: white;
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: {font_size}px;
                margin: 0;
                padding: 4px;
                overflow: hidden;
            }}
            div {{ margin-bottom: 2px; }}
            a {{ color: #4da6ff; }}
            img {{ vertical-align: middle; }}
        </style>
        </head>
        <body>
        {html}
        </body>
        </html>
        """
        self.chat_display.setHtml(base_html)

    def _append_html(self, html):
        self._html_content += html
        self._set_html(self._html_content)

    @pyqtSlot(str)
    def add_message(self, html):
        msg_id = self.next_msg_id
        self.next_msg_id += 1
        
        wrapped_html = f'<div id="msg_{msg_id}">{html}</div>'
        self.message_map[msg_id] = wrapped_html
        
        if self.show_link_previews:
            url_pattern = r'https?://[^\s<>]+'
            urls = re.findall(url_pattern, html)
            for url in urls[:1]:
                if url not in self.link_preview_threads:
                    thread = LinkPreviewThread(url)
                    thread.preview_ready.connect(lambda u, t, d: self._insert_link_preview(u, t, d))
                    thread.start()
                    self.link_preview_threads[url] = thread
        
        self._append_html(wrapped_html)
        self.chat_display.page().runJavaScript("window.scrollTo(0, document.body.scrollHeight);")

    def _scroll_to_bottom(self):
        self.chat_display.page().runJavaScript("window.scrollTo(0, document.body.scrollHeight);")

    def _insert_link_preview(self, url, title, description):
        if not title or not description:
            return
        preview_html = (
            f'<div style="margin-left: 20px; padding: 8px; background-color: rgba(100,100,100,0.3); '
            f'border-left: 3px solid #888; font-size: 11px; margin-top: 4px;">'
            f'<b>{title}</b><br/>{description}'
            f'</div>'
        )
        self._append_html(preview_html)
        self._scroll_to_bottom()

    def remove_message(self, msg_id):
        if msg_id not in self.message_map:
            return
        html = self._html_content
        pattern = f'<div id="msg_{msg_id}">[^<]*(?:<[^>]*>[^<]*)*</div>'
        html = re.sub(pattern, '', html, flags=re.DOTALL)
        self._set_html(html)
        del self.message_map[msg_id]

    def remove_message_by_user(self, username):
        pattern = f'<span[^>]*><b>{re.escape(username)}</b></span>[^<]*(?:<[^>]*>[^<]*)*'
        html = self._html_content
        original_length = len(html)
        html = re.sub(pattern, '', html, flags=re.DOTALL)
        if len(html) != original_length:
            self._set_html(html)


class LinkPreviewThread(QThread):
    preview_ready = pyqtSignal(str, str, str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.daemon = True
    
    def run(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.url, headers=headers, timeout=5)
            response.raise_for_status()
            html = response.text
            
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1)[:100] if title_match else "Link Preview"
            
            desc_match = re.search(r'<meta\s+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not desc_match:
                desc_match = re.search(r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            description = desc_match.group(1)[:150] if desc_match else ""
            
            self.preview_ready.emit(self.url, title, description)
        except:
            pass