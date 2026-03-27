import socket
import random
import re
import sys
import json
import os
import time
import base64
import ctypes
import ctypes.wintypes as wintypes
from collections import deque
import urllib.request
from packaging import version

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QDoubleSpinBox,
    QSlider, QCheckBox, QSpinBox, QSystemTrayIcon, QMenu, QAction,
    QTabWidget
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from overlay import ChatOverlay

try:
    import pytchat
    PYTCHAT_AVAILABLE = True
except ImportError:
    PYTCHAT_AVAILABLE = False

# ===================== CONFIG =====================
SETTINGS_FILE    = "settings.json"
CURRENT_VERSION  = "0.3.0-beta"
GITHUB_REPO      = "twhippp/ChatGate"
WM_HOTKEY        = 0x0312
HOTKEY_ID        = 1
RECONNECT_DELAYS = [3, 5, 10, 30, 60]

DARK_THEME = """
    QWidget { background-color: #18181b; color: #efeff1; font-family: 'Segoe UI'; }
    QLineEdit { background-color: #26262c; border: 1px solid #464649; color: white; padding: 5px; }
    QPushButton { background-color: #9146FF; color: white; font-weight: bold; padding: 10px; border-radius: 4px; }
    QSpinBox, QDoubleSpinBox { background-color: #26262c; border: 1px solid #464649; color: white; padding: 3px; }
    QSlider::groove:horizontal { background: #464649; height: 4px; }
    QSlider::handle:horizontal { background: #9146FF; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
    QCheckBox { color: #efeff1; }
    QMenu { background-color: #26262c; color: #efeff1; border: 1px solid #464649; }
    QMenu::item:selected { background-color: #9146FF; }
    QTabWidget::pane { border: 1px solid #464649; }
    QTabBar::tab { background: #26262c; color: #efeff1; padding: 8px 16px; border: 1px solid #464649; }
    QTabBar::tab:selected { background: #9146FF; color: white; }
    QTabBar::tab:hover { background: #3a3a3f; }
"""

LIGHT_THEME = """
    QWidget { background-color: #f0f0f0; color: #111111; font-family: 'Segoe UI'; }
    QLineEdit { background-color: #ffffff; border: 1px solid #cccccc; color: #111111; padding: 5px; }
    QPushButton { background-color: #9146FF; color: white; font-weight: bold; padding: 10px; border-radius: 4px; }
    QSpinBox, QDoubleSpinBox { background-color: #ffffff; border: 1px solid #cccccc; color: #111111; padding: 3px; }
    QSlider::groove:horizontal { background: #cccccc; height: 4px; }
    QSlider::handle:horizontal { background: #9146FF; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
    QCheckBox { color: #111111; }
    QMenu { background-color: #ffffff; color: #111111; border: 1px solid #cccccc; }
    QMenu::item:selected { background-color: #9146FF; color: white; }
    QTabWidget::pane { border: 1px solid #cccccc; }
    QTabBar::tab { background: #e0e0e0; color: #111111; padding: 8px 16px; border: 1px solid #cccccc; }
    QTabBar::tab:selected { background: #9146FF; color: white; }
    QTabBar::tab:hover { background: #d0d0d0; }
"""

# ===================== PLATFORM ICONS (base64 SVG) =====================
# Twitch glitch logo — purple
TWITCH_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#9146FF" d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/>
</svg>"""

# YouTube play button logo — red
YOUTUBE_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#FF0000" d="M23.495 6.205a3.007 3.007 0 0 0-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 0 0 .527 6.205a31.247 31.247 0 0 0-.522 5.805 31.247 31.247 0 0 0 .522 5.783 3.007 3.007 0 0 0 2.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 0 0 2.088-2.088 31.247 31.247 0 0 0 .5-5.783 31.247 31.247 0 0 0-.5-5.805zM9.609 15.601V8.408l6.264 3.602z"/>
</svg>"""

def _svg_to_pixmap(svg_bytes, size=16):
    """Convert a raw SVG bytes to a QPixmap at the given size."""
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtCore import QByteArray
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    from PyQt5.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap

