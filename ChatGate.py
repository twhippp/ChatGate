import socket, random, re, sys, json, os, time, threading, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque, defaultdict
from difflib import SequenceMatcher
import requests

from PyQt5.QtWidgets import (
    QApplication, QWidget, QTextBrowser, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QCheckBox
)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QTextCursor

# ===================== CONSTANTS =====================
SERVER = "irc.chat.twitch.tv"
PORT = 6667
SETTINGS_FILE = "settings.json"
CHAT_RATE_WINDOW = 5.0
REDIRECT_URI = "http://localhost:8080"
CLIENT_ID = "0lzbqx6jctjx7zxt39ubfo4eys7yor"  # <-- replace with your Twitch Client ID

OAUTH_SCOPES = [
    "channel:read:redemptions",
    "channel:read:subscriptions",
    "bits:read"
]

LOW_VALUE = {"gg","lol","lmao","pog","kekw","ez","nice","wow","ok","bruh"}
GREETINGS = {"hi","hello","hey","sup","yo","hiya","good morning","good evening"}
REPEAT_CHARS = re.compile(r"(.)\1{4,}")
REPEATED_WORD = re.compile(r"\b(\w{1,4})\b(?:\s+\1\b){2,}", re.I)
EMOTE_PATTERN = re.compile(r":[a-zA-Z0-9_]+:")

ROLE_COLORS = {
    "BROADCASTER":"red",
    "MOD":"green",
    "VIP":"pink",
    "SUB":"gold"
}

# ===================== SETTINGS =====================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE,"r") as f:
            data=json.load(f)
    else:
        data={}
    defaults={
        "channel":"",
        "font_size":14,
        "mps_threshold":3.0,
        "bypass_broadcaster":True,
        "bypass_mod":True,
        "bypass_vip":False,
        "bypass_sub":False,
        "access_token":"",
        "refresh_token":"",
        "theme":"dark"  # dark/light
    }
    for k,v in defaults.items(): data.setdefault(k,v)
    return data

def save_settings(settings):
    with open(SETTINGS_FILE,"w") as f:
        json.dump(settings,f,indent=2)

settings = load_settings()

# ===================== FILTER FUNCTIONS =====================
def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def is_greeting(msg):
    return msg.lower().strip() in GREETINGS

def tokenize(text):
    return re.findall(r"\w+", text.lower())

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

def is_reply(tags):
    return "reply-parent-msg-id" in tags

