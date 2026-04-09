# ChatGate

**Dynamic Transparent Overlay & Smart Filter for Twitch and YouTube**

ChatGate is a high-performance, dual-window live chat monitor designed for streamers. It features a transparent, click-through overlay that sits directly over your games, paired with a powerful controller to filter out spam and low-value messages in real-time. Supports both Twitch and YouTube Live simultaneously.

## Key Features

- **Dual-Window Architecture**: A dedicated **Controller** for settings and an **Invisible Overlay** for the game.
- **Click-Through Overlay**: The chat stays on top of your game but doesn't intercept mouse clicks.
- **Smart Logic Gate**: Automatically activates filters only when chat speed (MPS) exceeds your threshold.
- **Multi-Platform**: Connect to **Twitch** and **YouTube Live** at the same time — messages from both feed into a single unified overlay.
- **Platform Badges**: Each message shows a Twitch or YouTube icon so you always know where it came from.
- **Role Bypass**: Ensure Mod, VIP, Sub, and YouTube Member messages always break through the filter, no matter how fast chat is moving.
- **Customizable Appearance**: Real-time sliders for background opacity, window width, and font scaling.
- **Dark & Light Theme**: Toggle between themes from the controller.
- **No-Auth Connection**: Connects anonymously to any Twitch channel. No login required.
- **Global Hotkey**: Press `Ctrl+Shift+O` to instantly toggle the overlay visibility while in-game.
- **Auto-Reconnect**: Automatically reconnects with exponential backoff if either platform drops.
- **System Tray**: Minimize to the system tray to keep things clean while streaming.
- **Update Checker**: Automatically checks GitHub for newer releases on startup.

## Installation

1. **Download**: Grab the latest `ChatGate.exe` from the [Releases](https://github.com/twhippp/ChatGate/releases) page.
2. **Place**: Put the `.exe` in its own folder (it will create a `settings.json` file to remember your preferences and overlay position).
3. **Run**: Double-click `ChatGate.exe`. No Python installation required.

## Usage

### Connecting

- **Twitch**: Enter a channel name on the Twitch tab and click **Connect**.
- **YouTube**: Enter a `@handle`, full stream URL, or video ID on the YouTube tab and click **Connect**.
- Both platforms can be connected simultaneously.

### Positioning the Overlay

1. Click **Unlock Overlay to Move**.
2. A handle will appear on the overlay — drag it to your preferred location.
3. Click **Lock Position** to make it click-through again and hide the handle.

### Filtering

Adjust the **MPS Limit**. When chat moves faster than this threshold (Messages Per Second), the gate closes and low-effort messages get filtered out — short replies, emote spam, and common phrases like "lol" or "gg". Substantive messages like questions and unique comments still come through. Role Bypass ensures Mods, VIPs, Subs, and YouTube Members always get through regardless of speed.

### Visibility & Hotkey

Use the **Opacity** slider to blend the chat into your game's UI. Press `Ctrl+Shift+O` at any time — even while in a game — to show or hide the overlay.

> ⚠ **Important**: Your game must be running in **Borderless Windowed** mode for the overlay to appear on top of it. True exclusive fullscreen gives the game complete control of the display, preventing any overlay from rendering. This is a Windows limitation that affects all overlay tools including OBS. Most modern games support borderless windowed in their video settings, and it's the recommended mode for streaming in general.

## Controls

| Action | Control |
| :--- | :--- |
| **Toggle Overlay** | `Ctrl + Shift + O` |
| **Move Chat Window** | Unlock via Controller → Drag Handle |
| **Adjust Width** | Width Slider in Controller |
| **Adjust Opacity** | Opacity Slider in Controller |
| **Switch Theme** | Theme button in Controller |
| **Minimize to Tray** | Close button (if "Minimize to tray on close" is checked) |

## For Developers

### Requirements

Python dependencies are managed via a virtual environment. [uv](https://github.com/astral-sh/uv) is recommended:

```powershell
uv venv
uv pip install -r requirements.txt
```

If you prefer standard pip with an existing Python installation:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Running from Source

```powershell
.venv\Scripts\python.exe main.py
```

### Building the EXE

A `CreateEXE.bat` file is included for convenience. Just double-click it or run:

```powershell
CreateEXE.bat
```

This runs the full PyInstaller command with all the correct flags. The output exe will be in the `dist/` folder.

To run the command manually:

```powershell
python -m PyInstaller --onefile --windowed --name ChatGate --icon=ChatGate.ico --add-data "ChatGate.ico;." --hidden-import pytchat --hidden-import PyQt5.QtSvg main.py
```

### Project Structure

```
ChatGate/
├── main.py          # Main controller window and IRC/YouTube threads
├── overlay.py       # Transparent click-through overlay window
├── ChatGate.ico     # Application icon
├── CreateEXE.bat    # One-click build script for the Windows exe
├── requirements.txt # Python dependencies
└── settings.json    # Auto-generated user settings (do not commit)
```

## Notes

- **Borderless Windowed Required**: The overlay cannot appear on top of games running in exclusive fullscreen — this is a fundamental Windows limitation affecting all overlay tools including OBS.
- **Anonymous Twitch Mode**: ChatGate connects via `justinfan`, so it cannot send messages or view Sub-Only chat if the streamer has strict privacy settings enabled.
- **YouTube**: The channel must be currently live — pytchat cannot read VOD or offline chat.
- **Platform Support**: Optimized for Windows. Also tested and fully functional on Bazzite (Fedora) under ProtonTricks.

## Contributing

Got an idea for a better filter or a new feature? Feel free to open an issue or submit a pull request!