def _platform_badge_html(platform):
    """Return an HTML img tag with the platform icon as an inline base64 PNG."""
    svg = TWITCH_SVG if platform == "twitch" else YOUTUBE_SVG
    try:
        pm  = _svg_to_pixmap(svg, 14)
        buf = pm.toImage()
        import io
        # Convert QImage to PNG bytes via a temporary buffer trick
        from PyQt5.QtCore import QBuffer, QIODevice
        qbuf = QBuffer()
        qbuf.open(QIODevice.WriteOnly)
        buf.save(qbuf, "PNG")
        b64 = base64.b64encode(qbuf.data().data()).decode()
        return f"<img src='data:image/png;base64,{b64}' width='12' height='12' style='vertical-align:middle;'> "
    except Exception:
        # Fallback to text badge if SVG rendering fails
        if platform == "twitch":
            return "<span style='color:#9146FF;font-size:0.8em'>[T]</span> "
        return "<span style='color:#FF0000;font-size:0.8em'>[YT]</span> "

# ===================== ICON =====================
def get_icon_path():
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ChatGate.ico")

# ===================== VIDEO ID RESOLUTION =====================
VIDEO_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
WATCH_RE    = re.compile(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})')
HEADERS     = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

def _fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", errors="ignore")

def _extract_video_id_from_html(html):
    patterns = [
        r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"',
        r'watch\?v=([a-zA-Z0-9_-]{11})',
        r'canonical.*?watch\?v=([a-zA-Z0-9_-]{11})',
        r'og:video.*?v=([a-zA-Z0-9_-]{11})',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None

def resolve_video_id(user_input):
    s = user_input.strip().lstrip("@")
    if VIDEO_ID_RE.match(s):
        return s
    m = WATCH_RE.search(s)
    if m:
        return m.group(1)
    candidates = [
        f"https://www.youtube.com/@{s}/live",
        f"https://www.youtube.com/@{s}",
        f"https://www.youtube.com/c/{s}/live",
        f"https://www.youtube.com/c/{s}",
        f"https://www.youtube.com/user/{s}/live",
        f"https://www.youtube.com/user/{s}",
    ]
    for url in candidates:
        try:
            html = _fetch(url)
            vid  = _extract_video_id_from_html(html)
            if vid:
                return vid
        except Exception:
            continue
    return None

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, channel, threshold, bypass):
        super().__init__()
        chan = channel.lower().strip().replace("#", "")
        self.channel    = f"#{chan}"
        self.threshold  = threshold
        self.bypass     = bypass
        self.msg_times  = deque()
        self.is_running = True

    def stop(self):
        self.is_running = False

    def run(self):
        sock = socket.socket()
        try:
            self.status_msg.emit("Connecting...")
            sock.connect(("irc.chat.twitch.tv", 6667))
            sock.send(f"NICK justinfan{random.randint(10000, 99999)}\r\n".encode())
            sock.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            sock.send(f"JOIN {self.channel}\r\n".encode())
            self.status_msg.emit("Connected")

            while self.is_running:
                data = sock.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    break
                for line in data.split('\r\n'):
                    if not line:
                        continue
                    if line.startswith("PING"):
                        sock.send("PONG :tmi.twitch.tv\r\n".encode())
                        continue
                    if "PRIVMSG" not in line:
                        continue

                    tags = {}
                    if line.startswith("@"):
                        tag_part = line.split(" ", 1)[0][1:]
                        tags = dict(t.split("=") for t in tag_part.split(";") if "=" in t)

                    user = tags.get("display-name", "User")
                    try:
                        content = line.split("PRIVMSG", 1)[1].split(":", 1)[1]
                    except Exception:
                        content = ""

                    now = time.time()
                    self.msg_times.append(now)
                    while self.msg_times and now - self.msg_times[0] > 5.0:
                        self.msg_times.popleft()
                    mps          = len(self.msg_times) / 5.0
                    is_filtering = mps >= self.threshold
                    self.stats_update.emit(mps, is_filtering)

                    is_mod = tags.get("mod") == "1" or "broadcaster" in tags.get("badges", "")
                    is_sub = tags.get("subscriber") == "1"
                    is_vip = "vip" in tags.get("badges", "")

                    should_show = not is_filtering
                    if is_mod and self.bypass.get('mod'): should_show = True
                    if is_sub and self.bypass.get('sub'): should_show = True
                    if is_vip and self.bypass.get('vip'): should_show = True

                    if should_show:
                        badge = _platform_badge_html("twitch")
                        color = tags.get("color") or f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        self.message.emit(
                            f"{badge}<span style='color:{color}'><b>{user}</b></span>: {content}")

        except Exception:
            pass
        finally:
            sock.close()
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()

