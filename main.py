import socket
import random
import sys
import json
import os
import time
import ctypes
import ctypes.wintypes as wintypes
from collections import deque
import urllib.request
from packaging import version

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QLabel, QDoubleSpinBox, 
    QSlider, QCheckBox, QFrame
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QPoint
from overlay import ChatOverlay

# ===================== CONFIG =====================
SETTINGS_FILE = "settings.json"
CURRENT_VERSION = "0.1.2-beta"
GITHUB_REPO = "twhippp/ChatGate" 
WM_HOTKEY = 0x0312
HOTKEY_ID = 1

# ===================== IRC THREAD =====================
class IRCThread(QThread):
    message = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg = pyqtSignal(str)

    def __init__(self, channel, threshold, bypass):
        super().__init__()
        chan = channel.lower().strip()
        self.channel = f"#{chan}" if not chan.startswith("#") else chan
        self.threshold = threshold
        self.bypass = bypass
        self.msg_times = deque()
        self.is_running = True

    def run(self):
        sock = socket.socket()
        try:
            self.status_msg.emit("Connecting...")
            sock.connect(("irc.chat.twitch.tv", 6667))
            sock.send(f"NICK justinfan{random.randint(10000, 99999)}\r\n".encode())
            sock.send(b"CAP REQ :twitch.tv/tags\r\n")
            sock.send(f"JOIN {self.channel}\r\n".encode())
            self.status_msg.emit("Connected")
            
            while self.is_running:
                data = sock.recv(4096).decode("utf-8", errors="ignore")
                if not data: break
                for line in data.split('\r\n'):
                    if not line or line.startswith("PING"):
                        if line.startswith("PING"): sock.send("PONG :tmi.twitch.tv\r\n".encode())
                        continue
                    if "PRIVMSG" in line:
                        tags = {}
                        if line.startswith("@"):
                            tag_str, rest = line[1:].split(" ", 1)
                            tags = dict(t.split("=") for t in tag_str.split(";") if "=" in t)
                        
                        user = tags.get("display-name", "User")
                        content = line.split('PRIVMSG', 1)[1].split(':', 1)[1]
                        
                        now = time.time()
                        self.msg_times.append(now)
                        while self.msg_times and now - self.msg_times[0] > 5.0: self.msg_times.popleft()
                        mps = len(self.msg_times) / 5.0
                        is_filtering = mps >= self.threshold
                        
                        is_mod = tags.get("mod") == "1"
                        is_sub = tags.get("subscriber") == "1"
                        is_vip = "vip" in tags.get("badges", "")
                        
                        should_show = not is_filtering
                        if is_mod and self.bypass.get('mod'): should_show = True
                        if is_sub and self.bypass.get('sub'): should_show = True
                        if is_vip and self.bypass.get('vip'): should_show = True
                        
                        self.stats_update.emit(mps, is_filtering)
                        if should_show:
                            color = tags.get("color") or f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                            self.message.emit(f"<span style='color:{color}'><b>{user}</b></span>: {content}")
        except: self.status_msg.emit("Error")
        finally: sock.close()

