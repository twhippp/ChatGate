# ChatGate Changelog

## v0.4.1-beta

### New Features
- **Launch with OBS**: Auto-launches with OBS (enabled by default) - runs with `--obs-launch` flag and waits for OBS to start before showing
- **OBS Launch Checkbox**: Toggle option in controller to enable/disable auto-launch with OBS
- **YouTube Subscriber Bypass**: Added separate bypass option for free YouTube subscribers (distinct from paid Members)

### Changes
- **MPS Calculation**: YouTube now updates MPS every second (matching Twitch behavior)

### Bug Fixes
- Fixed app not fully closing when clicking X with "Minimize to tray on close" unchecked
- Various stability improvements

---

## v0.4.0-beta

# 📦 ChatGate v0.4.0-beta — Patch Notes

## ✨ New Features

### 🔍 Advanced Chat Filtering System

* Added **word-based filtering**:

  * **Always Block Words** (hard filter)
  * **High Volume Block Words** (only during spam)
* Added **User Whitelist / Blacklist**

---

### 🎛️ Granular Role Controls

* Replaced simple checkboxes with **3-state bypass system**:

  * `Always` → always show
  * `Normal` → respects filter
  * `Never` → always hide
* Applies to:

  * Broadcaster
  * Mods
  * VIPs
  * Subs
  * YouTube Members

---

### 🎉 Twitch Event Rendering

Added rich, styled event messages:

* Raids
* Subscriptions / Resubs
* Gift subs & gift bombs
* Bits / Cheers
* Announcements
* First-time chatters
* Watch streaks

All with:

* Colored highlight blocks
* Icons (🚨 ⭐ 🎁 💎 📢 🔥 👋)

---

### 🧩 Filters Tab UI

* New dedicated **Filters tab**
* Includes:

  * Bubble-style editable lists
  * Inline removal (✕ buttons)
  * Scrollable containers
* Real-time updates to filtering behavior

---

### 🎨 Dynamic Theming System

* Theme now supports **accent colors per tab**:

  * Twitch → Purple
  * YouTube → Red
  * Filters → Purple
* Fully rebuilt stylesheet system (modular + reusable)

---

### 📊 Improved MPS System

* Added **Combined vs Separate MPS modes**

  * Combined: both platforms share one limit
  * Separate: each platform tracked independently
* Visual gate indicator:

  * 🟢 Gate Open
  * 🔴 Gate Closed
* More accurate MPS calculation using background thread

---

### 🔔 Built-in Auto-Updater (Major)

* Background update check via GitHub tags
* Clickable version label → triggers update flow
* Features:

  * Installer auto-download with progress bar
  * Automatic launch after download
  * Fallback to browser if no installer found

---

### 🧠 Settings System Overhaul

* Settings now stored in:

  * `%APPDATA%/ChatGate/settings.json`
* Added **migration system**:

  * Converts old boolean bypass → new 3-state system
* Expanded settings:

  * Event toggles
  * Filters
  * UI preferences

---

### 📺 YouTube Backend Rewrite

* Switched from `pytchat` → `chat-downloader`
* Improved:

  * Stability
  * Compatibility
* Better member detection via badges

---

### 🛠️ UX Improvements

* Tooltip system added across UI
* Borderless window warning for overlays
* Clickable version label
* Cleaner layout and spacing
* Better status messaging

---

## 🐛 Fixes

* Fixed inconsistent YouTube connection reliability
* Fixed overlay opacity not applying correctly
* Fixed settings not persisting in some cases
* Fixed reconnect edge cases
* Improved error handling across threads
* Reduced UI freezing during heavy chat spikes

---

## ⚠️ Breaking / Notable Changes

* ❗ **Dependency change**:

  * `pytchat` → `chat-downloader`
* ❗ **Settings reset/migration** may occur on first launch
* ❗ Old bypass settings converted to new system

---

## v0.3.0-beta
- Previous version
