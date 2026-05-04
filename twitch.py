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
import requests
from collections import deque
from PyQt5.QtCore import QThread, pyqtSignal

TWITCH_CHANNEL_EMOTES = {}
TWITCH_GLOBAL_EMOTES = {}
TWITCH_NATIVE_GLOBAL_EMOTES = {}
EMOTE_CACHE_DIR = None
emote_progress = None  # Will be set to pyqtSignal(int, int) if available

def _get_emote_cache_dir():
    global EMOTE_CACHE_DIR
    if EMOTE_CACHE_DIR is None:
        EMOTE_CACHE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChatGate", "twitch_emotes")
        os.makedirs(EMOTE_CACHE_DIR, exist_ok=True)
    return EMOTE_CACHE_DIR
 
def _download_channel_emotes_from_twitchemotes(channel_name):
    cache_dir = _get_emote_cache_dir()
    channel_cache_dir = os.path.join(cache_dir, channel_name.lower())
    os.makedirs(channel_cache_dir, exist_ok=True)
    
    print(f"[Twitch Emotes] Step 1: Getting user ID for {channel_name}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(
            f"https://api.ivr.fi/v2/twitch/user?login={channel_name}",
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        user_data = resp.json()
        print(f"[Twitch Emotes] API response received, type: {type(user_data)}")
        if isinstance(user_data, list) and len(user_data) > 0:
            user_id = user_data[0].get('id')
        else:
            user_id = None
        if not user_id:
            print(f"[Twitch Emotes] Could not get user ID for {channel_name} - user not found")
            return
        print(f"[Twitch Emotes] User ID: {user_id}")
    except Exception as e:
        print(f"[Twitch Emotes] Error getting user ID: {e}")
        return
    
    print(f"[Twitch Emotes] Step 2: Fetching emote page for user ID {user_id}...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        resp = requests.get(
            f"https://twitchemotes.com/channels/{user_id}",
            headers=headers,
            timeout=15
        )
        resp.raise_for_status()
        html = resp.text
        print(f"[Twitch Emotes] Page fetched, length: {len(html)} chars")
    except Exception as e:
        print(f"[Twitch Emotes] Error fetching emote page: {e}")
        return
    
    print(f"[Twitch Emotes] Step 3: Parsing emote data...")
    import re as regex
    
    emote_pattern = regex.compile(r'<img[\s\S]*?src="(https://static-cdn\.jtvnw\.net/emoticons/v[12]/[^"]+)"[\s\S]*?data-regex="([^"]+)"')
    matches = emote_pattern.findall(html)
    
    if len(matches) < 10:
        emote_pattern2 = regex.compile(r'<img[\s\S]*?data-regex="([^"]+)"[\s\S]*?src="(https://static-cdn\.jtvnw\.net/emoticons/v[12]/[^"]+)"')
        matches2 = emote_pattern2.findall(html)
        if matches2:
            matches2 = [(url, name) for name, url in matches2]
            matches = list(matches) + matches2
    
    print(f"[Twitch Emotes] Pattern result: {len(matches)} matches")
    if matches:
        print(f"[Twitch Emotes] Sample matches:")
        for i, m in enumerate(matches[:10]):
            print(f"  {i+1}. {m[1]} -> {m[0]}")
    
    TWITCH_CHANNEL_EMOTES.clear()
    
    print(f"[Twitch Emotes] Step 4: Processing {len(matches)} emote images...")
    for match in matches:
        if len(match) >= 2:
            img_url, emote_name = match[0], match[1]
        else:
            continue
        
        is_animated = 'animated' in img_url.lower() or '/animated/' in img_url or img_url.endswith('.gif')
        
        if is_animated:
            img_source = img_url
            ext = 'gif'
            local_filename = os.path.join(channel_cache_dir, f"{emote_name}.{ext}")
        else:
            img_source = img_url
            ext = 'png'
            local_filename = os.path.join(channel_cache_dir, f"{emote_name}.{ext}")
        
        if not os.path.exists(local_filename):
            try:
                resp = requests.get(img_url, timeout=10)
                resp.raise_for_status()
                with open(local_filename, 'wb') as f:
                    f.write(resp.content)
                print(f"[Twitch Emotes] Downloaded {emote_name}.{ext}")
            except Exception as e:
                print(f"[Twitch Emotes] Failed to download {emote_name}: {e}")
                continue
        else:
            print(f"[Twitch Emotes] Using cached {emote_name}.{ext}")
        
        TWITCH_CHANNEL_EMOTES[emote_name] = (img_source, is_animated)
    
    print(f"[Twitch Emotes] Done! Loaded {len(TWITCH_CHANNEL_EMOTES)} emotes for {channel_name}")

TWITCH_NATIVE_GLOBAL_EMOTES = {
    "Kappa": "25",
    "PogChamp": "305954156",
    "4Head": "354",
    "KappaPride": "55338",
    "BibleThump": "86",
    "ResidentSleeper": "245",
    "cmonBruh": "100833",
    "MingLee": "68855",
    "FeelsDankMan": "1902",
    "FeelsBadMan": "1901",
    "FeelsGoodMan": "1900",
    "KappaWealth": "121789",
    "KappaClaus": "1491726",
    "KappaRoss": "1443380",
    "TheThing": "1115725",
    "PeoplesChamp": "29617",
    "SwiftRage": "28",
    "LUL": "425618",
    "LULW": "1130346",
    "PogU": "1315202",
    "WideHard": "466917",
    "NotLikeThis": "112443",
    "HeyGuys": "81469",
    "SingsMic": "1062987",
    "catJAM": "834303",
    "D:": "68",
    ":)": "1",
    ":(": "2",
    ":D": "3",
    "B)": "4",
    ";)": "5",
    "Keepo": "1904",
    "Kapow": "133537",
    "Shazam": "1000163",
    "RipCheer": "1888470",
    "BitBoss": "1855965",
    "TriHard": "1202322",
    "Jebaited": "114836",
    "NinjaTroll": "6452",
    "CopyThis": "1001169",
    "ThanksGuys": "1000642",
    "UnSane": "1001114",
    "HSCerious": "489126",
    "Hahasaurus": "1000026",
    "Melted": "1102696",
    "Stare": "1003173",
    "Strawberry": "1770715",
    "PogBones": "1151102",
    "hyperSlur": "1264591",
    "darkSlur": "1264590",
    "angelThump": "10005",
    "PizzaTime": "475605",
    "popcorn": "1198242",
    "EZ": "1887856",
    "Clap": "1009733",
    "BasedGod": "1454463",
    "modLove": "1915811",
    "pepeD": "239582",
    "peepoHappy": "360606",
    "peepoSad": "360610",
    "FeelsOkayMan": "2309426",
    "Comfy": "1040868",
    "PagMan": "3020395",
    "widePeepoHappy": "405143",
    "widePeepoSad": "405145",
    "widePeepoHug": "405142",
    "peepoClap": "106695670",
    "peepoLove": "212516",
    "peepoJam": "212521",
    "FeelsStrongMan": "1903",
    "PagChomp": "3020396",
}

def _download_global_emotes_from_twitchemotes():
    global TWITCH_GLOBAL_EMOTES
    
    # First load Twitch native global emotes (Kappa, PogChamp, etc.)
    total = len(TWITCH_NATIVE_GLOBAL_EMOTES)
    for i, (emote_name, emote_id) in enumerate(TWITCH_NATIVE_GLOBAL_EMOTES.items()):
        # Probe a small set of CDN URL patterns and pick the first that returns 200
        candidates = [
            f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/static/3.0",
            f"https://static-cdn.jtvnw.net/emoticons/v1/{emote_id}/1.0",
        ]
        chosen = None
        for c in candidates:
            try:
                h = requests.head(c, timeout=5, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
                if h.status_code == 200:
                    chosen = c
                    break
            except Exception:
                pass
        if not chosen:
            # fallback to the first candidate even if probe failed
            chosen = candidates[0]
        TWITCH_GLOBAL_EMOTES[emote_name] = (chosen, False)
        if emote_progress:
            emote_progress.emit(i + 1, total)

    # Merge in emotes from twitchemotes.com Global Emotes section
    print("[Twitch Global Emotes] Fetching Global Emotes from twitchemotes.com ...")
    try:
        resp = requests.get("https://twitchemotes.com/", timeout=15)
        resp.raise_for_status()
        html = resp.text
        # Find the Global Emotes section
        import re as regex
        # The section is <h3>Global Emotes</h3> ... <div class="..."> ... with multiple <img> tags
        section_match = regex.search(r'<h3[^>]*>\s*Global Emotes\s*</h3>([\s\S]+?)(<h3|<footer)', html, regex.IGNORECASE)
        if section_match:
            section = section_match.group(1)
            # Find all <img ...> tags inside the section and extract attributes robustly
            img_tags = regex.findall(r'<img[^>]+>', section)
            found = 0
            for tag in img_tags:
                m_name = regex.search(r'data-regex="([^\"]+)"', tag)
                m_src  = regex.search(r'src="([^\"]+)"', tag)
                if not m_name or not m_src:
                    # try the reversed attribute order or single-quoted attributes
                    m_name = m_name or regex.search(r"data-regex='([^']+)'", tag)
                    m_src  = m_src  or regex.search(r"src='([^']+)'", tag)
                if m_name and m_src:
                    emote_name = m_name.group(1)
                    img_url = m_src.group(1)
                    if img_url.startswith('//'):
                        img_url = 'https:' + img_url
                    is_animated = img_url.lower().endswith('.gif')
                    TWITCH_GLOBAL_EMOTES[emote_name] = (img_url, is_animated)
                    found += 1
            print(f"[Twitch Global Emotes] Found {found} emotes from twitchemotes.com")
        else:
            print("[Twitch Global Emotes] Could not find Global Emotes section in twitchemotes.com HTML")
    except Exception as e:
        print(f"[Twitch Global Emotes] Error fetching twitchemotes.com: {e}")

    # Then add BTTV global emotes
    print("[Twitch Global Emotes] Fetching BTTV global emotes...")
    try:
        resp = requests.get(
            "https://api.betterttv.net/3/cached/emotes/global",
            timeout=15
        )
        resp.raise_for_status()
        emotes = resp.json()
        print(f"[Twitch Global Emotes] Found {len(emotes)} BTTV emotes")
    except Exception as e:
        print(f"[Twitch Global Emotes] Error fetching BTTV: {e}")
        emotes = []

    total += len(emotes)
    for i, emote in enumerate(emotes):
        emote_id = emote.get("id")
        emote_name = emote.get("code")
        is_animated = emote.get("animated", False)

        if not emote_id or not emote_name:
            continue

        if is_animated:
            img_source = f"https://cdn.betterttv.net/emote/{emote_id}/3x.gif"
        else:
            img_source = f"https://cdn.betterttv.net/emote/{emote_id}/3x.png"

        TWITCH_GLOBAL_EMOTES[emote_name] = (img_source, is_animated)
        if emote_progress:
            emote_progress.emit(len(TWITCH_NATIVE_GLOBAL_EMOTES) + i + 1, total)

    if emote_progress:
        emote_progress.emit(total, total)
    print(f"[Twitch Global Emotes] Done! Loaded {len(TWITCH_GLOBAL_EMOTES)} total global emotes")
  
def _format_twitch_emotes(text):
    orig_text = text
    # Debug: log what we're searching for
    if any(e in text for e in ["Kappa", "PogChamp", "LUL"]):
        print(f"[Emote] Checking text: {text} | Global emote keys sample: {list(TWITCH_GLOBAL_EMOTES.keys())[:5]}")
    for emote_name, (img_source, is_animated) in TWITCH_GLOBAL_EMOTES.items():
        if emote_name in text:
            text = text.replace(emote_name, f'<img src="{img_source}" height="28" alt="{emote_name}"/>')
    for emote_name, (img_source, is_animated) in TWITCH_CHANNEL_EMOTES.items():
        if emote_name in text:
            text = text.replace(emote_name, f'<img src="{img_source}" height="28" alt="{emote_name}"/>')
    if text != orig_text:
        print(f"[Emote] Replaced: {text[:80]}...")
    return text
 
 
class IRCThread(QThread):
    message      = pyqtSignal(str)
    stats_update = pyqtSignal(float, bool)
    status_msg   = pyqtSignal(str)
    disconnected = pyqtSignal()
    mod_delete   = pyqtSignal(str)
 
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
        print(f"[Twitch] Loading emotes for {channel_name}...")
        _download_channel_emotes_from_twitchemotes(channel_name)
 
    def run(self):
        channel_name = self.channel.lstrip('#')
        
        print(f"[Twitch] Starting, global emotes count: {len(TWITCH_GLOBAL_EMOTES)}")
        if not TWITCH_GLOBAL_EMOTES:
            print("[Twitch] Starting global emote download thread...")
            def download_global():
                print("[Twitch] Running global emote download...")
                _download_global_emotes_from_twitchemotes()
                print(f"[Twitch] Download complete, global emotes: {len(TWITCH_GLOBAL_EMOTES)}")
            threading.Thread(target=download_global, daemon=True).start()
        
        if channel_name:
            def download_emotes():
                self._download_channel_emotes(channel_name)
            threading.Thread(target=download_emotes, daemon=True).start()
        
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
 
                    if "CLEARCHAT" in rest:
                        try:
                            if ":" in rest:
                                user_deleted = rest.split(":", 1)[1]
                                self.mod_delete.emit(user_deleted)
                        except:
                            pass
                        continue
 
                    if "CLEARMSG" in rest:
                        try:
                            if "login=" in rest:
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
                        content = _format_twitch_emotes(content)
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
