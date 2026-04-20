"""
Kick Support Module for ChatGate
This module contains all Kick-related functionality.
Kick is a livestreaming platform that uses WebSocket-based chat.

Author: ChatGate Contributors
Date: April 2026
"""

import time
import threading
import json
import ssl
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

# Kick imports - may need to be installed
try:
    import websocket
    KICK_AVAILABLE = True
    KICK_ERROR = None
except ImportError as e:
    KICK_AVAILABLE = False
    KICK_ERROR = str(e)


class KickThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    CHAT_RATE_WINDOW = 5.0

    def __init__(self, channel, threshold, bypass_member, filters):
        super().__init__()
        self.channel       = channel.strip().lower()
        self.threshold     = threshold
        self.bypass_member = bypass_member
        self.filters       = filters
        self.msg_times     = deque()
        self.is_running    = True
        self.ws            = None

    def stop(self):
        self.is_running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

    def _should_show(self, user, msg, is_verified, mps):
        f = self.filters
        if user.lower() in [u.lower() for u in f.get("user_blacklist", [])]: 
            return False
        if user.lower() in [u.lower() for u in f.get("user_whitelist", [])]: 
            return True
        msg_lower = msg.lower()
        for word in f.get("always_block_words", []):
            if word.lower() in msg_lower: 
                return False
        is_filtering = mps >= self.threshold
        if is_filtering:
            for word in f.get("volume_block_words", []):
                if word.lower() in msg_lower: 
                    return False
        if is_verified:
            if self.bypass_member == "Always": 
                return True
            if self.bypass_member == "Never":  
                return False
        if is_filtering: 
            return False
        return True

    def run(self):
        self.status_msg.emit("Connecting...")

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
            # Construct Kick WebSocket URL
            ws_url = f"wss://ws-us2.kick.com/app?v=3&token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOlwvXC9raWNrLnRvIiwicHVzaGVyX2RhdGEiOnsiYnJvYWRjYXN0X2lkIjoie2NoYW5uZWx9IiwiYXV0aCI6IiJ9LCJpYXQiOjE2MjMwMzMzNzAsImV4cCI6MTYyMzEyMDAwMH0"
            self.status_msg.emit(f"Connecting to {self.channel}...")

            def on_message(ws, message):
                if not self.is_running:
                    return
                try:
                    data = json.loads(message)
                    # Handle chat messages
                    if data.get('event') == 'chat_message':
                        msg_data = data.get('data', {})
                        user = msg_data.get('username', 'Unknown')
                        msg = msg_data.get('message', '')
                        is_verified = msg_data.get('is_verified_bot', False)

                        if msg:
                            self.msg_times.append(time.time())
                            if self._should_show(user, msg, is_verified, len(self.msg_times) / self.CHAT_RATE_WINDOW):
                                color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                                self.message.emit(
                                    f"<span style='color:#000000;font-weight:bold'>[KICK]</span> "
                                    f"<span style='color:{color}'><b>{user}</b></span>: {msg}")
                except Exception as e:
                    pass

            def on_error(ws, error):
                if self.is_running:
                    self.status_msg.emit(f"Error: {error}")

            def on_close(ws, close_status_code, close_msg):
                if self.is_running:
                    self.status_msg.emit("Disconnected")
                    self.disconnected.emit()

            def on_open(ws):
                self.status_msg.emit(f"Connected to {self.channel}")
                # Subscribe to channel
                ws.send(json.dumps({
                    "event": "pusher:subscribe",
                    "data": {"channel": f"chatrooms.{self.channel}.v2"}
                }))

            # Note: This is a simplified implementation. Real Kick support would need:
            # - Proper authentication
            # - Channel ID resolution
            # - Full event handling for kicks, subscriptions, etc.
            # For now, this is a placeholder that follows the structure
            
            self.status_msg.emit("Kick support is in development")

        except Exception as e:
            self.status_msg.emit(f"Error: {e}")
        finally:
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()