# ===================== MAIN CONTROLLER =====================
class ChatGateMain(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = self.load_settings()
        self.setWindowTitle("ChatGate Controller")
        self.resize(500, 600)
        
        # Initialize Overlay
        self.overlay = ChatOverlay()
        self.overlay_active = False
        
        # Restore saved position and size
        self.overlay.move(self.settings.get("pos_x", 100), self.settings.get("pos_y", 100))
        self.overlay.resize(self.settings.get("width", 400), self.settings.get("height", 600))
        
        self.init_ui()
        self.apply_theme()
        self.register_hotkey()
        
        # Apply style immediately from settings
        self.sync_overlay()
        
        QTimer.singleShot(500, self.check_for_updates)

    def load_settings(self):
        defaults = {
            "channel": "piratesoftware", "mps": 3.0, "opacity": 80, 
            "mod": True, "vip": True, "sub": False,
            "pos_x": 100, "pos_y": 100, "width": 400, "height": 600
        }
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f: 
                    return {**defaults, **json.load(f)}
            except: pass
        return defaults

    def save_settings(self):
        data = {
            "channel": self.chan_input.text(),
            "mps": self.mps_spin.value(),
            "opacity": self.alpha_slider.value(),
            "mod": self.bp_mod.isChecked(),
            "vip": self.bp_vip.isChecked(),
            "sub": self.bp_sub.isChecked(),
            "pos_x": self.overlay.x(),
            "pos_y": self.overlay.y(),
            "width": self.overlay.width(),
            "height": self.overlay.height()
        }
        with open(SETTINGS_FILE, "w") as f: 
            json.dump(data, f, indent=4)

    def apply_theme(self):
        self.setStyleSheet("""
            QWidget { background-color: #18181b; color: #efeff1; font-family: 'Segoe UI'; }
            QLineEdit { background-color: #26262c; border: 1px solid #464649; color: white; padding: 5px; border-radius: 4px; }
            QPushButton { background-color: #9146FF; color: white; border-radius: 4px; font-weight: bold; padding: 10px; }
            QPushButton:hover { background-color: #772ce8; }
            QDoubleSpinBox { background-color: #26262c; color: white; border: 1px solid #464649; }
            QCheckBox { spacing: 8px; }
            QLabel#status { font-weight: bold; color: #eb0400; }
        """)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self.ver_label = QLabel(f"v{CURRENT_VERSION}")
        self.status_label = QLabel("DISCONNECTED"); self.status_label.setObjectName("status")
        header.addWidget(self.ver_label); header.addStretch(); header.addWidget(self.status_label)
        layout.addLayout(header)

        # Connection
        form = QHBoxLayout()
        self.chan_input = QLineEdit(self.settings["channel"])
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.clicked.connect(self.start_chat)
        form.addWidget(QLabel("Channel:")); form.addWidget(self.chan_input); form.addWidget(self.connect_btn)
        layout.addLayout(form)

        # Move/Unlock Toggle
        self.move_btn = QPushButton("UNLOCK OVERLAY TO MOVE")
        self.move_btn.setCheckable(True)
        self.move_btn.clicked.connect(self.toggle_move_mode)
        layout.addWidget(self.move_btn)

        # Stats
        stats = QHBoxLayout()
        self.mps_label = QLabel("MPS: 0.00")
        self.mps_spin = QDoubleSpinBox()
        self.mps_spin.setRange(0.1, 100.0); self.mps_spin.setValue(self.settings["mps"])
        stats.addWidget(self.mps_label); stats.addStretch(); stats.addWidget(QLabel("Gate Threshold:")); stats.addWidget(self.mps_spin)
        layout.addLayout(stats)

        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet("background-color: #464649;"); layout.addWidget(line)

        # Bypasses
        layout.addWidget(QLabel("<b>BYPASS FILTERS</b>"))
        bp_layout = QHBoxLayout()
        self.bp_mod = QCheckBox("Mods"); self.bp_mod.setChecked(self.settings["mod"])
        self.bp_vip = QCheckBox("VIPs"); self.bp_vip.setChecked(self.settings["vip"])
        self.bp_sub = QCheckBox("Subs"); self.bp_sub.setChecked(self.settings["sub"])
        bp_layout.addWidget(self.bp_mod); bp_layout.addWidget(self.bp_vip); bp_layout.addWidget(self.bp_sub)
        layout.addLayout(bp_layout)

        # Visuals Sliders
        layout.addWidget(QLabel("<b>OVERLAY OPACITY</b>"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(0, 100); self.alpha_slider.setValue(self.settings["opacity"])
        self.alpha_slider.valueChanged.connect(self.sync_overlay)
        layout.addWidget(self.alpha_slider)

        layout.addWidget(QLabel("<b>OVERLAY SCALE (WIDTH)</b>"))
        self.width_slider = QSlider(Qt.Horizontal)
        self.width_slider.setRange(200, 1200)
        self.width_slider.setValue(self.settings.get("width", 400))
        self.width_slider.valueChanged.connect(self.sync_overlay)
        layout.addWidget(self.width_slider)

        self.info_label = QLabel("Hotkey: Ctrl+Shift+O to toggle overlay visibility")
        self.info_label.setStyleSheet("color: #adadb8; font-size: 11px;")
        layout.addWidget(self.info_label)

    def sync_overlay(self):
        # 1. Update Style (Opacity)
        opacity_decimal = self.alpha_slider.value() / 100.0
        self.overlay.update_style(22, opacity_decimal)
        
        # 2. Update Width
        self.overlay.resize(self.width_slider.value(), self.overlay.height())
        
        # 3. Save to file
        self.save_settings()

    def toggle_move_mode(self):
        is_unlocked = self.move_btn.isChecked()
        self.overlay.set_click_through(not is_unlocked)
        self.move_btn.setText("LOCK OVERLAY POSITION" if is_unlocked else "UNLOCK OVERLAY TO MOVE")
        self.move_btn.setStyleSheet("background-color: #9146FF;" if is_unlocked else "background-color: #26262c;")
        if is_unlocked: self.overlay.show()
        else: self.save_settings()

    def check_for_updates(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            with urllib.request.urlopen(url, timeout=2) as r:
                data = json.loads(r.read().decode())
                if version.parse(data["tag_name"].replace("v","")) > version.parse(CURRENT_VERSION):
                    self.ver_label.setText("UPDATE AVAILABLE"); self.ver_label.setStyleSheet("color: #00ff7f;")
        except: pass

    def register_hotkey(self):
        ctypes.windll.user32.RegisterHotKey(int(self.winId()), HOTKEY_ID, 0x0002 | 0x0004, ord("O"))

    def nativeEvent(self, eventType, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self.overlay_active = not self.overlay_active
            if self.overlay_active: 
                self.overlay.show()
                self.overlay.set_click_through(True)
            else: 
                self.overlay.hide()
            return True, 0
        return super().nativeEvent(eventType, message)

    def start_chat(self):
        self.save_settings()
        bypass = {'mod': self.bp_mod.isChecked(), 'vip': self.bp_vip.isChecked(), 'sub': self.bp_sub.isChecked()}
        self.irc = IRCThread(self.chan_input.text(), self.mps_spin.value(), bypass)
        self.irc.message.connect(self.overlay.add_message)
        self.irc.stats_update.connect(lambda m, f: (self.mps_label.setText(f"MPS: {m:.2f}"), 
                                                  self.mps_label.setStyleSheet("color: #ff8200;" if f else "")))
        self.irc.status_msg.connect(lambda t: (self.status_label.setText(t.upper()), 
                                              self.status_label.setStyleSheet("color: #00ff7f;" if "CONNECTED" in t.upper() else "")))
        self.irc.start()
        if not self.overlay_active: 
            self.overlay_active = True
            self.overlay.show()
            self.overlay.set_click_through(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ChatGateMain(); w.show()
    sys.exit(app.exec_())