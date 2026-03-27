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
    QSlider, QCheckBox, QSpinBox, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt5.QtGui import QIcon
from overlay import ChatOverlay

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
"""

# ===================== ICON =====================
def get_icon_path():
    """Resolves icon path whether running as a script or frozen exe."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ChatGate.ico")

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

                    # Broadcaster tag check from badges (Gemini's improvement)
                    is_mod = tags.get("mod") == "1" or "broadcaster" in tags.get("badges", "")
                    is_sub = tags.get("subscriber") == "1"
                    is_vip = "vip" in tags.get("badges", "")

                    should_show = not is_filtering
                    if is_mod and self.bypass.get('mod'): should_show = True
                    if is_sub and self.bypass.get('sub'): should_show = True
                    if is_vip and self.bypass.get('vip'): should_show = True

                    if should_show:
                        color = tags.get("color") or f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        self.message.emit(
                            f"<span style='color:{color}'><b>{user}</b></span>: {content}")

        except Exception:
            pass
        finally:
            sock.close()
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()

# ===================== MAIN CONTROLLER =====================
class ChatGateMain(QWidget):
    def __init__(self):
        super().__init__()
        self.settings       = self.load_settings()
        self.dark_mode      = self.settings.get("dark_mode", True)
        self.setWindowTitle("ChatGate Controller")
        self.resize(450, 600)

        self.overlay            = ChatOverlay()
        self.overlay_active     = False
        self.irc                = None
        self._reconnect_attempt = 0
        self._reconnect_timer   = QTimer()
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)
        self._last_channel      = ""

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
            "channel": "piratesoftware", "mps": 3.0, "opacity": 100,
            "mod": True, "vip": True, "sub": True,
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
            "channel":   self.chan_input.text(),
            "mps":       self.mps_spin.value(),
            "opacity":   self.alpha_slider.value(),
            "mod":       self.bp_mod.isChecked(),
            "vip":       self.bp_vip.isChecked(),
            "sub":       self.bp_sub.isChecked(),
            "pos_x":     self.overlay.x(),
            "pos_y":     self.overlay.y(),
            "width":     self.overlay.width(),
            "height":    self.overlay.height(),
            "dark_mode": self.dark_mode,
            "font_size": self.font_spin.value(),
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
            WM_SETICON       = 0x0080
            ICON_SMALL       = 0
            ICON_BIG         = 1
            IMAGE_ICON       = 1
            LR_LOADFROMFILE  = 0x0010
            LR_DEFAULTSIZE   = 0x0040
            hicon = ctypes.windll.user32.LoadImageW(
                None, ico_path, IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
            hwnd = int(self.winId())
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,   hicon)
        except Exception as e:
            print(f"DEBUG: Win32 icon set failed: {e}")

    # ===================== UI =====================
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        self.ver_label    = QLabel(f"v{CURRENT_VERSION}")
        self.status_label = QLabel("OFFLINE")
        self.mps_label    = QLabel("MPS: 0.0")
        header.addWidget(self.ver_label)
        header.addStretch()
        header.addWidget(self.mps_label)
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Channel + connect
        layout.addWidget(QLabel("Twitch Channel:"))
        form = QHBoxLayout()
        self.chan_input  = QLineEdit(self.settings["channel"])
        self.chan_input.textChanged.connect(self.save_settings)
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.clicked.connect(self.start_chat)
        form.addWidget(self.chan_input)
        form.addWidget(self.connect_btn)
        layout.addLayout(form)

        # Unlock overlay
        self.move_btn = QPushButton("UNLOCK OVERLAY TO MOVE")
        self.move_btn.setCheckable(True)
        self.move_btn.toggled.connect(self.toggle_move_mode)
        layout.addWidget(self.move_btn)

        # Opacity
        layout.addWidget(QLabel("<b>OPACITY</b>"))
        self.alpha_slider = QSlider(Qt.Horizontal)
        self.alpha_slider.setRange(10, 100)
        self.alpha_slider.setValue(self.settings["opacity"])
        self.alpha_slider.valueChanged.connect(self.sync_overlay)
        layout.addWidget(self.alpha_slider)

        # Font size + MPS threshold on one row
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

        # Bypass checkboxes
        layout.addWidget(QLabel("<b>BYPASS FILTERS FOR:</b>"))
        self.bp_mod = QCheckBox("Moderators / Broadcaster")
        self.bp_mod.setChecked(self.settings["mod"])
        self.bp_sub = QCheckBox("Subscribers")
        self.bp_sub.setChecked(self.settings["sub"])
        self.bp_vip = QCheckBox("VIPs")
        self.bp_vip.setChecked(self.settings["vip"])
        for cb in [self.bp_mod, self.bp_sub, self.bp_vip]:
            cb.stateChanged.connect(self.save_settings)
            layout.addWidget(cb)

        # Theme toggle
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

    # ===================== IRC / RECONNECT =====================
    def start_chat(self):
        self.save_settings()
        self._reconnect_attempt = 0
        self._last_channel = self.chan_input.text()
        self._reconnect_timer.stop()
        self._launch_irc()
        if not self.overlay_active:
            self.overlay_active = True
            self.overlay.show()
            self.overlay.set_click_through(True)

    def _launch_irc(self):
        if self.irc is not None:
            self.irc.stop()
            try:
                self.irc.disconnected.disconnect()
            except Exception:
                pass
        bypass = {
            'mod': self.bp_mod.isChecked(),
            'vip': self.bp_vip.isChecked(),
            'sub': self.bp_sub.isChecked()
        }
        self.irc = IRCThread(self._last_channel, self.mps_spin.value(), bypass)
        self.irc.message.connect(self.overlay.add_message)
        self.irc.stats_update.connect(self._update_stats)
        self.irc.status_msg.connect(lambda s: self.status_label.setText(s.upper()))
        self.irc.disconnected.connect(self._on_disconnected)
        self.irc.start()

    def _update_stats(self, mps, filtering):
        self.mps_label.setText(f"MPS: {mps:.1f}")
        self.mps_label.setStyleSheet(
            f"color: {'#ff4444' if filtering else '#9146FF'}; font-weight: bold;")

    def _on_disconnected(self):
        delay = RECONNECT_DELAYS[min(self._reconnect_attempt, len(RECONNECT_DELAYS) - 1)]
        self._reconnect_attempt += 1
        self.status_label.setText(f"RECONNECTING IN {delay}s...")
        self._reconnect_timer.start(delay * 1000)

    def _do_reconnect(self):
        if not self._last_channel:
            return
        self.status_label.setText(f"RECONNECTING... (attempt {self._reconnect_attempt})")
        self._launch_irc()

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