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
    QTabWidget, QComboBox, QScrollArea, QFrame, QSizePolicy, QGroupBox
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QCursor
from overlay import ChatOverlay

try:
    from chat_downloader import ChatDownloader
    YT_AVAILABLE = True
    YT_ERROR = None
except ImportError as e:
    YT_AVAILABLE = False
    YT_ERROR = str(e)

# ===================== CONFIG =====================
SETTINGS_FILE    = "settings.json"
CURRENT_VERSION  = "0.3.2-beta"
GITHUB_REPO      = "twhippp/ChatGate"
WM_HOTKEY        = 0x0312
HOTKEY_ID        = 1
RECONNECT_DELAYS = [3, 5, 10, 30, 60]

BYPASS_OPTIONS = ["Always", "Normal", "Never"]

TAB_TWITCH  = 0
TAB_YOUTUBE = 1
TAB_FILTERS = 2

ACCENT = {
    TAB_TWITCH:  "#9146FF",
    TAB_YOUTUBE: "#FF0000",
    TAB_FILTERS: "#9146FF",
}

# ===================== THEMES =====================
def _build_theme(bg, widget_bg, border, fg, hover, accent):
    return f"""
    QWidget {{ background-color: {bg}; color: {fg}; font-family: 'Segoe UI'; }}
    QLineEdit {{ background-color: {widget_bg}; border: 1px solid {border}; color: {fg}; padding: 5px; border-radius: 3px; }}
    QPushButton {{ background-color: {accent}; color: white; font-weight: bold; padding: 8px 12px; border-radius: 4px; border: none; }}
    QPushButton:hover {{ background-color: {accent}dd; }}
    QSpinBox, QDoubleSpinBox {{ background-color: {widget_bg}; border: 1px solid {border}; color: {fg}; padding: 3px; border-radius: 3px; }}
    QComboBox {{ background-color: {widget_bg}; border: 1px solid {border}; color: {fg}; padding: 4px; border-radius: 3px; }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{ background-color: {widget_bg}; color: {fg}; border: 1px solid {border}; selection-background-color: {accent}; }}
    QSlider::groove:horizontal {{ background: {border}; height: 4px; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {accent}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
    QCheckBox {{ color: {fg}; }}
    QMenu {{ background-color: {widget_bg}; color: {fg}; border: 1px solid {border}; }}
    QMenu::item:selected {{ background-color: {accent}; color: white; }}
    QTabWidget::pane {{ border: 1px solid {border}; }}
    QTabBar::tab {{ background: {widget_bg}; color: {fg}; padding: 8px 16px; border: 1px solid {border}; }}
    QTabBar::tab:selected {{ background: {accent}; color: white; }}
    QTabBar::tab:hover {{ background: {hover}; }}
    QScrollArea {{ border: none; }}
    QGroupBox {{ border: 1px solid {border}; border-radius: 4px; margin-top: 6px; padding-top: 6px; font-weight: bold; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; }}
    """

DARK_THEME_BASE  = ("#18181b", "#26262c", "#464649", "#efeff1", "#3a3a3f")
LIGHT_THEME_BASE = ("#f0f0f0", "#ffffff", "#cccccc", "#111111", "#d0d0d0")

def get_theme(dark, accent="#9146FF"):
    base = DARK_THEME_BASE if dark else LIGHT_THEME_BASE
    return _build_theme(*base, accent)

# ===================== PLATFORM ICONS =====================
TWITCH_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#9146FF" d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/>
</svg>"""

YOUTUBE_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path fill="#FF0000" d="M23.495 6.205a3.007 3.007 0 0 0-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 0 0 .527 6.205a31.247 31.247 0 0 0-.522 5.805 31.247 31.247 0 0 0 .522 5.783 3.007 3.007 0 0 0 2.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 0 0 2.088-2.088 31.247 31.247 0 0 0 .5-5.783 31.247 31.247 0 0 0-.5-5.805zM9.609 15.601V8.408l6.264 3.602z"/>
</svg>"""

def _svg_to_pixmap(svg_bytes, size=16):
    from PyQt5.QtSvg import QSvgRenderer
    from PyQt5.QtCore import QByteArray
    from PyQt5.QtGui import QPainter
    renderer = QSvgRenderer(QByteArray(svg_bytes))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap

def _platform_badge_html(platform):
    svg = TWITCH_SVG if platform == "twitch" else YOUTUBE_SVG
    try:
        from PyQt5.QtCore import QBuffer, QIODevice
        pm   = _svg_to_pixmap(svg, 14)
        qbuf = QBuffer()
        qbuf.open(QIODevice.WriteOnly)
        pm.toImage().save(qbuf, "PNG")
        b64 = base64.b64encode(qbuf.data().data()).decode()
        return f"<img src='data:image/png;base64,{b64}' width='12' height='12' style='vertical-align:middle;'> "
    except Exception:
        return "<span style='color:#9146FF;font-size:0.8em'>[T]</span> " if platform == "twitch" \
               else "<span style='color:#FF0000;font-size:0.8em'>[YT]</span> "

# ===================== EVENT FORMATTERS =====================
def fmt_raid(from_user, viewer_count):
    return (f"<span style='background-color:#9146FF22; border-left:3px solid #9146FF; padding:2px 6px;'>"
            f"🚨 <b style='color:#9146FF'>{from_user}</b> is raiding with "
            f"<b style='color:#FFD700'>{viewer_count}</b> viewers!</span>")

def fmt_sub(user, months, msg=""):
    base = (f"<span style='background-color:#FFD70022; border-left:3px solid #FFD700; padding:2px 6px;'>"
            f"⭐ <b style='color:#FFD700'>{user}</b> subscribed")
    if months and int(months) > 1:
        base += f" (<b>{months} months</b>)"
    if msg:
        base += f" — {msg}"
    return base + "</span>"

def fmt_subgift(gifter, recipient, months=""):
    return (f"<span style='background-color:#FFD70022; border-left:3px solid #FFD700; padding:2px 6px;'>"
            f"🎁 <b style='color:#FFD700'>{gifter}</b> gifted a sub to "
            f"<b style='color:#FFD700'>{recipient}</b>"
            + (f" ({months} months)" if months else "") + "</span>")

