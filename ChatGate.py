import socket
import random
import re
import sys
import json
import os
import time
from collections import deque
from difflib import SequenceMatcher

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
    """
    Determines if a message is meaningful enough to pass the filter.
    - Accepts normal sentences with enough words.
    - Blocks excessive repeats, emote spam, or short meaningless messages.
    """
    tokens = tokenize(msg)
    
    # Block very short messages
    if len(tokens) < min_words:
        return False

    # Block repeated characters (aaaaa) or repeated short words (uh uh uh)
    if REPEAT_CHARS.search(msg) or REPEATED_WORD.search(msg):
        return False

    # Block if emotes exceed threshold
    emotes = EMOTE_PATTERN.findall(msg)
    if tokens and len(emotes)/len(tokens) > max_emote_ratio:
        return False

    # Everything else is considered substantive
    return True

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message = pyqtSignal(str)
    filter_state = pyqtSignal(bool, float)  # active, MPS

    def __init__(self, channel, mps_threshold, role_bypass, cooldown_time=3.0, similarity_threshold=0.75):
        super().__init__()
        self.channel = channel.lower()
        self.nick = f"justinfan{random.randint(10000,99999)}"
        self.mps_threshold = mps_threshold
        self.role_bypass = role_bypass
        self.msg_times = deque()
        self.user_last_msg = {}  # username -> last message
        self.recent_msgs = deque(maxlen=50)
        self.cooldown_time = cooldown_time
        self.similarity_threshold = similarity_threshold

    def update_threshold(self, value):
        self.mps_threshold = value

    def update_bypass(self, bypass):
        self.role_bypass = bypass

    def run(self):
        sock = socket.socket()
        sock.connect((SERVER, PORT))
        sock.sendall(f"NICK {self.nick}\r\n".encode())
        sock.sendall(b"CAP REQ :twitch.tv/tags\r\n")
        sock.sendall(f"JOIN #{self.channel}\r\n".encode())

        buffer = ""
        while True:
            buffer += sock.recv(4096).decode(errors="ignore")
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                if line.startswith("PING"):
                    sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                    continue
                if "PRIVMSG" not in line:
                    continue

                # ----- rate tracking -----
                now = time.time()
                self.msg_times.append(now)
                while self.msg_times and now - self.msg_times[0] > CHAT_RATE_WINDOW:
                    self.msg_times.popleft()
                mps = len(self.msg_times)/CHAT_RATE_WINDOW
                filter_active = mps >= self.mps_threshold
                self.filter_state.emit(filter_active, mps)

                # ----- parse IRC -----
                tags_part, rest = line.split(" ",1)
                _, msg = rest.split(" :",1)
                tags = dict(t.split("=",1) for t in tags_part[1:].split(";") if "=" in t)
                user = tags.get("display-name","user")
                msg_text = msg.strip()

                # ----- roles -----
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

                # ----- cooldown check -----
                last_msg = self.user_last_msg.get(user, ("",0))
                if now - last_msg[1] < self.cooldown_time and similarity(msg_text,last_msg[0]) > 0.8:
                    continue
                self.user_last_msg[user] = (msg_text, now)

                # ----- similarity detection -----
                if not bypass:
                    blocked = False
                    for recent in self.recent_msgs:
                        if similarity(msg_text,recent) >= self.similarity_threshold:
                            blocked = True
                            break
                    if blocked:
                        continue
                self.recent_msgs.append(msg_text)

                # ----- adaptive min length -----
                min_words = 3 + int(mps / 2)  # slower growth to allow normal sentences
                if filter_active and not bypass:
                    if not is_greeting(msg_text) and not is_substantive(msg_text, min_words):
                        continue

                # ----- render -----
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
        self.apply_font()
        self.filter_label = QLabel("FILTER OFF")
        self.filter_label.setStyleSheet("color:gray")

        top = QHBoxLayout()
        top.addWidget(QLabel("Channel"))
        top.addWidget(self.channel_input)
        top.addWidget(self.connect_btn)
        top.addWidget(QLabel("Font"))
        top.addWidget(self.font_size)
        top.addWidget(QLabel("MPS"))
        top.addWidget(self.mps_spin)

        bypass_row = QHBoxLayout()
        for cb in self.bypass_checks.values():
            bypass_row.addWidget(cb)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(bypass_row)
        layout.addWidget(self.filter_label)
        layout.addWidget(self.chat)

        self.thread = None
        self.connect_btn.clicked.connect(self.start_chat)
        self.font_size.valueChanged.connect(self.update_font)
        self.mps_spin.valueChanged.connect(self.update_threshold)
        for cb in self.bypass_checks.values():
            cb.stateChanged.connect(self.update_bypass)

        # message fade timer
        self.fade_timer = QTimer()
        self.fade_timer.setInterval(2000)
        self.fade_timer.timeout.connect(self.fade_messages)
        self.fade_timer.start()
        self.message_ages = []

    def current_bypass(self):
        return {k:cb.isChecked() for k,cb in self.bypass_checks.items()}

    def apply_font(self):
        self.chat.setStyleSheet(f"background:#18181b;color:white;font-size:{self.font_size.value()}px;")

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
        self.thread.start()

    def add_message(self, html):
        self.chat.moveCursor(QTextCursor.End)
        self.chat.insertHtml(html + "<br>")
        self.chat.moveCursor(QTextCursor.End)
        self.message_ages.append(time.time())

    def update_filter_label(self, active, mps):
        self.filter_label.setText(f"{'FILTER ACTIVE' if active else 'FILTER OFF'} ({mps:.1f} MPS)")
        self.filter_label.setStyleSheet(f"color:{'red' if active else 'gray'};font-weight:bold")

    def fade_messages(self):
        now = time.time()
        # simplified fade; full HTML per-line coloring would require model tracking
        # this is placeholder for message age fade logic
        pass

# ===================== ENTRY =====================
if __name__=="__main__":
    app=QApplication(sys.argv)
    win=ChatGate()
    win.show()
    sys.exit(app.exec_())
