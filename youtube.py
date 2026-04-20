"""
YouTube Support Module for ChatGate
This module contains all YouTube-related functionality.

Author: ChatGate Contributors
Date: April 2026
"""

import re
import time
import threading
import urllib.request
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

# Video ID resolution utilities
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
    
    # Try live pages first (most specific)
    for url in [
        f"https://www.youtube.com/@{s}/live",
        f"https://www.youtube.com/c/{s}/live",
        f"https://www.youtube.com/user/{s}/live",
    ]:
        try:
            print(f"YT resolving: {url}")
            html = _fetch(url)
            vid = _extract_video_id_from_html(html)
            if vid:
                print(f"YT resolved {url} -> {vid}")
                return vid
        except Exception as e:
            print(f"YT failed to resolve {url}: {e}")
            continue
    
    # Fallback to channel pages if no live found
    for url in [
        f"https://www.youtube.com/@{s}",
        f"https://www.youtube.com/c/{s}",
        f"https://www.youtube.com/user/{s}",
    ]:
        try:
            print(f"YT resolving (fallback): {url}")
            html = _fetch(url)
            vid = _extract_video_id_from_html(html)
            if vid:
                print(f"YT resolved {url} -> {vid}")
                return vid
        except Exception as e:
            print(f"YT failed to resolve {url}: {e}")
            continue
    
    return None


class YouTubeThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    CHAT_RATE_WINDOW = 5.0

    def __init__(self, handle, threshold, bypass_member, filters, platform_badge_html):
        super().__init__()
        self.handle         = handle
        self.threshold      = threshold
        self.bypass_member  = bypass_member
        self.filters        = filters
        self.msg_times      = deque()
        self.is_running     = True
        self._platform_badge_html = platform_badge_html

    def stop(self):
        self.is_running = False

    def _should_show(self, user, msg, is_member, mps):
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
        if is_member:
            if self.bypass_member == "Always": 
                return True
            if self.bypass_member == "Never":  
                return False
        if is_filtering: 
            return False
        return True

    def run(self):
        self.status_msg.emit("Resolving channel...")
        video_id = resolve_video_id(self.handle)
        if not video_id:
            self.status_msg.emit("Error: Could not find live stream")
            if self.is_running: 
                self.disconnected.emit()
            return

        self.status_msg.emit(f"Connecting... (ID: {video_id})")

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
            import pytchat
            
            chat = pytchat.create(video_id=video_id, interruptable=False)
            if not chat.is_alive():
                self.status_msg.emit("Error: Chat not active")
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
                    mps = len(self.msg_times) / self.CHAT_RATE_WINDOW
                    is_filtering = mps >= self.threshold
                    self.stats_update.emit(mps, is_filtering)

                    is_member = bool(item.author.badgeUrl)
                    user = item.author.name
                    msg = item.message

                    if self._should_show(user, msg, is_member, mps):
                        badge = self._platform_badge_html("youtube")
                        color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        self.message.emit(
                            f"{badge}<span style='color:{color}'><b>{user}</b></span>: {msg}")

        except Exception as e:
            print(f"YT Error: {e}")
            pass
        finally:
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()