def fmt_subgift_bomb(gifter, count):
    return (f"<span style='background-color:#FFD70022; border-left:3px solid #FFD700; padding:2px 6px;'>"
            f"🎁 <b style='color:#FFD700'>{gifter}</b> gifted "
            f"<b style='color:#FFD700'>{count}</b> subs to the community!</span>")

def fmt_announcement(user, msg, color="PRIMARY"):
    color_map = {"PRIMARY": "#9146FF", "BLUE": "#4da6ff", "GREEN": "#00e5cb", "ORANGE": "#ff9a00", "PURPLE": "#9146FF"}
    c = color_map.get(color.upper(), "#9146FF")
    return (f"<span style='background-color:{c}22; border-left:3px solid {c}; padding:2px 6px;'>"
            f"📢 <b style='color:{c}'>{user}</b>: {msg}</span>")

def fmt_bits(user, bits, msg=""):
    return (f"<span style='background-color:#ff69b422; border-left:3px solid #ff69b4; padding:2px 6px;'>"
            f"💎 <b style='color:#ff69b4'>{user}</b> cheered "
            f"<b style='color:#ff69b4'>{bits} bits</b>"
            + (f" — {msg}" if msg else "") + "</span>")

def fmt_first_chat(user, msg):
    return (f"<span style='background-color:#00e5cb22; border-left:3px solid #00e5cb; padding:2px 6px;'>"
            f"👋 <b style='color:#00e5cb'>First chat!</b> "
            f"<b style='color:#00e5cb'>{user}</b>: {msg}</span>")

# ===================== ICON =====================
def get_icon_path():
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ChatGate.ico")

# ===================== SETTINGS =====================
SETTINGS_DEFAULTS = {
    "twitch_channel": "piratesoftware",
    "yt_handle": "",
    "mps": 3.0,
    "opacity": 100,
    "pos_x": 100, "pos_y": 100, "width": 400, "height": 600,
    "dark_mode": True,
    "font_size": 22,
    "minimize_to_tray": True,
    "combined_mps": True,
    "bypass_broadcaster": "Normal",
    "bypass_mod":         "Normal",
    "bypass_vip":         "Normal",
    "bypass_sub":         "Normal",
    "bypass_yt_member":   "Normal",
    "always_block_words":  [],
    "volume_block_words":  [],
    "user_whitelist":      [],
    "user_blacklist":      [],
    "show_raids":          True,
    "show_subs":           True,
    "show_bits":           True,
    "show_announcements":  True,
    "show_first_chat":     False,
}

def migrate_settings(raw):
    migrated = dict(SETTINGS_DEFAULTS)
    direct_keys = [
        "twitch_channel", "yt_handle", "mps", "opacity",
        "pos_x", "pos_y", "width", "height",
        "dark_mode", "font_size", "minimize_to_tray", "combined_mps",
        "bypass_broadcaster", "bypass_mod", "bypass_vip", "bypass_sub",
        "bypass_yt_member",
        "always_block_words", "volume_block_words",
        "user_whitelist", "user_blacklist",
        "show_raids", "show_subs", "show_bits", "show_announcements", "show_first_chat",
    ]
    for k in direct_keys:
        if k in raw: migrated[k] = raw[k]
    bool_map = {"mod": "bypass_mod", "vip": "bypass_vip", "sub": "bypass_sub"}
    for old_key, new_key in bool_map.items():
        if old_key in raw and new_key not in raw:
            migrated[new_key] = "Always" if raw[old_key] else "Normal"
    if "channel" in raw and "twitch_channel" not in raw:
        migrated["twitch_channel"] = raw["channel"]
    return migrated

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                raw = json.load(f)
            migrated = migrate_settings(raw)
            if migrated != raw:
                with open(SETTINGS_FILE, "w") as f:
                    json.dump(migrated, f, indent=4)
            return migrated
        except Exception:
            pass
    return dict(SETTINGS_DEFAULTS)

def save_settings_to_file(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ===================== VIDEO ID RESOLUTION =====================
VIDEO_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')
WATCH_RE    = re.compile(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})')
YT_HEADERS  = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

