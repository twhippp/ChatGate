import sys
import ctypes
import re
import requests
import importlib.util
import os

# Load project's badges.py explicitly to avoid colliding with the top-level
# `badges/` assets directory which would make `import badges` pick the
# directory instead of the helper module.
import json
proj_root = os.path.dirname(os.path.abspath(__file__))
badges_py = os.path.join(proj_root, 'badges.py')
if os.path.exists(badges_py):
    try:
        spec = importlib.util.spec_from_file_location('project_badges', badges_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        get_badge_html = getattr(mod, 'get_badge_html')
    except Exception:
        get_badge_html = None
else:
    get_badge_html = None

if get_badge_html is None:
    def get_badge_html(token, size=14):
        if token == 'm': return "<span style='color:#9146FF;'>🛡️</span> "
        if token == 'v': return "<span style='color:#ffcc00;'>💎</span> "
        if token == 's': return "<span style='color:#FFD700;'>★</span> "
        return ''
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSlot, QPoint, QThread, pyqtSignal, QTimer
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
        # Slightly larger handle for visibility and easier grabbing
        self.drag_handle.setFixedHeight(28)
        self.drag_handle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.drag_handle.setStyleSheet("""
            background-color: rgba(145, 70, 255, 200);
            color: white;
            font-weight: bold;
            font-size: 12px;
            padding: 4px 8px;
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

    def _debug_log(self, tag, txt):
        try:
            print(f"[Overlay] {tag}: {txt[:200]}")
        except Exception:
            pass

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
            /* Keep body static and allow #messages to scroll so we can hide scrollbar */
            html, body {{
                background-color: {rgba};
                color: white;
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: {font_size}px;
                margin: 0;
                padding: 4px;
                height: 100%;
                overflow: hidden;
            }}
            div {{ margin-bottom: 2px; }}
            #messages {{ padding-bottom: 8px; max-height: 100%; overflow-y: auto; -ms-overflow-style: none; scrollbar-width: none; }}
            /* Hide webkit scrollbar */
            #messages::-webkit-scrollbar {{ width: 0px; height: 0px; display: none; }}
            a {{ color: #4da6ff; }}
            img {{ vertical-align: middle; }}
        </style>
        </head>
        <body>
        <div id="messages">{html}</div>
        </body>
        </html>
        """
        self.chat_display.setHtml(base_html)

    def _append_html(self, html):
        # Keep the python-side HTML content for lookups, but append to the
        # live DOM instead of resetting the whole page (prevents scroll jump).
        wrapped = html
        self._html_content += wrapped
        try:
            js = (
                "(function(){var m=document.getElementById('messages');"
                + "if(m) m.insertAdjacentHTML('beforeend'," + json.dumps(wrapped) + ");})();"
            )
            self.chat_display.page().runJavaScript(js)
        except Exception:
            # Fallback to full re-render if JS append fails
            self._set_html(self._html_content)

    @pyqtSlot(str)
    def add_message(self, html):
        # Replace simple badge tokens like [m], [v], [s] with images
        def _badge_repl(m):
            tok = m.group(1).lower()
            return get_badge_html(tok, size=max(12, getattr(self, '_font_size', 14) - 2))
        html = re.sub(r"\[([mvsMVS])\]", _badge_repl, html)
        # Detect channel-points / user-notice redeems and render a banner
        try:
            lower = html.lower()
            if 'redeemed' in lower and 'channel' in lower:
                # extract inline svg if present
                svg_match = re.search(r'(<svg[\s\S]*?</svg>)', html, re.IGNORECASE)
                svg = svg_match.group(1) if svg_match else ''
                # extract "User redeemed Reward" pattern
                ur_match = re.search(r'>(?P<user>[^<>]+?)\s+redeemed\s+(?P<reward>[^<]+)', html, re.IGNORECASE | re.DOTALL)
                if ur_match:
                    user = ur_match.group('user').strip()
                    reward = ur_match.group('reward').strip()
                    # find a trailing numeric points value if present
                    pts = ''
                    pts_matches = re.findall(r'>(\d+)<', html)
                    if pts_matches:
                        pts = pts_matches[-1]
                    size = max(14, getattr(self, '_font_size', 14) + 2)
                    banner = (
                        f"<div style=\"padding:10px; margin:6px 0; background:linear-gradient(90deg,#fff6d6,#ffe680);"
                        f" data-redeem='1'>"
                        f"<div style=\"display:flex; align-items:center; gap:10px;\">"
                        f"<div style=\"width:36px;height:36px;flex:0 0 36px;\">{svg}</div>"
                        f"<div style=\"flex:1; color:#1b1b1b; font-size:{size}px; font-weight:700;\">"
                        f"{user} <span style=\"font-weight:600;\">redeemed</span> <span style=\"color:#b35a00;\">{reward}</span>"
                        f"</div>"
                        f"<div style=\"flex:0 0 auto; font-weight:800; color:#b35a00; font-size:{size}px;\">{pts}</div>"
                        f"</div></div>"
                    )
                    html = banner
        except Exception:
            pass
        self._debug_log('add_message_received', html)
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
        self._schedule_scroll()

    @pyqtSlot(str, str, str)
    def add_redeem(self, user, reward, cost):
        # Render a prominent redeem banner
        try:
            size = max(14, getattr(self, '_font_size', 14) + 2)
            svg = ("<svg width=\"24\" height=\"24\" viewBox=\"0 0 24 24\">"
                   "<path d=\"M12 5v2a5 5 0 0 1 5 5h2a7 7 0 0 0-7-7Z\"></path>"
                   "<path fill-rule=\"evenodd\" d=\"M1 12C1 5.925 5.925 1 12 1s11 4.925 11 11-4.925 11-11 11S1 18.075 1 12Zm11 9a9 9 0 1 1 0-18 9 9 0 0 1 0 18Z\" clip-rule=\"evenodd\"></path>"
                   "</svg>")
            pts = cost or ""
            banner = (
                f"<div style=\"padding:10px; margin:6px 0; background:linear-gradient(90deg,#fff6d6,#ffe680);" \
                f"border-radius:6px; border:1px solid #f0c070;\">"
                f"<div style=\"display:flex; align-items:center; gap:10px;\">"
                f"<div style=\"width:36px;height:36px;flex:0 0 36px;\">{svg}</div>"
                f"<div style=\"flex:1; color:#1b1b1b; font-size:{size}px; font-weight:700;\">"
                f"{user} <span style=\"font-weight:600;\">redeemed</span> <span style=\"color:#b35a00;\">{reward}</span>"
                f"</div>"
                f"<div style=\"flex:0 0 auto; font-weight:800; color:#b35a00; font-size:{size}px;\">{pts}</div>"
                f"</div></div>"
            )
            self._append_html(banner)
            self._schedule_scroll()
        except Exception:
            pass

    def _schedule_scroll(self):
        QTimer.singleShot(50, self._scroll_to_bottom)
        QTimer.singleShot(100, self._scroll_to_bottom)
        QTimer.singleShot(200, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        # Clear old messages to prevent memory buildup
        if self.next_msg_id > 500:
            self._html_content = ""
            self.message_map.clear()
            self.next_msg_id = 0
            try:
                self.chat_display.page().runJavaScript("var m=document.getElementById('messages'); if(m) m.innerHTML='';")
            except Exception:
                self._set_html("")
        else:
            # Scroll the messages container (body is non-scrolling now)
            js = (
                "(function(){var m=document.getElementById('messages');"
                "if(m){m.scrollTop=m.scrollHeight; var last=m.lastElementChild; if(last) last.scrollIntoView();}})();"
            )
            self.chat_display.page().runJavaScript(js)

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
        self._schedule_scroll()

    def remove_message(self, msg_id):
        if msg_id not in self.message_map:
            return
        # Remove from python-side content
        html = self._html_content
        pattern = f'<div id="msg_{msg_id}">[^<]*(?:<[^>]*>[^<]*)*</div>'
        html = re.sub(pattern, '', html, flags=re.DOTALL)
        self._html_content = html
        try:
            js = f"var e=document.getElementById('msg_{msg_id}'); if(e) e.remove();"
            self.chat_display.page().runJavaScript(js)
        except Exception:
            self._set_html(self._html_content)
        del self.message_map[msg_id]

    def remove_message_by_user(self, username):
        pattern = f'<span[^>]*><b>{re.escape(username)}</b></span>[^<]*(?:<[^>]*>[^<]*)*'
        html = self._html_content
        original_length = len(html)
        html = re.sub(pattern, '', html, flags=re.DOTALL)
        if len(html) != original_length:
            self._html_content = html
            try:
                # Best-effort: remove any matching user nodes client-side
                js = (
                    "(function(){var msgs=document.querySelectorAll('#messages > div');"
                    "for(var i=0;i<msgs.length;i++){if(msgs[i].innerText.indexOf("+ json.dumps(username) +")!==-1){msgs[i].remove();}}})();"
                )
                self.chat_display.page().runJavaScript(js)
            except Exception:
                self._set_html(self._html_content)


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