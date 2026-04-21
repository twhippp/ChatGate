"""
Kick Support Module for ChatGate
This module contains all Kick-related functionality.
Kick uses the Pusher protocol for real-time chat updates.

Author: ChatGate Contributors
Date: April 2026
"""

import time
import threading
import json
import re
import ssl
import requests
import urllib.parse
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

try:
    import websocket
    import tls_client
    KICK_AVAILABLE = True
    KICK_ERROR = None
except ImportError as e:
    KICK_AVAILABLE = False
    KICK_ERROR = str(e)

TLS_SESSION = None

def _get_tls_session():
    global TLS_SESSION
    if TLS_SESSION is None:
        TLS_SESSION = tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
    return TLS_SESSION


GLOBAL_EMOTES = {}

def _load_kick_emotes():
    global GLOBAL_EMOTES
    if GLOBAL_EMOTES:
        return GLOBAL_EMOTES

    kick_emote_html = '''<div class="grid grid-cols-8 justify-between gap-2"><button class="betterhover:hover:bg-white/10 disabled:betterhover:hover:bg-white/10 relative aspect-square size-10 rounded-sm p-1 disabled:opacity-40 lg:size-9" data-state="closed"><img class="aspect-square size-8 lg:size-7" alt="emojiAngel" loading="lazy" src="https://files.kick.com/emotes/1730752/fullsize"></button><button class="betterhover:hover:bg-white/10 disabled:betterhover:hover:bg-white/10 relative aspect-square size-10 rounded-sm p-1 disabled:opacity-40 lg:size-9" data-state="closed"><img class="aspect-square size-8 lg:size-7" alt="emojiAngry" loading="lazy" src="https://files.kick.com/emotes/1730753/fullsize"></button></div>'''

    try:
        import re as re_module
        img_pattern = r'<img[^>]+>'
        for img_tag in re_module.finditer(img_pattern, kick_emote_html):
            tag = img_tag.group(0)
            url_match = re_module.search(r'src="(https://files\.kick\.com/emotes/\d+/fullsize)"', tag)
            name_match = re_module.search(r'alt="([^"]+)"', tag)
            if url_match and name_match:
                url = url_match.group(1)
                emote_id = url.split('/')[-2]
                name = name_match.group(1)
                GLOBAL_EMOTES[emote_id] = {'name': name, 'id': emote_id}
        print(f"[KICK] Loaded {len(GLOBAL_EMOTES)} global emotes")
        return GLOBAL_EMOTES
    except Exception as e:
        print(f"[KICK] Emote parse error: {e}")
        return {}

def _download_emote_cached(emote_id):
    import os
    cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'emote_cache')
    os.makedirs(cache_dir, exist_ok=True)
    local_path = os.path.join(cache_dir, f'{emote_id}.gif')
    if os.path.exists(local_path):
        return local_path
    try:
        session = _get_tls_session()
        r = session.get(f'https://files.kick.com/emotes/{emote_id}/fullsize')
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(r.content)
            return local_path
    except:
        pass
    return None

class KickThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    CHAT_RATE_WINDOW = 5.0
    PUSHER_KEY = "32cbd69e4b950bf97679"  # Public Pusher key for Kick
    PUSHER_HOST = "ws-us2.pusher.com"    # Pusher cluster for Kick

    def __init__(self, channel, threshold, bypass_member, filters):
        super().__init__()
        self.channel       = channel.strip().lower()
        self.threshold     = threshold
        self.bypass_member = bypass_member
        self.filters       = filters
        self.msg_times     = deque()
        self.is_running    = True
        self.ws            = None
        self.chatroom_id   = None
        self.emotes       = {}

    def stop(self):
        self.is_running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass

    def _get_emotes(self):
        _load_kick_emotes()
        self.emotes = dict(GLOBAL_EMOTES)
        print(f"[KICK] Using {len(self.emotes)} emotes")
        self.status_msg.emit(f"Loaded {len(self.emotes)} emotes")

    def _get_chatroom_id(self, channel):
        try:
            self.status_msg.emit(f"Looking up chatroom for {channel}...")

            url = f"https://kick.com/api/v2/channels/{channel}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Referer': f'https://kick.com/{channel}',
            }

            session = _get_tls_session()
            response = session.get(url, headers=headers)
            self.status_msg.emit(f"API response: {response.status_code}")

            if response.status_code != 200:
                self.status_msg.emit(f"Error: {response.status_code} - {response.text[:100]}")
                return None

            data = response.json()
            chatroom = data.get('chatroom', {})
            chatroom_id = chatroom.get('id')

            if chatroom_id:
                self.status_msg.emit(f"Found chatroom ID: {chatroom_id}")
                return chatroom_id
            else:
                self.status_msg.emit(f"Could not find chatroom for {channel}")
                return None

        except Exception as e:
            self.status_msg.emit(f"Error: {e}")
            return None

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

        # Start the message rate counter
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
            # Step 1: Get the chatroom ID
            self.chatroom_id = self._get_chatroom_id(self.channel)
            if not self.chatroom_id:
                self.status_msg.emit("KICK UNAVAILABLE - Could not find channel")
                return

            # Step 1.5: Get emotes
            self.status_msg.emit("Loading emotes...")
            self._get_emotes()

            # Step 2: Connect to Pusher WebSocket
            ws_url = (f"wss://{self.PUSHER_HOST}:"
                     f"443/app/{self.PUSHER_KEY}?"
                     f"protocol=7&client=js&version=7.0.0&flash=false")
            
            self.status_msg.emit(f"Connecting to {self.channel}...")

            def on_message(ws, message):
                if not self.is_running:
                    return
                try:
                    data = json.loads(message)
                    event = data.get('event')

                    # Handle pusher:connection_established
                    if event == 'pusher:connection_established':
                        self.status_msg.emit("Connected to Pusher")

                    # Handle pusher:subscription_succeeded
                    if event == 'pusher:subscription_succeeded' or event == 'pusher_internal:subscription_succeeded':
                        self.status_msg.emit(f"Connected to {self.channel}")

                    # Handle chat messages from Pusher
                    elif event == 'App\\Events\\ChatMessageSentEvent' or event == 'App\\Events\\ChatMessageEvent':
                        channel = data.get('channel', '')
                        if f'chatrooms.{self.chatroom_id}' in channel or f'chatroom_{self.chatroom_id}' in channel:
                            msg_data = data.get('data', {})
                            if isinstance(msg_data, str):
                                msg_data = json.loads(msg_data)

                            sender = msg_data.get('sender', {})
                            user = sender.get('username', 'Unknown')
                            msg = msg_data.get('content', '')
                            is_verified = sender.get('is_verified', False)

                            msg = re.sub(r'\[emote:\d+:([^\]]+)\]', r':\1:', msg)

                            if msg:
                                self.msg_times.append(time.time())
                                mps = len(self.msg_times) / self.CHAT_RATE_WINDOW
                                if self._should_show(user, msg, is_verified, mps):
                                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                                    self.message.emit(
                                        f"<span style='color:#00D084;font-weight:bold'>[KICK]</span> "
                                        f"<span style='color:{color}'><b>{user}</b></span>: {msg}")
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    self.status_msg.emit(f"Msg error: {e}")

            def on_open(ws):
                for ch in [f"chatrooms.{self.chatroom_id}.v2", f"chatroom_{self.chatroom_id}"]:
                    subscribe_msg = {
                        "event": "pusher:subscribe",
                        "data": {
                            "channel": ch
                        }
                    }
                    try:
                        ws.send(json.dumps(subscribe_msg))
                    except Exception as e:
                        self.status_msg.emit(f"Failed to subscribe: {e}")

            def on_error(ws, error):
                if self.is_running:
                    self.status_msg.emit(f"WebSocket Error: {error}")

            def on_close(ws, close_status_code, close_msg):
                if self.is_running:
                    self.status_msg.emit("Disconnected")
                    self.disconnected.emit()

            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )

            ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE},
                ping_interval=30,
                ping_timeout=10
            )
            return

        except Exception as e:
            self.status_msg.emit(f"KICK UNAVAILABLE - {str(e)}")
            return