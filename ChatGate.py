import socket
import random
import re
import sys
import json
import os
import time
from collections import deque
from difflib import SequenceMatcher
import urllib.request
from packaging import version

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextBrowser, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QTextCursor

# ===================== CONSTANTS =====================
SERVER = "irc.chat.twitch.tv"
PORT = 6667
SETTINGS_FILE = "settings.json"
CHAT_RATE_WINDOW = 5.0
MY_NAME = "yourusername"

CURRENT_VERSION = "0.1.1-beta"
GITHUB_REPO = "twhippp/ChatGate"  # replace with actual GitHub repo path

LOW_VALUE = {"gg","lol","lmao","pog","kekw","ez","nice","wow","ok","bruh"}
GREETINGS = {"hi","hello","hey","sup","yo","hiya","good morning","good evening"}
REPEAT_CHARS = re.compile(r"(.)\1{4,}")
REPEATED_WORD = re.compile(r"\b(\w{1,4})\b(?:\s+\1\b){2,}", re.I)
EMOTE_PATTERN = re.compile(r":[a-zA-Z0-9_]+:")

# ===================== SETTINGS =====================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# ===================== FILTER LOGIC =====================
def tokenize(text):
    return re.findall(r"\w+", text.lower())

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def is_greeting(msg):
    return msg.lower().strip() in GREETINGS

def is_substantive(msg, min_words=3, max_emote_ratio=0.5):
    tokens = tokenize(msg)
    if len(tokens) < min_words:
        return False
    if REPEAT_CHARS.search(msg) or REPEATED_WORD.search(msg):
        return False
    emotes = EMOTE_PATTERN.findall(msg)
    if tokens and len(emotes)/len(tokens) > max_emote_ratio:
        return False
    return True

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message = pyqtSignal(str)
    filter_state = pyqtSignal(bool, float)
    connected = pyqtSignal(bool)

    def __init__(self, channel, mps_threshold, role_bypass, cooldown_time=3.0, similarity_threshold=0.75):
        super().__init__()
        self.channel = channel.lower()
        self.nick = f"justinfan{random.randint(10000,99999)}"
        self.mps_threshold = mps_threshold
        self.role_bypass = role_bypass
        self.msg_times = deque()
        self.user_last_msg = {}
        self.recent_msgs = deque(maxlen=50)
        self.cooldown_time = cooldown_time
        self.similarity_threshold = similarity_threshold

    def update_threshold(self, value):
        self.mps_threshold = value

    def update_bypass(self, bypass):
        self.role_bypass = bypass

    def run(self):
        sock = socket.socket()
        try:
            sock.connect((SERVER, PORT))
            sock.sendall(f"NICK {self.nick}\r\n".encode())
            sock.sendall(b"CAP REQ :twitch.tv/tags\r\n")
            sock.sendall(f"JOIN #{self.channel}\r\n".encode())
        except Exception:
            self.connected.emit(False)
            return

        joined = False
        buffer = ""
        while True:
            buffer += sock.recv(4096).decode(errors="ignore")
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                if line.startswith("PING"):
                    sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                    continue

                if not joined:
                    if f"JOIN #{self.channel}" in line and self.nick in line:
                        self.connected.emit(True)
                        joined = True
                    elif "NOTICE" in line and "cannot join channel" in line.lower():
                        self.connected.emit(False)
                        return

                if "PRIVMSG" not in line:
                    continue

                now = time.time()
                self.msg_times.append(now)
                while self.msg_times and now - self.msg_times[0] > CHAT_RATE_WINDOW:
                    self.msg_times.popleft()
                mps = len(self.msg_times)/CHAT_RATE_WINDOW
                filter_active = mps >= self.mps_threshold
                self.filter_state.emit(filter_active, mps)

                tags_part, rest = line.split(" ",1)
                _, msg = rest.split(" :",1)
                tags = dict(t.split("=",1) for t in tags_part[1:].split(";") if "=" in t)
                user = tags.get("display-name","user")
                msg_text = msg.strip()

                roles = []
                role_keys = set()
                if tags.get("broadcaster")=="1":
                    roles.append(("BROADCASTER","red"))
                    role_keys.add("broadcaster")
                if tags.get("mod")=="1":
                    roles.append(("MOD","green"))
                    role_keys.add("mod")
                if "vip" in tags.get("badges",""):
                    roles.append(("VIP","pink"))
                    role_keys.add("vip")
                if tags.get("subscriber")=="1":
                    roles.append(("SUB","gold"))
                    role_keys.add("sub")
                bypass = any(self.role_bypass.get(r,False) for r in role_keys)

                last_msg = self.user_last_msg.get(user, ("",0))
                if now - last_msg[1] < self.cooldown_time and similarity(msg_text,last_msg[0]) > 0.8:
                    continue
                self.user_last_msg[user] = (msg_text, now)

                if not bypass:
                    blocked = False
                    for recent in self.recent_msgs:
                        if similarity(msg_text,recent) >= self.similarity_threshold:
                            blocked = True
                            break
                    if blocked:
                        continue
                self.recent_msgs.append(msg_text)

                min_words = 3 + int(mps / 2)
                if filter_active and not bypass:
                    if not is_greeting(msg_text) and not is_substantive(msg_text, min_words):
                        continue

                role_html = " ".join(f"<span style='color:{c}'>[{n}]</span>" for n,c in roles)
                msg_html = msg_text
                if MY_NAME.lower() in msg_text.lower():
                    msg_html = re.sub(f"({MY_NAME})", r"<b style='color:#ff0'>\1</b>", msg_html, flags=re.I)
                name_color = f"hsl({abs(hash(user)) % 360},100%,70%)"
                html = f"{role_html} <span style='color:{name_color}'>{user}</span>: {msg_html}"
                self.message.emit(html)