def mention_of_me(text):
    chan = settings.get("channel","").lower()
    return re.search(rf"(?<!\w){re.escape(chan)}(?!\w)", text.lower())

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message = pyqtSignal(str)
    filter_state = pyqtSignal(bool,float)
    connection_status = pyqtSignal(str,str)

    def __init__(self, channel, mps_threshold, role_bypass):
        super().__init__()
        self.channel = channel.lower()
        self.nick = f"justinfan{random.randint(10000,99999)}"
        self.mps_threshold = mps_threshold
        self.role_bypass = role_bypass
        self.msg_times = deque()
        self.user_last_msg = {}
        self.recent_msgs = deque(maxlen=50)
        self.running = True

    def update_threshold(self, val):
        self.mps_threshold = val

    def update_bypass(self, b):
        self.role_bypass = b

    def run(self):
        try:
            sock = socket.socket()
            sock.connect((SERVER, PORT))
            sock.sendall(f"NICK {self.nick}\r\n".encode())
            sock.sendall(b"CAP REQ :twitch.tv/tags\r\n")
            sock.sendall(f"JOIN #{self.channel}\r\n".encode())
            self.connection_status.emit("CONNECTED","green")
        except:
            self.connection_status.emit("DISCONNECTED","red")
            return

        buf=""
        while self.running:
            try:
                buf += sock.recv(4096).decode(errors="ignore")
            except:
                self.connection_status.emit("DISCONNECTED","red")
                break

            while "\r\n" in buf:
                line, buf = buf.split("\r\n",1)
                if line.startswith("PING"):
                    sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                    continue
                if "PRIVMSG" not in line: continue

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

                # roles
                roles=[]
                role_keys = set()
                badges = tags.get("badges","")
                if "broadcaster" in badges:
                    roles.append(("BROADCASTER",ROLE_COLORS["BROADCASTER"]))
                    role_keys.add("broadcaster")
                if tags.get("mod")=="1":
                    roles.append(("MOD",ROLE_COLORS["MOD"]))
                    role_keys.add("mod")
                if "vip" in badges:
                    roles.append(("VIP",ROLE_COLORS["VIP"]))
                    role_keys.add("vip")
                if tags.get("subscriber")=="1":
                    roles.append(("SUB",ROLE_COLORS["SUB"]))
                    role_keys.add("sub")

                bypass = any(self.role_bypass.get(r,False) for r in role_keys)

                # cooldown & similarity
                last_msg = self.user_last_msg.get(user, ("",0))
                if now - last_msg[1] < 1.0 and similarity(msg_text,last_msg[0]) > 0.8:
                    continue
                self.user_last_msg[user] = (msg_text, now)

                if not bypass:
                    blocked = False
                    for recent in self.recent_msgs:
                        if similarity(msg_text,recent) >= 0.75:
                            blocked = True
                            break
                    if blocked: continue
                self.recent_msgs.append(msg_text)

                # adaptive min length
                min_words = 3 + int(mps/2)
                if filter_active and not bypass:
                    if not is_greeting(msg_text) and not is_substantive(msg_text, min_words):
                        continue

                # render HTML
                role_html = " ".join(f"<span style='color:{c}'>[{n}]</span>" for n,c in roles)
                display_text = msg_text
                if mention_of_me(msg_text):
                    display_text = re.sub(
                        f"({re.escape(settings.get('channel',''))})",
                        r"<b style='background-color:#ffff00;color:#000;'>\1</b>",
                        display_text,
                        flags=re.I
                    )
                name_color = f"hsl({abs(hash(user))%360},100%,70%)"
                html = f"{role_html} <span style='color:{name_color}'>{user}</span>: {display_text}"
                self.message.emit(html)