def _fetch(url):
    req = urllib.request.Request(url, headers=YT_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", errors="ignore")

def _extract_video_id_from_html(html):
    for pat in [
        r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"',
        r'watch\?v=([a-zA-Z0-9_-]{11})',
        r'canonical.*?watch\?v=([a-zA-Z0-9_-]{11})',
    ]:
        m = re.search(pat, html)
        if m: return m.group(1)
    return None

def resolve_video_id(user_input):
    s = user_input.strip().lstrip("@")
    if VIDEO_ID_RE.match(s): return s
    m = WATCH_RE.search(s)
    if m: return m.group(1)
    for url in [
        f"https://www.youtube.com/@{s}/live",
        f"https://www.youtube.com/@{s}",
        f"https://www.youtube.com/c/{s}/live",
        f"https://www.youtube.com/c/{s}",
        f"https://www.youtube.com/user/{s}/live",
    ]:
        try:
            vid = _extract_video_id_from_html(_fetch(url))
            if vid: return vid
        except Exception:
            continue
    return None

# ===================== BUBBLE WIDGET =====================
class BubbleWidget(QWidget):
    removed = pyqtSignal(str)

    def __init__(self, text, accent="#9146FF", parent=None):
        super().__init__(parent)
        self.text   = text
        self.accent = accent
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: white; background: transparent; border: none; font-size: 12px;")
        btn = QPushButton("✕")
        btn.setFixedSize(16, 16)
        btn.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; font-size: 10px; padding: 0; font-weight: bold; }
            QPushButton:hover { color: #ffaaaa; }
        """)
        btn.clicked.connect(lambda: self.removed.emit(self.text))
        layout.addWidget(lbl)
        layout.addWidget(btn)
        self.setStyleSheet(f"BubbleWidget {{ background-color: {accent}55; border: 1px solid {accent}99; border-radius: 10px; }}")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

class BubbleList(QWidget):
    changed = pyqtSignal(list)

    def __init__(self, placeholder="Type and press Enter...", accent="#9146FF", parent=None):
        super().__init__(parent)
        self.accent = accent
        self.items  = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumHeight(70)
        self.scroll.setMaximumHeight(120)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bubble_container = QWidget()
        self.bubble_layout    = QVBoxLayout(self.bubble_container)
        self.bubble_layout.setContentsMargins(4, 4, 4, 4)
        self.bubble_layout.setSpacing(4)
        self.bubble_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.bubble_container)
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self._add_from_input)
        outer.addWidget(self.scroll)
        outer.addWidget(self.input)

    def _add_from_input(self):
        text = self.input.text().strip()
        if text: self.add_item(text); self.input.clear()

    def add_item(self, text):
        if text in self.items: return
        self.items.append(text)
        bubble = BubbleWidget(text, self.accent)
        bubble.removed.connect(self._remove_item)
        self.bubble_layout.addWidget(bubble)
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))
        self.changed.emit(list(self.items))

    def _remove_item(self, text):
        if text in self.items: self.items.remove(text)
        for i in range(self.bubble_layout.count()):
            item = self.bubble_layout.itemAt(i)
            if item and isinstance(item.widget(), BubbleWidget) and item.widget().text == text:
                w = item.widget()
                self.bubble_layout.removeWidget(w)
                w.deleteLater()
                break
        self.changed.emit(list(self.items))

    def set_items(self, items):
        for text in items: self.add_item(text)

    def get_items(self):
        return list(self.items)

    def update_accent(self, accent):
        self.accent = accent

# ===================== TOOLTIP BUTTON =====================
def make_tooltip_btn(tip_text, accent="#9146FF"):
    btn = QPushButton("?")
    btn.setFixedSize(18, 18)
    btn.setToolTip(tip_text)
    btn.setStyleSheet(f"""
        QPushButton {{ background: #464649; color: #efeff1; border-radius: 9px; font-size: 10px; font-weight: bold; padding: 0; border: none; }}
        QPushButton:hover {{ background: {accent}; }}
    """)
    btn.setCursor(QCursor(Qt.WhatsThisCursor))
    return btn

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, channel, threshold, bypass, filters, event_flags):
        super().__init__()
        chan = channel.lower().strip().replace("#", "")
        self.channel     = f"#{chan}"
        self.threshold   = threshold
        self.bypass      = bypass
        self.filters     = filters
        self.event_flags = event_flags  # dict: show_raids, show_subs, show_bits, show_announcements, show_first_chat
        self.msg_times   = deque()
        self.is_running  = True

    def stop(self):
        self.is_running = False

    def _should_show(self, user, msg, roles, mps):
        f = self.filters
        if user.lower() in [u.lower() for u in f.get("user_blacklist", [])]: return False
        if user.lower() in [u.lower() for u in f.get("user_whitelist", [])]: return True
        msg_lower = msg.lower()
        for word in f.get("always_block_words", []):
            if word.lower() in msg_lower: return False
        is_filtering = mps >= self.threshold
        if is_filtering:
            for word in f.get("volume_block_words", []):
                if word.lower() in msg_lower: return False
        role_result = None
        for role in roles:
            rule = self.bypass.get(role, "Normal")
            if rule == "Always": return True
            if rule == "Never" and role_result is None: role_result = False
        if role_result is False: return False
        if not is_filtering: return True
        return self._is_substantive(msg_lower)

    LOW_VALUE_EXACT = {
        "lol","lmao","lmfao","gg","ggs","ez","pog","pogchamp","kekw","omegalul",
        "pepega","monkas","hi","hello","hey","yo","sup","hype","lets go","let's go",
        "wow","nice","ok","okay","xd","lul","haha","hahaha","lolol","f","w","l",
        "rip","oof","based","facts","true","same","real","fr","ngl","imo","bruh",
        "bro","omg","omfg","wtf","damn","dang","yep","yup","nope","nah","ayy",
    }
    REPEAT_CHARS = re.compile(r"(.)\1{4,}")

    def _is_substantive(self, msg_lower):
        stripped = msg_lower.strip()
        if len(stripped) < 15:
            if stripped in self.LOW_VALUE_EXACT: return False
            if "?" in stripped: return True
            return False
        if self.REPEAT_CHARS.search(stripped): return False
        tokens     = re.findall(r"\b\w+\b", stripped)
        real_words = [t for t in tokens if len(t) >= 3]
        if not tokens: return False
        if len(real_words) / len(tokens) < 0.4: return False
        if "?" in stripped: return True
        return len(real_words) >= 4

    def _role_badges_html(self, roles):
        parts = []
        if "broadcaster" in roles: parts.append("<span style='color:#FF6B35;font-weight:bold'>[B]</span>")
        if "mod"         in roles: parts.append("<span style='color:#00AD03;font-weight:bold'>[M]</span>")
        if "vip"         in roles: parts.append("<span style='color:#FF69B4;font-weight:bold'>[V]</span>")
        if "sub"         in roles: parts.append("<span style='color:#FFD700;font-weight:bold'>[S]</span>")
        return " ".join(parts) + (" " if parts else "")

    def _handle_usernotice(self, tags):
        """Parse USERNOTICE events and return formatted HTML or None."""
        msg_id   = tags.get("msg-id", "")
        user     = tags.get("display-name", tags.get("login", "Someone"))
        sys_msg  = tags.get("system-msg", "").replace("\\s", " ")

        if msg_id == "raid" and self.event_flags.get("show_raids"):
            viewer_count = tags.get("msg-param-viewerCount", "?")
            return fmt_raid(user, viewer_count)

        if msg_id in ("sub", "resub") and self.event_flags.get("show_subs"):
            months = tags.get("msg-param-cumulative-months", "")
            return fmt_sub(user, months)

        if msg_id == "subgift" and self.event_flags.get("show_subs"):
            recipient = tags.get("msg-param-recipient-display-name", "someone")
            months    = tags.get("msg-param-months", "")
            return fmt_subgift(user, recipient, months)

        if msg_id in ("submysterygift", "standardpayforward", "communitypayforward") and self.event_flags.get("show_subs"):
            count = tags.get("msg-param-mass-gift-count", "?")
            return fmt_subgift_bomb(user, count)

        if msg_id == "announcement" and self.event_flags.get("show_announcements"):
            color = tags.get("msg-param-color", "PRIMARY")
            # message text comes separately; sys_msg is the announcement body for this type
            return fmt_announcement(user, sys_msg, color) if sys_msg else None

        return None

    def run(self):
        sock = socket.socket()

        def _tick():
            while self.is_running:
                time.sleep(1.0)
                now = time.time()
                while self.msg_times and now - self.msg_times[0] > 5.0:
                    self.msg_times.popleft()
                self.stats_update.emit(len(self.msg_times) / 5.0, len(self.msg_times) / 5.0 >= self.threshold)

        import threading
        threading.Thread(target=_tick, daemon=True).start()

        try:
            self.status_msg.emit("Connecting...")
            sock.connect(("irc.chat.twitch.tv", 6667))
            sock.send(f"NICK justinfan{random.randint(10000, 99999)}\r\n".encode())
            sock.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            sock.send(f"JOIN {self.channel}\r\n".encode())
            self.status_msg.emit("Connected")

            buf = ""
            while self.is_running:
                chunk = sock.recv(4096).decode("utf-8", errors="ignore")
                if not chunk: break
                buf += chunk
                while "\r\n" in buf:
                    line, buf = buf.split("\r\n", 1)
                    if not line: continue

                    if line.startswith("PING"):
                        sock.send("PONG :tmi.twitch.tv\r\n".encode())
                        continue

                    # Parse tags
                    tags = {}
                    rest = line
                    if rest.startswith("@"):
                        tag_str, rest = rest[1:].split(" ", 1)
                        tags = dict(t.split("=", 1) for t in tag_str.split(";") if "=" in t)

                    # USERNOTICE — raids, subs, announcements
                    if "USERNOTICE" in rest:
                        html = self._handle_usernotice(tags)
                        if html:
                            self.message.emit(html)
                        continue

                    if "PRIVMSG" not in rest:
                        continue

                    user = tags.get("display-name", "User")
                    try:
                        content = rest.split("PRIVMSG", 1)[1].split(":", 1)[1]
                    except Exception:
                        content = ""

                    now = time.time()
                    self.msg_times.append(now)
                    while self.msg_times and now - self.msg_times[0] > 5.0:
                        self.msg_times.popleft()
                    mps = len(self.msg_times) / 5.0
                    self.stats_update.emit(mps, mps >= self.threshold)

                    # Bits / cheers
                    bits = tags.get("bits", "")
                    if bits and self.event_flags.get("show_bits"):
                        self.message.emit(fmt_bits(user, bits, content.strip()))
                        continue

                    badges = tags.get("badges", "")
                    roles  = []
                    if "broadcaster" in badges:       roles.append("broadcaster")
                    if tags.get("mod") == "1":        roles.append("mod")
                    if "vip" in badges:               roles.append("vip")
                    if tags.get("subscriber") == "1": roles.append("sub")

                    # First-time chatter
                    if tags.get("first-msg") == "1" and self.event_flags.get("show_first_chat"):
                        self.message.emit(fmt_first_chat(user, content.strip()))
                        continue

                    if self._should_show(user, content, roles, mps):
                        color = tags.get("color") or f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        self.message.emit(
                            f"{_platform_badge_html('twitch')}{self._role_badges_html(roles)}"
                            f"<span style='color:{color}'><b>{user}</b></span>: {content}")

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

    def __init__(self, handle, threshold, bypass_member, filters):
        super().__init__()
        self.handle        = handle
        self.threshold     = threshold
        self.bypass_member = bypass_member
        self.filters       = filters
        self.msg_times     = deque()
        self.is_running    = True

    def stop(self):
        self.is_running = False

    def _should_show(self, user, msg, is_member, mps):
        f = self.filters
        if user.lower() in [u.lower() for u in f.get("user_blacklist", [])]: return False
        if user.lower() in [u.lower() for u in f.get("user_whitelist", [])]: return True
        msg_lower = msg.lower()
        for word in f.get("always_block_words", []):
            if word.lower() in msg_lower: return False
        is_filtering = mps >= self.threshold
        if is_filtering:
            for word in f.get("volume_block_words", []):
                if word.lower() in msg_lower: return False
        if is_member:
            if self.bypass_member == "Always": return True
            if self.bypass_member == "Never":  return False
        if is_filtering: return False
        return True

    def run(self):
        self.status_msg.emit("Resolving channel...")
        video_id = resolve_video_id(self.handle)
        if not video_id:
            self.status_msg.emit("Error: Could not find live stream")
            if self.is_running: self.disconnected.emit()
            return

        self.status_msg.emit(f"Connecting... (ID: {video_id})")

        import threading
        def _tick():
            while self.is_running:
                time.sleep(1.0)
                now = time.time()
                while self.msg_times and now - self.msg_times[0] > self.CHAT_RATE_WINDOW:
                    self.msg_times.popleft()
                mps = len(self.msg_times) / self.CHAT_RATE_WINDOW
                self.stats_update.emit(mps, mps >= self.threshold)
        threading.Thread(target=_tick, daemon=True).start()

        try:
            url  = f"https://www.youtube.com/watch?v={video_id}"
            chat = ChatDownloader().get_chat(url, message_types=['text_message'])
            self.status_msg.emit("Connected")

            for message in chat:
                if not self.is_running: break
                now = time.time()
                self.msg_times.append(now)
                while self.msg_times and now - self.msg_times[0] > self.CHAT_RATE_WINDOW:
                    self.msg_times.popleft()
                mps = len(self.msg_times) / self.CHAT_RATE_WINDOW
                self.stats_update.emit(mps, mps >= self.threshold)

                user      = message.get('author', {}).get('name', 'User')
                msg       = message.get('message', '')
                badges    = message.get('author', {}).get('badges', [])
                is_member = any('member' in b.get('title', '').lower() for b in badges)

                if not msg: continue
                if self._should_show(user, msg, is_member, mps):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"{_platform_badge_html('youtube')}"
                        f"<span style='color:{color}'><b>{user}</b></span>: {msg}")

        except Exception as e:
            self.status_msg.emit(f"Error: {e}")
        finally:
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()

# ===================== MAIN CONTROLLER =====================
class ChatGateMain(QWidget):
    def __init__(self):
        super().__init__()
        self.settings    = load_settings()
        self.dark_mode   = self.settings.get("dark_mode", True)
        self.setWindowTitle("ChatGate")
        self.resize(500, 800)

        self.overlay         = ChatOverlay()
        self.overlay_active  = False
        self.irc             = None
        self.yt              = None
        self._current_accent = ACCENT[TAB_TWITCH]

        self._irc_reconnect_attempt = 0
        self._irc_reconnect_timer   = QTimer()
        self._irc_reconnect_timer.setSingleShot(True)
        self._irc_reconnect_timer.timeout.connect(self._do_irc_reconnect)
        self._last_twitch_channel   = ""

        self._yt_reconnect_attempt  = 0
        self._yt_reconnect_timer    = QTimer()
        self._yt_reconnect_timer.setSingleShot(True)
        self._yt_reconnect_timer.timeout.connect(self._do_yt_reconnect)
        self._last_yt_handle        = ""

        self._twitch_mps = 0.0
        self._yt_mps     = 0.0

        self.overlay.move(self.settings.get("pos_x", 100), self.settings.get("pos_y", 100))
        self.overlay.resize(self.settings.get("width", 400), self.settings.get("height", 600))

        self.init_ui()
        self.apply_theme()
        self.register_hotkey()
        self.sync_overlay()
        self.init_tray()

        QTimer.singleShot(100,  self._set_win32_icon)
        QTimer.singleShot(1000, self.check_for_updates)

    def _get_event_flags(self):
        return {
            "show_raids":         self.show_raids_check.isChecked(),
            "show_subs":          self.show_subs_check.isChecked(),
            "show_bits":          self.show_bits_check.isChecked(),
            "show_announcements": self.show_ann_check.isChecked(),
            "show_first_chat":    self.show_first_check.isChecked(),
        }

    def save_settings(self):
        data = {
            "twitch_channel":     self.twitch_input.text(),
            "yt_handle":          self.yt_input.text(),
            "mps":                self.mps_spin.value(),
            "opacity":            self.alpha_slider.value(),
            "pos_x":              self.overlay.x(),
            "pos_y":              self.overlay.y(),
            "width":              self.overlay.width(),
            "height":             self.overlay.height(),
            "dark_mode":          self.dark_mode,
            "font_size":          self.font_spin.value(),
            "minimize_to_tray":   self.minimize_to_tray_check.isChecked(),
            "combined_mps":       self.combined_mps_check.isChecked(),
            "bypass_broadcaster": self.bp_broadcaster.currentText(),
            "bypass_mod":         self.bp_mod.currentText(),
            "bypass_vip":         self.bp_vip.currentText(),
            "bypass_sub":         self.bp_sub.currentText(),
            "bypass_yt_member":   self.bp_yt_member.currentText(),
            "always_block_words": self.always_block_list.get_items(),
            "volume_block_words": self.volume_block_list.get_items(),
            "user_whitelist":     self.user_whitelist.get_items(),
            "user_blacklist":     self.user_blacklist.get_items(),
            **self._get_event_flags(),
        }
        save_settings_to_file(data)

    def _get_filters(self):
        return {
            "always_block_words": self.always_block_list.get_items(),
            "volume_block_words": self.volume_block_list.get_items(),
            "user_whitelist":     self.user_whitelist.get_items(),
            "user_blacklist":     self.user_blacklist.get_items(),
        }

    def _get_twitch_bypass(self):
        return {
            "broadcaster": self.bp_broadcaster.currentText(),
            "mod":         self.bp_mod.currentText(),
            "vip":         self.bp_vip.currentText(),
            "sub":         self.bp_sub.currentText(),
        }

    def apply_theme(self, accent=None):
        if accent is None: accent = self._current_accent
        self._current_accent = accent
        self.setStyleSheet(get_theme(self.dark_mode, accent))
        self.theme_btn.setText("☀ Light Mode" if self.dark_mode else "☾ Dark Mode")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.save_settings()

    def _on_tab_changed(self, index):
        if not hasattr(self, 'theme_btn'): return
        accent = ACCENT.get(index, "#9146FF")
        self.apply_theme(accent)
        for bl in [self.always_block_list, self.volume_block_list, self.user_whitelist, self.user_blacklist]:
            bl.update_accent(accent)

    def init_tray(self):
        icon = QIcon(get_icon_path())
        self.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("ChatGate")
        menu = QMenu()
        for label, slot in [
            ("Show Controller", self.restore_from_tray),
            ("Toggle Overlay",  self._hotkey_toggle),
            (None, None),
            ("Quit",            self.quit_app),
        ]:
            if label is None: menu.addSeparator()
            else:
                a = QAction(label, self); a.triggered.connect(slot); menu.addAction(a)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.restore_from_tray() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def restore_from_tray(self):
        self.showNormal(); self.activateWindow(); self.raise_()

    def quit_app(self):
        self.overlay.hide(); self.tray.hide(); QApplication.quit()

    def closeEvent(self, event):
        if self.minimize_to_tray_check.isChecked():
            event.ignore(); self.hide()
            self.tray.showMessage("ChatGate",
                "Running in the background. Double-click the tray icon to restore.",
                QSystemTrayIcon.Information, 2000)
        else:
            self.overlay.hide(); self.tray.hide(); event.accept()

    def _set_win32_icon(self):
        try:
            ico = get_icon_path()
            if not os.path.exists(ico): return
            hicon = ctypes.windll.user32.LoadImageW(None, ico, 1, 0, 0, 0x0010 | 0x0040)
            hwnd  = int(self.winId())
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 0, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, 0x0080, 1, hicon)
        except Exception:
            pass

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.ver_label = QLabel(f"v{CURRENT_VERSION}")
        hotkey_lbl = QLabel("Ctrl+Shift+O — Toggle Overlay")
        hotkey_lbl.setStyleSheet("color: #666; font-size: 11px;")
        self.mps_label = QLabel("MPS: 0.0")
        header.addWidget(self.ver_label); header.addStretch()
        header.addWidget(hotkey_lbl);    header.addStretch()
        header.addWidget(self.mps_label)
        layout.addLayout(header)

        bw_label = QLabel("⚠ Game must run in Borderless Windowed mode for overlay to appear on top.")
        bw_label.setStyleSheet("color: #888; font-size: 10px;")
        bw_label.setWordWrap(True)
        layout.addWidget(bw_label)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.addTab(self._build_twitch_tab(),  "Twitch")
        self.tabs.addTab(self._build_youtube_tab(), "YouTube")
        self.tabs.addTab(self._build_filters_tab(), "Filters")
        layout.addWidget(self.tabs)

        layout.addWidget(self._hline())

        self.move_btn = QPushButton("UNLOCK OVERLAY TO MOVE")
        self.move_btn.setCheckable(True)
        self.move_btn.toggled.connect(self.toggle_move_mode)
        layout.addWidget(self.move_btn)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("<b>OPACITY</b>"))
        opacity_row.addWidget(make_tooltip_btn(
            "Controls how transparent the chat overlay background is.\n100 = fully opaque, 10 = nearly invisible."))
        opacity_row.addStretch()
        layout.addLayout(opacity_row)
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(10, 100)
        self.alpha_slider.setValue(self.settings["opacity"])
        self.alpha_slider.valueChanged.connect(self.sync_overlay)
        layout.addWidget(self.alpha_slider)

        fm_row = QHBoxLayout()
        self.font_spin = QSpinBox()
        self.font_spin.setRange(12, 60)
        self.font_spin.setValue(self.settings["font_size"])
        self.font_spin.valueChanged.connect(self.sync_overlay)
        self.mps_spin = QDoubleSpinBox()
        self.mps_spin.setRange(0.1, 25.0)
        self.mps_spin.setValue(self.settings["mps"])
        self.mps_spin.valueChanged.connect(self.save_settings)
        fm_row.addWidget(QLabel("Font:")); fm_row.addWidget(self.font_spin)
        fm_row.addWidget(make_tooltip_btn("Font size of messages in the overlay."))
        fm_row.addSpacing(12)
        fm_row.addWidget(QLabel("MPS Limit:")); fm_row.addWidget(self.mps_spin)
        fm_row.addWidget(make_tooltip_btn(
            "Messages Per Second threshold.\nWhen chat exceeds this speed, the filter activates."))
        fm_row.addStretch()
        layout.addLayout(fm_row)

        cmps_row = QHBoxLayout()
        self.combined_mps_check = QCheckBox("Combined MPS calculation")
        self.combined_mps_check.setChecked(self.settings.get("combined_mps", True))
        self.combined_mps_check.stateChanged.connect(self.save_settings)
        cmps_row.addWidget(self.combined_mps_check)
        cmps_row.addWidget(make_tooltip_btn(
            "Combined: all platforms share one MPS pool.\nSeparated: each platform tracks its own speed."))
        cmps_row.addStretch()
        layout.addLayout(cmps_row)

        bottom_row = QHBoxLayout()
        self.minimize_to_tray_check = QCheckBox("Minimize to tray on close")
        self.minimize_to_tray_check.setChecked(self.settings.get("minimize_to_tray", True))
        self.minimize_to_tray_check.stateChanged.connect(self.save_settings)
        self.theme_btn = QPushButton("")
        self.theme_btn.clicked.connect(self.toggle_theme)
        bottom_row.addWidget(self.minimize_to_tray_check); bottom_row.addStretch()
        bottom_row.addWidget(self.theme_btn)
        layout.addLayout(bottom_row)

    def _hline(self):
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet("color: #464649;")
        return line

    def _bypass_combo(self, setting_key):
        cb = QComboBox(); cb.addItems(BYPASS_OPTIONS)
        cb.setCurrentText(self.settings.get(setting_key, "Normal"))
        cb.currentTextChanged.connect(self.save_settings)
        return cb

    def _build_twitch_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        # Connect row
        row = QHBoxLayout()
        self.twitch_input = QLineEdit(self.settings.get("twitch_channel", ""))
        self.twitch_input.setPlaceholderText("Channel name")
        self.twitch_input.textChanged.connect(self.save_settings)
        self.twitch_connect_btn = QPushButton("CONNECT")
        self.twitch_connect_btn.clicked.connect(self.start_twitch)
        row.addWidget(self.twitch_input); row.addWidget(self.twitch_connect_btn)
        lay.addLayout(row)

        self.twitch_status = QLabel("OFFLINE")
        self.twitch_status.setStyleSheet("font-weight: bold;")
        lay.addWidget(self.twitch_status)
        lay.addWidget(self._hline())

        # Role bypass
        bh = QHBoxLayout()
        bh.addWidget(QLabel("<b>ALLOW MESSAGES</b>"))
        bh.addWidget(make_tooltip_btn(
            "Always: always show regardless of filter.\nNormal: goes through MPS filter.\nNever: always hidden."))
        bh.addStretch()
        lay.addLayout(bh)

        self.bp_broadcaster = self._bypass_combo("bypass_broadcaster")
        self.bp_mod         = self._bypass_combo("bypass_mod")
        self.bp_vip         = self._bypass_combo("bypass_vip")
        self.bp_sub         = self._bypass_combo("bypass_sub")

        for label, combo in [("Broadcaster:", self.bp_broadcaster), ("Mods:", self.bp_mod),
                              ("VIPs:", self.bp_vip), ("Subs:", self.bp_sub)]:
            r = QHBoxLayout(); lbl = QLabel(label); lbl.setFixedWidth(90)
            r.addWidget(lbl); r.addWidget(combo); r.addStretch(); lay.addLayout(r)

        lay.addWidget(self._hline())

        # ---- Event toggles ----
        ev_group = QGroupBox("Channel Events")
        ev_lay   = QVBoxLayout(ev_group)
        ev_lay.setSpacing(6)

        self.show_raids_check = QCheckBox("Show Raids")
        self.show_raids_check.setChecked(self.settings.get("show_raids", True))
        self.show_raids_check.stateChanged.connect(self.save_settings)

        self.show_subs_check = QCheckBox("Show Subs / Resubs / Gift Subs")
        self.show_subs_check.setChecked(self.settings.get("show_subs", True))
        self.show_subs_check.stateChanged.connect(self.save_settings)

        self.show_bits_check = QCheckBox("Show Bits / Cheers")
        self.show_bits_check.setChecked(self.settings.get("show_bits", True))
        self.show_bits_check.stateChanged.connect(self.save_settings)

        self.show_ann_check = QCheckBox("Show Announcements")
        self.show_ann_check.setChecked(self.settings.get("show_announcements", True))
        self.show_ann_check.stateChanged.connect(self.save_settings)

        self.show_first_check = QCheckBox("Highlight First-Time Chatters")
        self.show_first_check.setChecked(self.settings.get("show_first_chat", False))
        self.show_first_check.stateChanged.connect(self.save_settings)

        for cb in [self.show_raids_check, self.show_subs_check, self.show_bits_check,
                   self.show_ann_check, self.show_first_check]:
            ev_lay.addWidget(cb)

        lay.addWidget(ev_group)
        lay.addWidget(self._hline())

        # ---- Test buttons ----
        test_group = QGroupBox("Preview Events")
        test_lay   = QVBoxLayout(test_group)
        test_lay.setSpacing(4)
        test_lbl = QLabel("Send a sample event to the overlay:")
        test_lbl.setStyleSheet("font-size: 11px; color: #888;")
        test_lay.addWidget(test_lbl)

        btn_row1 = QHBoxLayout()
        btn_row2 = QHBoxLayout()

        def test_btn(label, fn):
            b = QPushButton(label)
            b.clicked.connect(lambda: (self._show_overlay(), self.overlay.add_message(fn())))
            return b

        btn_row1.addWidget(test_btn("🚨 Raid",    lambda: fmt_raid("ExampleStreamer", 420)))
        btn_row1.addWidget(test_btn("⭐ Sub",     lambda: fmt_sub("CoolViewer", "6")))
        btn_row1.addWidget(test_btn("🎁 Gift Sub",lambda: fmt_subgift("GenerousGuy", "LuckyViewer", "1")))
        btn_row2.addWidget(test_btn("🎁 Sub Bomb",lambda: fmt_subgift_bomb("BigDonor", "10")))
        btn_row2.addWidget(test_btn("💎 Bits",    lambda: fmt_bits("CheerPerson", "500", "Great stream!")))
        btn_row2.addWidget(test_btn("📢 Announce",lambda: fmt_announcement("Moderator", "Welcome everyone!", "BLUE")))

        first_row = QHBoxLayout()
        first_row.addWidget(test_btn("👋 First Chat", lambda: fmt_first_chat("NewViewer", "Hello! First time here!")))
        first_row.addStretch()

        test_lay.addLayout(btn_row1)
        test_lay.addLayout(btn_row2)
        test_lay.addLayout(first_row)
        lay.addWidget(test_group)

        lay.addStretch()
        return tab

    def _build_youtube_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        row = QHBoxLayout()
        self.yt_input = QLineEdit(self.settings.get("yt_handle", ""))
        self.yt_input.setPlaceholderText("@handle, URL, or video ID")
        self.yt_input.textChanged.connect(self.save_settings)
        self.yt_connect_btn = QPushButton("CONNECT")
        self.yt_connect_btn.clicked.connect(self.start_youtube)
        row.addWidget(self.yt_input); row.addWidget(self.yt_connect_btn)
        lay.addLayout(row)

        self.yt_status = QLabel("OFFLINE")
        self.yt_status.setStyleSheet("font-weight: bold;")
        lay.addWidget(self.yt_status)
        lay.addWidget(self._hline())

        bh = QHBoxLayout()
        bh.addWidget(QLabel("<b>ALLOW MESSAGES</b>"))
        bh.addWidget(make_tooltip_btn(
            "Always: member messages always show.\nNormal: members go through the MPS filter.\nNever: member messages are always hidden.",
            accent="#FF0000"))
        bh.addStretch()
        lay.addLayout(bh)

        self.bp_yt_member = self._bypass_combo("bypass_yt_member")
        r = QHBoxLayout(); lbl = QLabel("Members:"); lbl.setFixedWidth(90)
        r.addWidget(lbl); r.addWidget(self.bp_yt_member); r.addStretch()
        lay.addLayout(r)

        if not YT_AVAILABLE:
            msg  = f"⚠ YouTube unavailable: {YT_ERROR}" if YT_ERROR else "⚠ chat-downloader not installed."
            warn = QLabel(msg)
            warn.setStyleSheet("color: #ff4444;")
            warn.setWordWrap(True)
            lay.addWidget(warn)
            self.yt_connect_btn.setEnabled(False)

        lay.addStretch()
        return tab

    def _build_filters_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        accent = self._current_accent

        for header_text, tip, attr, setting_key in [
            ("<b>ALWAYS BLOCK WORDS</b>",
             "Messages containing any of these words will NEVER appear in the overlay.",
             "always_block_list", "always_block_words"),
            ("<b>HIGH VOLUME BLOCK WORDS</b>",
             "Blocked only when the filter is active (chat exceeds MPS limit).",
             "volume_block_list", "volume_block_words"),
            ("<b>USER WHITELIST</b>",
             "These users always get through, bypassing all filters.",
             "user_whitelist", "user_whitelist"),
            ("<b>USER BLACKLIST</b>",
             "These users are never shown, regardless of any other settings.",
             "user_blacklist", "user_blacklist"),
        ]:
            h = QHBoxLayout()
            h.addWidget(QLabel(header_text))
            h.addWidget(make_tooltip_btn(tip))
            h.addStretch()
            lay.addLayout(h)
            bl = BubbleList("Type and press Enter...", accent)
            bl.set_items(self.settings.get(setting_key, []))
            bl.changed.connect(lambda _: self.save_settings())
            setattr(self, attr, bl)
            lay.addWidget(bl)
            lay.addWidget(self._hline())

        lay.addStretch()
        return tab

    def sync_overlay(self):
        self.overlay.update_style(self.font_spin.value(), self.alpha_slider.value() / 100.0)
        self.overlay.resize(self.settings.get("width", 400), self.overlay.height())
        self.save_settings()

    def toggle_move_mode(self, unlocked):
        self.move_btn.setText("LOCK POSITION" if unlocked else "UNLOCK OVERLAY TO MOVE")
        self.overlay.set_click_through(not unlocked)
        if unlocked: self.overlay.show()
        else:        self.save_settings()

    def register_hotkey(self):
        try:
            ctypes.windll.user32.RegisterHotKey(int(self.winId()), HOTKEY_ID, 0x0002 | 0x0004, ord("O"))
        except: pass

    def _hotkey_toggle(self):
        self.overlay_active = not self.overlay_active
        self.overlay.show() if self.overlay_active else self.overlay.hide()
        if self.overlay_active: self.overlay.set_click_through(True)

    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self._hotkey_toggle(); return True, 0
        return super().nativeEvent(eventType, message)

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
        self.irc = IRCThread(
            self._last_twitch_channel, self.mps_spin.value(),
            self._get_twitch_bypass(), self._get_filters(), self._get_event_flags())
        self.irc.message.connect(self.overlay.add_message)
        self.irc.stats_update.connect(lambda m, f: self._update_stats(m, f, "twitch"))
        self.irc.status_msg.connect(lambda s: self.twitch_status.setText(s.upper()))
        self.irc.disconnected.connect(self._on_irc_disconnected)
        self.irc.start()

    def _on_irc_disconnected(self):
        delay = RECONNECT_DELAYS[min(self._irc_reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
        self._irc_reconnect_attempt += 1
        self.twitch_status.setText(f"RECONNECTING IN {delay}s...")
        self._irc_reconnect_timer.start(delay * 1000)

    def _do_irc_reconnect(self):
        if self._last_twitch_channel: self._launch_irc()

    def start_youtube(self):
        if not YT_AVAILABLE: return
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
            self._last_yt_handle, self.mps_spin.value(),
            self.bp_yt_member.currentText(), self._get_filters())
        self.yt.message.connect(self.overlay.add_message)
        self.yt.stats_update.connect(lambda m, f: self._update_stats(m, f, "youtube"))
        self.yt.status_msg.connect(lambda s: self.yt_status.setText(s.upper()))
        self.yt.disconnected.connect(self._on_yt_disconnected)
        self.yt.start()

    def _on_yt_disconnected(self):
        delay = RECONNECT_DELAYS[min(self._yt_reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
        self._yt_reconnect_attempt += 1
        self.yt_status.setText(f"RECONNECTING IN {delay}s...")
        self._yt_reconnect_timer.start(delay * 1000)

    def _do_yt_reconnect(self):
        if self._last_yt_handle: self._launch_yt()

    def _show_overlay(self):
        if not self.overlay_active:
            self.overlay_active = True
            self.overlay.show()
            self.overlay.set_click_through(True)

    def _update_stats(self, mps, filtering, platform):
        combined  = self.combined_mps_check.isChecked()
        threshold = self.mps_spin.value()

        if self.irc is not None: self.irc.threshold = threshold
        if self.yt  is not None: self.yt.threshold  = threshold

        if not combined:
            if platform == "twitch": self._twitch_mps = mps
            else:                    self._yt_mps     = mps

        is_filtering = mps >= threshold
        gate_color   = "#ff4444" if is_filtering else "#44cc44"
        gate_text    = "🔴 GATE CLOSED" if is_filtering else "🟢 GATE OPEN"
        status_text  = f"CONNECTED  |  {gate_text}  |  MPS: {mps:.1f}"

        if combined:
            self.mps_label.setText(f"MPS: {mps:.1f}")
            self.mps_label.setStyleSheet(f"color: {gate_color}; font-weight: bold;")
            if platform == "twitch":
                self.twitch_status.setText(status_text)
                self.twitch_status.setStyleSheet(f"font-weight: bold; color: {gate_color};")
            else:
                self.yt_status.setText(status_text)
                self.yt_status.setStyleSheet(f"font-weight: bold; color: {gate_color};")
        else:
            if platform == "twitch":
                self.twitch_status.setText(status_text)
                self.twitch_status.setStyleSheet(f"font-weight: bold; color: {gate_color};")
            else:
                self.yt_status.setText(status_text)
                self.yt_status.setStyleSheet(f"font-weight: bold; color: {gate_color};")
            twitch_active = self.irc is not None and self.irc.is_running
            yt_active     = self.yt  is not None and self.yt.is_running
            display_mps   = max(
                self._twitch_mps if twitch_active else 0.0,
                self._yt_mps     if yt_active     else 0.0)
            self.mps_label.setText(f"MPS: {display_mps:.1f}")
            self.mps_label.setStyleSheet("color: #888; font-weight: bold;")

    def check_for_updates(self):
        try:
            headers   = {'User-Agent': 'Mozilla/5.0 (ChatGate-Updater)'}
            current_v = version.parse(CURRENT_VERSION.lower().replace("v", "").strip())
            latest_v  = current_v
            latest_tag, latest_url = None, f"https://github.com/{GITHUB_REPO}/releases"

            for endpoint, url_builder in [
                (f"https://api.github.com/repos/{GITHUB_REPO}/releases",
                 lambda item: item.get("html_url", latest_url)),
                (f"https://api.github.com/repos/{GITHUB_REPO}/tags",
                 lambda item: f"https://github.com/{GITHUB_REPO}/tags"),
            ]:
                try:
                    req = urllib.request.Request(endpoint, headers=headers)
                    with urllib.request.urlopen(req, timeout=5) as r:
                        for item in json.loads(r.read().decode()):
                            tag = item.get("tag_name") or item.get("name", "")
                            try:
                                v = version.parse(tag.lower().replace("v", "").strip())
                                if v > latest_v:
                                    latest_v = v; latest_tag = tag; latest_url = url_builder(item)
                            except Exception: pass
                except Exception: pass

            if latest_tag:
                self.ver_label.setText(
                    f"<a href='{latest_url}' style='color:#00ff7f; text-decoration:none;'>"
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