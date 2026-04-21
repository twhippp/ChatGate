"""
Twitch Support Module for ChatGate
This module contains all Twitch-related functionality via IRC.

Author: ChatGate Contributors
Date: April 2026
"""

import socket
import random
import re
import time
import threading
import os
import json
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

TWITCH_CHANNEL_EMOTE_URLS = {}

def _format_twitch_emotes(text, channel_name=''):
    for emote in TWITCH_CHANNEL_EMOTE_URLS.keys():
        if emote in text:
            text = text.replace(emote, f':{emote}:')
    return text

def _download_twitch_emotes():
    pass


class IRCThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()
    mod_delete   = pyqtSignal(str)  # Emits username when their messages are deleted

    def __init__(self, channel, threshold, bypass, filters, event_flags, platform_badge_html, fmt_raid, fmt_sub, fmt_subgift, fmt_subgift_bomb, fmt_announcement, fmt_watch_streak, fmt_bits, fmt_first_chat):
        super().__init__()
        chan = channel.lower().strip().replace("#", "")
        self.channel     = f"#{chan}"
        self.threshold   = threshold
        self.bypass      = bypass
        self.filters     = filters
        self.event_flags = event_flags
        self.msg_times   = deque()
        self.is_running  = True
        self.sock        = None
        # Capture formatter functions
        self._platform_badge_html = platform_badge_html
        self._fmt_raid = fmt_raid
        self._fmt_sub = fmt_sub
        self._fmt_subgift = fmt_subgift
        self._fmt_subgift_bomb = fmt_subgift_bomb
        self._fmt_announcement = fmt_announcement
        self._fmt_watch_streak = fmt_watch_streak
        self._fmt_bits = fmt_bits
        self._fmt_first_chat = fmt_first_chat

    def stop(self):
        self.is_running = False
        # Close socket to interrupt blocking recv()
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

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
        msg_id  = tags.get("msg-id", "")
        user    = tags.get("display-name", tags.get("login", "Someone"))
        sys_msg = tags.get("system-msg", "").replace("\\s", " ")

        if msg_id == "raid" and self.event_flags.get("show_raids"):
            return self._fmt_raid(user, tags.get("msg-param-viewerCount", "?"))
        if msg_id in ("sub", "resub") and self.event_flags.get("show_subs"):
            return self._fmt_sub(user, tags.get("msg-param-cumulative-months", ""))
        if msg_id == "subgift" and self.event_flags.get("show_subs"):
            return self._fmt_subgift(user,
                tags.get("msg-param-recipient-display-name", "someone"),
                tags.get("msg-param-months", ""))
        if msg_id in ("submysterygift", "standardpayforward", "communitypayforward") \
                and self.event_flags.get("show_subs"):
            return self._fmt_subgift_bomb(user, tags.get("msg-param-mass-gift-count", "?"))
        if msg_id == "announcement" and self.event_flags.get("show_announcements"):
            color = tags.get("msg-param-color", "PRIMARY")
            return self._fmt_announcement(user, sys_msg, color) if sys_msg else None
        if msg_id == "watch-streak" and self.event_flags.get("show_watch_streaks"):
            return self._fmt_watch_streak(user, tags.get("msg-param-streak-months", "?"))
        return None

    def _download_channel_emotes(self, channel_name):
        import urllib.request
        print(f"[Twitch] Loading emotes for {channel_name}...")
        try:
            req = urllib.request.Request(
                f"https://decapi.me/bttv/emotes/{channel_name}",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                emotes = response.read().decode().strip().split()
                TWITCH_CHANNEL_EMOTE_URLS.clear()
                for emote in emotes:
                    TWITCH_CHANNEL_EMOTE_URLS[emote] = True
            print(f"[Twitch] Loaded {len(TWITCH_CHANNEL_EMOTE_URLS)} channel emotes")
        except Exception as e:
            print(f"[Twitch] Emote load error: {e}")

    def run(self):
        channel_name = self.channel.lstrip('#')
        if channel_name:
            self._download_channel_emotes(channel_name)
        self.sock = socket.socket()
        sock = self.sock

        def _tick():
            while self.is_running:
                time.sleep(1.0)
                now = time.time()
                while self.msg_times and now - self.msg_times[0] > 5.0:
                    self.msg_times.popleft()
                mps = len(self.msg_times) / 5.0
                self.stats_update.emit(mps, mps >= self.threshold)

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

                    tags = {}
                    rest = line
                    if rest.startswith("@"):
                        tag_str, rest = rest[1:].split(" ", 1)
                        tags = dict(t.split("=", 1) for t in tag_str.split(";") if "=" in t)

                    if "USERNOTICE" in rest:
                        html = self._handle_usernotice(tags)
                        if html: self.message.emit(html)
                        continue

                    # Handle moderator message deletion
                    if "CLEARCHAT" in rest:
                        # Format: @room-id=123 CLEARCHAT :username (ban/timeout)
                        # or: @room-id=123 CLEARCHAT (clear all chat)
                        try:
                            if ":" in rest:
                                user_deleted = rest.split(":", 1)[1]
                                self.mod_delete.emit(user_deleted)
                        except:
                            pass
                        continue

                    if "CLEARMSG" in rest:
                        # Format: @target-msg-id=xxx CLEARMSG :message text
                        # Delete message by ID (we emit the user from tags if available)
                        try:
                            if "login=" in rest:
                                # Extract login from tags
                                login_match = re.search(r'login=([^;\s]+)', rest)
                                if login_match:
                                    user_deleted = login_match.group(1)
                                    self.mod_delete.emit(user_deleted)
                        except:
                            pass
                        continue

                    if "PRIVMSG" not in rest: continue

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

                    bits = tags.get("bits", "")
                    if bits and self.event_flags.get("show_bits"):
                        self.message.emit(self._fmt_bits(user, bits, content.strip()))
                        continue

                    badges = tags.get("badges", "")
                    roles  = []
                    if "broadcaster" in badges:       roles.append("broadcaster")
                    if tags.get("mod") == "1":        roles.append("mod")
                    if "vip" in badges:               roles.append("vip")
                    if tags.get("subscriber") == "1": roles.append("sub")

                    if tags.get("first-msg") == "1" and self.event_flags.get("show_first_chat"):
                        self.message.emit(self._fmt_first_chat(user, content.strip()))
                        continue

                    if self._should_show(user, content, roles, mps):
                        color = tags.get("color") or f"hsl({abs(hash(user)) % 360}, 80%, 75%)"
                        channel_name = self.channel.lstrip('#')
                        content = _format_twitch_emotes(content, channel_name)
                        self.message.emit(
                            f"{self._platform_badge_html('twitch')}{self._role_badges_html(roles)}"
                            f"<span style='color:{color}'><b>{user}</b></span>: {content}")

        except Exception:
            pass
        finally:
            sock.close()
            if self.is_running:
                self.status_msg.emit("Disconnected")
                self.disconnected.emit()