# ===================== GUI =====================
class ChatGate(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatGate")
        self.resize(900,840)
        self.settings = settings

        # Controls
        self.channel_input = QLineEdit(self.settings.get("channel",""))
        self.connect_btn = QPushButton("Connect")
        self.oauth_btn = QPushButton("Authenticate")
        self.theme_btn = QPushButton("Toggle Theme")
        self.font_size = QSpinBox(); self.font_size.setRange(10,30); self.font_size.setValue(self.settings.get("font_size",14))
        self.mps_spin = QDoubleSpinBox(); self.mps_spin.setRange(0.2,20); self.mps_spin.setSingleStep(0.2); self.mps_spin.setValue(self.settings.get("mps_threshold",3.0))
        self.bypass_checks = {k:QCheckBox(f"{k.capitalize()} bypass") for k in ["broadcaster","mod","vip","sub"]}
        for k,cb in self.bypass_checks.items(): cb.setChecked(self.settings.get(f"bypass_{k}",True))
        self.status_label = QLabel("DISCONNECTED")
        self.filter_label = QLabel("FILTER OFF")
        self.chat = QTextBrowser()
        self.activity = QTextBrowser()
        self.apply_theme()  # set initial theme

        top = QHBoxLayout()
        top.addWidget(QLabel("Channel")); top.addWidget(self.channel_input); top.addWidget(self.connect_btn); top.addWidget(self.oauth_btn); top.addWidget(self.theme_btn)
        top.addWidget(QLabel("Font")); top.addWidget(self.font_size); top.addWidget(QLabel("MPS")); top.addWidget(self.mps_spin)
        top.addWidget(self.status_label); top.addWidget(self.filter_label)

        bypass_row = QHBoxLayout()
        for cb in self.bypass_checks.values(): bypass_row.addWidget(cb)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(bypass_row)
        layout.addWidget(QLabel("Activity Feed")); layout.addWidget(self.activity)
        layout.addWidget(QLabel("Chat")); layout.addWidget(self.chat)

        self.thread = None

        self.connect_btn.clicked.connect(self.start_chat)
        self.oauth_btn.clicked.connect(self.authenticate)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.font_size.valueChanged.connect(self.update_font)
        self.mps_spin.valueChanged.connect(self.update_threshold)
        for cb in self.bypass_checks.values(): cb.stateChanged.connect(self.update_bypass)

    def apply_chat_font(self):
        self.chat.setStyleSheet(f"font-size:{self.font_size.value()}px;")

    def apply_activity_font(self):
        self.activity.setStyleSheet(f"font-size:{self.font_size.value()}px;")

    def update_font(self, val):
        self.apply_chat_font()
        self.apply_activity_font()
        self.settings["font_size"] = val
        save_settings(self.settings)

    def update_threshold(self, val):
        self.settings["mps_threshold"] = val
        save_settings(self.settings)
        if self.thread: self.thread.update_threshold(val)

    def update_bypass(self):
        bp = {k:cb.isChecked() for k,cb in self.bypass_checks.items()}
        for k,v in bp.items(): self.settings[f"bypass_{k}"]=v
        save_settings(self.settings)
        if self.thread: self.thread.update_bypass(bp)

    def start_chat(self):
        chan = self.channel_input.text().strip().lower()
        if not chan: return
        self.settings["channel"] = chan; save_settings(self.settings)
        if self.thread: self.thread.running=False; self.thread.terminate()
        self.chat.clear(); self.activity.clear()
        self.thread = IRCThread(chan, self.mps_spin.value(), self.current_bypass())
        self.thread.message.connect(self.add_chat)
        self.thread.filter_state.connect(self.update_filter_label)
        self.thread.connection_status.connect(self.update_status)
        self.thread.start()

    def current_bypass(self): return {k:cb.isChecked() for k,cb in self.bypass_checks.items()}

    def add_chat(self, html):
        self.chat.moveCursor(QTextCursor.End)
        self.chat.insertHtml(html+"<br>")
        self.chat.moveCursor(QTextCursor.End)

    def add_activity(self, text, color):
        fmt = f"<span style='color:{color};font-weight:bold'>{text}</span>"
        self.activity.moveCursor(QTextCursor.End)
        self.activity.insertHtml(fmt+"<br>")
        self.activity.moveCursor(QTextCursor.End)

    def update_filter_label(self, active, mps):
        self.filter_label.setText(f"{'FILTER ACTIVE' if active else 'FILTER OFF'} ({mps:.1f} MPS)")

    def update_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color}")

    def apply_theme(self):
        theme = self.settings.get("theme","dark")
        if theme=="dark":
            bg="#18181b"; fg="white"
        else:
            bg="white"; fg="black"
        self.chat.setStyleSheet(f"background:{bg};color:{fg};font-size:{self.font_size.value()}px;")
        self.activity.setStyleSheet(f"background:{bg};color:{fg};font-size:{self.font_size.value()}px;")
        self.setStyleSheet(f"background:{bg};color:{fg}")

    def toggle_theme(self):
        current = self.settings.get("theme","dark")
        self.settings["theme"] = "light" if current=="dark" else "dark"
        save_settings(self.settings)
        self.apply_theme()

    def authenticate(self):
        import socketserver
        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                qs = parse_qs(urlparse(self.path).query)
                code = qs.get("code",[None])[0]
                if code:
                    self.send_response(200)
                    self.send_header("Content-type","text/html")
                    self.end_headers()
                    self.wfile.write(b"<h2>You can close this window. Authentication succeeded.</h2>")

                    token_url = "https://id.twitch.tv/oauth2/token"
                    resp = requests.post(token_url,data={
                        "client_id": CLIENT_ID,
                        "code": code,
                        "grant_type":"authorization_code",
                        "redirect_uri": REDIRECT_URI
                    })
                    data = resp.json()
                    settings["access_token"] = data.get("access_token")
                    settings["refresh_token"] = data.get("refresh_token")
                    save_settings(settings)
                    self.server.success=True
                else:
                    self.send_response(400)
                    self.end_headers()

        def run_server():
            with socketserver.TCPServer(("localhost",8080),OAuthHandler) as httpd:
                httpd.success=False
                httpd.handle_request()
                if getattr(httpd,"success",False):
                    self.update_status("AUTHENTICATED","green")

        auth_url = f"https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={' '.join(OAUTH_SCOPES)}"
        threading.Thread(target=run_server,daemon=True).start()
        webbrowser.open(auth_url)

# ===================== ENTRY =====================
if __name__=="__main__":
    app = QApplication(sys.argv)
    win = ChatGate()
    win.show()
    sys.exit(app.exec_())
