"""
TikTok Support Module for ChatGate
This module contains all TikTok-related functionality.

Author: ChatGate Contributors
Date: April 2026
"""

import time
import threading
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

# TikTok imports - may need to be installed
try:
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import ConnectEvent, CommentEvent, LikeEvent, GiftEvent, ShareEvent, FollowEvent
    TT_AVAILABLE = True
    TT_ERROR = None
except ImportError as e:
    TT_AVAILABLE = False
    TT_ERROR = str(e)


class TikTokThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()

    CHAT_RATE_WINDOW = 5.0

    def __init__(self, handle, threshold, bypass_member, filters):
        super().__init__()
        self.handle        = handle.strip().lstrip("@")
        self.threshold     = threshold
        self.bypass_member = bypass_member
        self.filters       = filters
        self.msg_times     = deque()
        self.is_running    = True

    def stop(self):
        self.is_running = False

    def _should_show(self, user, msg, is_follower, mps):
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
        if is_follower:
            if self.bypass_member == "Always": return True
            if self.bypass_member == "Never":  return False
        if is_filtering: return False
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
            client = TikTokLiveClient(unique_id=f"@{self.handle}")
            self.status_msg.emit(f"Connecting to @{self.handle}...")

            async def on_comment(event):
                if not self.is_running:
                    return
                self.msg_times.append(time.time())

                user = event.user.unique_id
                msg  = event.comment
                is_follower = event.user.is_follower

                if not msg: return
                if self._should_show(user, msg, is_follower, 0):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"<span style='color:#000000;font-weight:bold'>[TT]</span> "
                        f"<span style='color:{color}'><b>{user}</b></span>: {msg}")

            async def on_like(event):
                if not self.is_running: return

                user = event.user.unique_id
                count = event.like_count
                if count > 1:
                    msg = f"liked {count} times"
                else:
                    msg = "liked"
                if self._should_show(user, msg, False, 0):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"<span style='color:#000000;font-weight:bold'>[TT]</span> "
                        f"<span style='color:{color}'><b>{user}</b></span> {msg}")

            async def on_gift(event):
                if not self.is_running: return
                self.msg_times.append(time.time())

                user = event.user.unique_id
                gift_name = event.gift.name if event.gift else "gift"
                if self._should_show(user, gift_name, False, 0):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"<span style='color:#000000;font-weight:bold'>[TT]</span> "
                        f"<span style='color:{color}'><b>{user}</b></span> sent {gift_name}")

            async def on_follow(event):
                if not self.is_running: return
                user = event.user.unique_id
                if self._should_show(user, "followed", False, 0):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"<span style='color:#000000;font-weight:bold'>[TT]</span> "
                        f"<span style='color:{color}'><b>{user}</b></span> followed")

            async def on_share(event):
                if not self.is_running: return
                user = event.user.unique_id
                if self._should_show(user, "shared", False, 0):
                    color = f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                    self.message.emit(
                        f"<span style='color:#000000;font-weight:bold'>[TT]</span> "
                        f"<span style='color:{color}'><b>{user}</b></span> shared the live")

            client.add_listener(CommentEvent, on_comment)
            client.add_listener(LikeEvent, on_like)
            client.add_listener(GiftEvent, on_gift)
            client.add_listener(FollowEvent, on_follow)
            client.add_listener(ShareEvent, on_share)

            client.run()

        except Exception as e:
            self.status_msg.emit(f"Error: {e}")
        finally:
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()