# ===================== YOUTUBE THREAD =====================
class YouTubeThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    CHAT_RATE_WINDOW = 5.0

    def __init__(self, handle, threshold, bypass_member=False):
        super().__init__()
        self.handle        = handle
        self.threshold     = threshold
        self.bypass_member = bypass_member
        self.msg_times     = deque()
        self.is_running    = True

    def stop(self):
        self.is_running = False

    def run(self):
        self.status_msg.emit("Resolving channel...")
        video_id = resolve_video_id(self.handle)

        if not video_id:
            self.status_msg.emit("Error: Could not find live stream")
            if self.is_running:
                self.disconnected.emit()
            return

        self.status_msg.emit(f"Connecting... (ID: {video_id})")

        try:
            chat = pytchat.create(video_id=video_id, interruptable=False)
            if not chat.is_alive():
                self.status_msg.emit("Error: Stream found but chat is not active")
                if self.is_running:
                    self.disconnected.emit()
                return

            self.status_msg.emit("Connected")

            while self.is_running and chat.is_alive():
                for item in chat.get().sync_items():
                    if not self.is_running:
                        break

                    now = time.time()
                    self.msg_times.append(now)
                    while self.msg_times and now - self.msg_times[0] > self.CHAT_RATE_WINDOW:
                        self.msg_times.popleft()
                    mps          = len(self.msg_times) / self.CHAT_RATE_WINDOW
                    is_filtering = mps >= self.threshold
                    self.stats_update.emit(mps, is_filtering)

                    is_member   = bool(item.author.badgeUrl)
                    should_show = not is_filtering
                    if is_member and self.bypass_member:
                        should_show = True

                    if should_show:
                        badge = _platform_badge_html("youtube")
                        user  = item.author.name
                        color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        self.message.emit(
                            f"{badge}<span style='color:{color}'><b>{user}</b></span>: {item.message}")

        except Exception:
            pass
        finally:
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()