# ===================== GUI =====================
class ChatGate(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatGate")
        self.resize(640,840)
        self.settings = load_settings()
        self.dark_mode = self.settings.get("dark_mode", True)

        self.channel_input = QLineEdit(self.settings.get("channel",""))
        self.connect_btn = QPushButton("Connect")
        self.font_size = QSpinBox()
        self.font_size.setRange(10,30)
        self.font_size.setValue(self.settings.get("font_size",14))
        self.mps_spin = QDoubleSpinBox()
        self.mps_spin.setRange(0.2,20)
        self.mps_spin.setSingleStep(0.2)
        self.mps_spin.setValue(self.settings.get("mps_threshold",3.0))
        self.bypass_checks = {k:QCheckBox(f"{k.capitalize()} bypass") for k in ["broadcaster","mod","vip","sub"]}
        for k, cb in self.bypass_checks.items():
            cb.setChecked(self.settings.get(f"bypass_{k}",True))
        self.chat = QTextBrowser()
        self.filter_label = QLabel("FILTER OFF")
        self.filter_label.setStyleSheet("color:gray")
        self.toggle_theme_btn = QPushButton("Toggle Theme")
        self.toggle_theme_btn.clicked.connect(self.toggle_theme)

        self.connection_label = QLabel("Not connected")
        self.update_label = QLabel("Checking for updates...")

        self.apply_theme()
        self.apply_font()

        top = QHBoxLayout()
        top.addWidget(QLabel("Channel"))
        top.addWidget(self.channel_input)
        top.addWidget(self.connect_btn)
        top.addWidget(QLabel("Font"))
        top.addWidget(self.font_size)
        top.addWidget(QLabel("MPS"))
        top.addWidget(self.mps_spin)
        top.addWidget(self.toggle_theme_btn)

        status_row = QHBoxLayout()
        status_row.addWidget(self.connection_label)
        status_row.addWidget(self.update_label)

        bypass_row = QHBoxLayout()
        for cb in self.bypass_checks.values():
            bypass_row.addWidget(cb)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(bypass_row)
        layout.addWidget(self.filter_label)
        layout.addLayout(status_row)
        layout.addWidget(self.chat)

        self.thread = None
        self.connect_btn.clicked.connect(self.start_chat)
        self.font_size.valueChanged.connect(self.update_font)
        self.mps_spin.valueChanged.connect(self.update_threshold)
        for cb in self.bypass_checks.values():
            cb.stateChanged.connect(self.update_bypass)

        self.fade_timer = QTimer()
        self.fade_timer.setInterval(2000)
        self.fade_timer.timeout.connect(self.fade_messages)
        self.fade_timer.start()
        self.message_ages = []

        self.check_for_updates()

    def apply_theme(self):
        bg = "#18181b" if self.dark_mode else "#ffffff"
        fg = "white" if self.dark_mode else "black"
        self.chat.setStyleSheet(f"background:{bg};color:{fg};font-size:{self.font_size.value()}px;")
        self.setStyleSheet(f"background:{'#121212' if self.dark_mode else '#f0f0f0'};color:{fg};")

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.settings["dark_mode"] = self.dark_mode
        save_settings(self.settings)
        self.apply_theme()

    def apply_font(self):
        fg = "white" if self.dark_mode else "black"
        bg = "#18181b" if self.dark_mode else "#ffffff"
        self.chat.setStyleSheet(f"background:{bg};color:{fg};font-size:{self.font_size.value()}px;")

    def current_bypass(self):
        return {k:cb.isChecked() for k,cb in self.bypass_checks.items()}

    def update_font(self, size):
        self.apply_font()
        self.settings["font_size"] = size
        save_settings(self.settings)

    def update_threshold(self, value):
        self.settings["mps_threshold"] = value
        save_settings(self.settings)
        if self.thread:
            self.thread.update_threshold(value)

    def update_bypass(self):
        bypass=self.current_bypass()
        for k,v in bypass.items():
            self.settings[f"bypass_{k}"] = v
        save_settings(self.settings)
        if self.thread:
            self.thread.update_bypass(bypass)

    def start_chat(self):
        channel=self.channel_input.text().strip()
        if not channel:
            return
        self.settings["channel"] = channel
        save_settings(self.settings)
        if self.thread:
            self.thread.terminate()
        self.chat.clear()
        self.message_ages=[]
        self.thread = IRCThread(channel, self.mps_spin.value(), self.current_bypass())
        self.thread.message.connect(self.add_message)
        self.thread.filter_state.connect(self.update_filter_label)
        self.thread.connected.connect(self.update_connection_status)
        self.thread.start()
        self.connection_label.setText("Connecting...")
        self.connection_label.setStyleSheet("color:orange;font-weight:bold")

    def update_connection_status(self, success):
        if success:
            self.connection_label.setText("Successfully joined channel")
            self.connection_label.setStyleSheet("color:green;font-weight:bold")
        else:
            self.connection_label.setText("Connection failed")
            self.connection_label.setStyleSheet("color:red;font-weight:bold")

    def add_message(self, html):
        self.chat.moveCursor(QTextCursor.End)
        self.chat.insertHtml(html + "<br>")
        self.chat.moveCursor(QTextCursor.End)
        self.message_ages.append(time.time())

    def update_filter_label(self, active, mps):
        self.filter_label.setText(f"{'FILTER ACTIVE' if active else 'FILTER OFF'} ({mps:.1f} MPS)")
        self.filter_label.setStyleSheet(f"color:{'red' if active else 'gray'};font-weight:bold")

    def fade_messages(self):
        pass

    def check_for_updates(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if not data:
                    self.update_label.setText("No releases found")
                    self.update_label.setStyleSheet("color:gray;font-weight:bold")
                    return
                latest_tag = data[0].get("tag_name", "")
                current_v = version.parse(CURRENT_VERSION)
                latest_v = version.parse(latest_tag)
                if latest_v > current_v:
                    self.update_label.setText(f"Update available: {latest_tag}")
                    self.update_label.setStyleSheet("color:blue;font-weight:bold")
                else:
                    self.update_label.setText("Up to date")
                    self.update_label.setStyleSheet("color:green;font-weight:bold")
        except Exception:
            self.update_label.setText("Update check failed")
            self.update_label.setStyleSheet("color:red;font-weight:bold")

# ===================== ENTRY =====================
if __name__=="__main__":
    app=QApplication(sys.argv)
    win=ChatGate()
    win.show()
    sys.exit(app.exec_())