# ===================== MAIN CONTROLLER =====================
class ChatGateMain(QWidget):
    def __init__(self):
        super().__init__()
        self.settings   = self.load_settings()
        self.dark_mode  = self.settings.get("dark_mode", True)
        self.setWindowTitle("ChatGate")
        self.resize(460, 660)

        self.overlay        = ChatOverlay()
        self.overlay_active = False

        # Twitch IRC
        self.irc                  = None
        self._irc_reconnect_attempt = 0
        self._irc_reconnect_timer   = QTimer()
        self._irc_reconnect_timer.setSingleShot(True)
        self._irc_reconnect_timer.timeout.connect(self._do_irc_reconnect)
        self._last_twitch_channel = ""

        # YouTube
        self.yt                  = None
        self._yt_reconnect_attempt = 0
        self._yt_reconnect_timer   = QTimer()
        self._yt_reconnect_timer.setSingleShot(True)
        self._yt_reconnect_timer.timeout.connect(self._do_yt_reconnect)
        self._last_yt_handle      = ""

        self.overlay.move(self.settings.get("pos_x", 100), self.settings.get("pos_y", 100))
        self.overlay.resize(self.settings.get("width", 400), self.settings.get("height", 600))

        self.init_ui()
        self.apply_theme()
        self.register_hotkey()
        self.sync_overlay()
        self.init_tray()

        QTimer.singleShot(100,  self._set_win32_icon)
        QTimer.singleShot(1000, self.check_for_updates)

    # ===================== SETTINGS =====================
    def load_settings(self):
        defaults = {
            "twitch_channel": "piratesoftware",
            "yt_handle": "",
            "mps": 3.0, "opacity": 100,
            "mod": True, "vip": True, "sub": True, "yt_member": True,
            "pos_x": 100, "pos_y": 100, "width": 400, "height": 600,
            "dark_mode": True, "font_size": 22
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return {**defaults, **json.load(f)}
            except:
                pass
        return defaults

    def save_settings(self):
        data = {
            "twitch_channel": self.twitch_input.text(),
            "yt_handle":      self.yt_input.text(),
            "mps":            self.mps_spin.value(),
            "opacity":        self.alpha_slider.value(),
            "mod":            self.bp_mod.isChecked(),
            "vip":            self.bp_vip.isChecked(),
            "sub":            self.bp_sub.isChecked(),
            "yt_member":      self.bp_yt_member.isChecked(),
            "pos_x":          self.overlay.x(),
            "pos_y":          self.overlay.y(),
            "width":          self.overlay.width(),
            "height":         self.overlay.height(),
            "dark_mode":      self.dark_mode,
            "font_size":      self.font_spin.value(),
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)

    # ===================== THEME =====================
    def apply_theme(self):
        self.setStyleSheet(DARK_THEME if self.dark_mode else LIGHT_THEME)
        self.theme_btn.setText("☀ Light Mode" if self.dark_mode else "☾ Dark Mode")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.save_settings()

    # ===================== TRAY =====================
    def init_tray(self):
        icon = QIcon(get_icon_path())
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("ChatGate")

        menu = QMenu()
        action_show   = QAction("Show Controller", self)
        action_toggle = QAction("Toggle Overlay",  self)
        action_quit   = QAction("Quit",            self)
        action_show.triggered.connect(self.restore_from_tray)
        action_toggle.triggered.connect(self._hotkey_toggle)
        action_quit.triggered.connect(self.quit_app)
        menu.addAction(action_show)
        menu.addAction(action_toggle)
        menu.addSeparator()
        menu.addAction(action_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def quit_app(self):
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "ChatGate",
            "Running in the background. Double-click the tray icon to restore.",
            QSystemTrayIcon.Information,
            2000
        )

    # ===================== WIN32 ICON =====================
    def _set_win32_icon(self):
        try:
            ico_path = get_icon_path()
            if not os.path.exists(ico_path):
                return
            WM_SETICON      = 0x0080
            IMAGE_ICON      = 1
            LR_LOADFROMFILE = 0x0010
            LR_DEFAULTSIZE  = 0x0040
            hicon = ctypes.windll.user32.LoadImageW(
                None, ico_path, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
            hwnd = int(self.winId())
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon)
        except Exception:
            pass

    # ===================== UI =====================
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        self.ver_label    = QLabel(f"v{CURRENT_VERSION}")
        self.mps_label    = QLabel("MPS: 0.0")
        header.addWidget(self.ver_label)
        header.addStretch()
        header.addWidget(self.mps_label)
        layout.addLayout(header)

        # ---- Platform tabs ----
        tabs = QTabWidget()

        # Twitch tab
        twitch_tab = QWidget()
        twitch_layout = QVBoxLayout(twitch_tab)
        twitch_layout.setContentsMargins(10, 10, 10, 10)
        twitch_layout.setSpacing(8)

        twitch_row = QHBoxLayout()
        self.twitch_input  = QLineEdit(self.settings.get("twitch_channel", ""))
        self.twitch_input.setPlaceholderText("Channel name")
        self.twitch_input.textChanged.connect(self.save_settings)
        self.twitch_connect_btn = QPushButton("CONNECT")
        self.twitch_connect_btn.clicked.connect(self.start_twitch)
        twitch_row.addWidget(self.twitch_input)
        twitch_row.addWidget(self.twitch_connect_btn)
        twitch_layout.addLayout(twitch_row)

        self.twitch_status = QLabel("OFFLINE")
        twitch_layout.addWidget(self.twitch_status)

        twitch_layout.addWidget(QLabel("Bypass filters for:"))
        self.bp_mod = QCheckBox("Moderators / Broadcaster")
        self.bp_mod.setChecked(self.settings["mod"])
        self.bp_sub = QCheckBox("Subscribers")
        self.bp_sub.setChecked(self.settings["sub"])
        self.bp_vip = QCheckBox("VIPs")
        self.bp_vip.setChecked(self.settings["vip"])
        for cb in [self.bp_mod, self.bp_sub, self.bp_vip]:
            cb.stateChanged.connect(self.save_settings)
            twitch_layout.addWidget(cb)
        twitch_layout.addStretch()

        # YouTube tab
        yt_tab = QWidget()
        yt_layout = QVBoxLayout(yt_tab)
        yt_layout.setContentsMargins(10, 10, 10, 10)
        yt_layout.setSpacing(8)

        yt_row = QHBoxLayout()
        self.yt_input = QLineEdit(self.settings.get("yt_handle", ""))
        self.yt_input.setPlaceholderText("@handle, URL, or video ID")
        self.yt_input.textChanged.connect(self.save_settings)
        self.yt_connect_btn = QPushButton("CONNECT")
        self.yt_connect_btn.clicked.connect(self.start_youtube)
        yt_row.addWidget(self.yt_input)
        yt_row.addWidget(self.yt_connect_btn)
        yt_layout.addLayout(yt_row)

        self.yt_status = QLabel("OFFLINE")
        yt_layout.addWidget(self.yt_status)

        yt_layout.addWidget(QLabel("Bypass filters for:"))
        self.bp_yt_member = QCheckBox("Members")
        self.bp_yt_member.setChecked(self.settings.get("yt_member", True))
        self.bp_yt_member.stateChanged.connect(self.save_settings)
        yt_layout.addWidget(self.bp_yt_member)

        if not PYTCHAT_AVAILABLE:
            warn = QLabel("⚠ pytchat not installed.\nRun: pip install pytchat")
            warn.setStyleSheet("color: #ff4444;")
            yt_layout.addWidget(warn)
            self.yt_connect_btn.setEnabled(False)

        yt_layout.addStretch()

        tabs.addTab(twitch_tab, "Twitch")
        tabs.addTab(yt_tab,     "YouTube")
        layout.addWidget(tabs)

        # ---- Shared overlay controls ----
        self.move_btn = QPushButton("UNLOCK OVERLAY TO MOVE")
        self.move_btn.setCheckable(True)
        self.move_btn.toggled.connect(self.toggle_move_mode)
        layout.addWidget(self.move_btn)

        layout.addWidget(QLabel("<b>OPACITY</b>"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(10, 100)
        self.alpha_slider.setValue(self.settings["opacity"])
        self.alpha_slider.valueChanged.connect(self.sync_overlay)
        layout.addWidget(self.alpha_slider)

        row = QHBoxLayout()
        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 60)
        self.font_spin.setValue(self.settings["font_size"])
        self.font_spin.valueChanged.connect(self.sync_overlay)
        self.mps_spin = QDoubleSpinBox()
        self.mps_spin.setRange(0.1, 25.0)
        self.mps_spin.setValue(self.settings["mps"])
        self.mps_spin.valueChanged.connect(self.save_settings)
        row.addWidget(QLabel("Font:"))
        row.addWidget(self.font_spin)
        row.addWidget(QLabel("MPS Limit:"))
        row.addWidget(self.mps_spin)
        layout.addLayout(row)

        self.theme_btn = QPushButton("")
        self.theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_btn)

        layout.addStretch()

    # ===================== OVERLAY SYNC =====================
    def sync_overlay(self):
        self.overlay.update_style(self.font_spin.value(), self.alpha_slider.value() / 100.0)
        self.overlay.resize(self.settings.get("width", 400), self.overlay.height())
        self.save_settings()

    def toggle_move_mode(self, unlocked):
        self.move_btn.setText("LOCK POSITION" if unlocked else "UNLOCK OVERLAY TO MOVE")
        self.overlay.set_click_through(not unlocked)
        if unlocked:
            self.overlay.show()
        else:
            self.save_settings()

    # ===================== HOTKEY =====================
    def register_hotkey(self):
        try:
            ctypes.windll.user32.RegisterHotKey(
                int(self.winId()), HOTKEY_ID, 0x0002 | 0x0004, ord("O"))
        except:
            pass

    def _hotkey_toggle(self):
        self.overlay_active = not self.overlay_active
        self.overlay.show() if self.overlay_active else self.overlay.hide()
        if self.overlay_active:
            self.overlay.set_click_through(True)

    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self._hotkey_toggle()
            return True, 0
        return super().nativeEvent(eventType, message)

    # ===================== TWITCH =====================
    def start_twitch(self):
        self.save_settings()
        self._irc_reconnect_attempt = 0
        self._last_twitch_channel   = self.twitch_input.text().strip()
        self._irc_reconnect_timer.stop()
        self._launch_irc()
        self._show_overlay()

    def _launch_irc(self):
        if self.irc is not None:
            self.irc.stop()
            try: self.irc.disconnected.disconnect()
            except: pass
        bypass = {
            'mod': self.bp_mod.isChecked(),
            'vip': self.bp_vip.isChecked(),
            'sub': self.bp_sub.isChecked()
        }
        self.irc = IRCThread(self._last_twitch_channel, self.mps_spin.value(), bypass)
        self.irc.message.connect(self.overlay.add_message)
        self.irc.stats_update.connect(self._update_stats)
        self.irc.status_msg.connect(lambda s: self.twitch_status.setText(s.upper()))
        self.irc.disconnected.connect(self._on_irc_disconnected)
        self.irc.start()

    def _on_irc_disconnected(self):
        delay = RECONNECT_DELAYS[min(self._irc_reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
        self._irc_reconnect_attempt += 1
        self.twitch_status.setText(f"RECONNECTING IN {delay}s...")
        self._irc_reconnect_timer.start(delay * 1000)

    def _do_irc_reconnect(self):
        if self._last_twitch_channel:
            self._launch_irc()

    # ===================== YOUTUBE =====================
    def start_youtube(self):
        if not PYTCHAT_AVAILABLE:
            return
        self.save_settings()
        self._yt_reconnect_attempt = 0
        self._last_yt_handle       = self.yt_input.text().strip()
        self._yt_reconnect_timer.stop()
        self._launch_yt()
        self._show_overlay()

    def _launch_yt(self):
        if self.yt is not None:
            self.yt.stop()
            try: self.yt.disconnected.disconnect()
            except: pass
        self.yt = YouTubeThread(
            self._last_yt_handle,
            self.mps_spin.value(),
            bypass_member=self.bp_yt_member.isChecked()
        )
        self.yt.message.connect(self.overlay.add_message)
        self.yt.stats_update.connect(self._update_stats)
        self.yt.status_msg.connect(lambda s: self.yt_status.setText(s.upper()))
        self.yt.disconnected.connect(self._on_yt_disconnected)
        self.yt.start()

    def _on_yt_disconnected(self):
        delay = RECONNECT_DELAYS[min(self._yt_reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
        self._yt_reconnect_attempt += 1
        self.yt_status.setText(f"RECONNECTING IN {delay}s...")
        self._yt_reconnect_timer.start(delay * 1000)

    def _do_yt_reconnect(self):
        if self._last_yt_handle:
            self._launch_yt()

    # ===================== SHARED =====================
    def _show_overlay(self):
        if not self.overlay_active:
            self.overlay_active = True
            self.overlay.show()
            self.overlay.set_click_through(True)

    def _update_stats(self, mps, filtering):
        self.mps_label.setText(f"MPS: {mps:.1f}")
        self.mps_label.setStyleSheet(
            f"color: {'#ff4444' if filtering else '#9146FF'}; font-weight: bold;")

    # ===================== UPDATE CHECK =====================
    def check_for_updates(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 (ChatGate-Updater)'})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                if data:
                    latest_tag = data[0]["name"]
                    latest_v   = latest_tag.lower().replace("v", "").strip()
                    current_v  = CURRENT_VERSION.lower().replace("v", "").strip()
                    if version.parse(latest_v) > version.parse(current_v):
                        update_link = f"https://github.com/{GITHUB_REPO}/tags"
                        self.ver_label.setText(
                            f"<a href='{update_link}' style='color:#00ff7f; text-decoration:none;'>"
                            f"UPDATE AVAILABLE: {latest_tag}</a>")
                        self.ver_label.setOpenExternalLinks(True)
                    else:
                        self.ver_label.setText(f"v{CURRENT_VERSION} (Latest)")
        except Exception:
            pass

# ===================== ENTRY =====================
if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ChatGate.App")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("ChatGate")
    app.setOrganizationName("ChatGate")
    app.setWindowIcon(QIcon(get_icon_path()))
    app.setQuitOnLastWindowClosed(False)
    w = ChatGateMain()
    w.show()
    sys.exit(app.exec_())
