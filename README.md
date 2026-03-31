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
- **Update Checker**: Automatically checks GitHub for newer releases and tags on startup.

## Installation

1. **Download**: Grab the latest `ChatGate.exe` from the [Releases](https://github.com/twhippp/ChatGate/releases) page.
2. **Place**: Put the `.exe` in its own folder (it will create a `settings.json` file to remember your preferences and overlay position).
3. **Run**: Double-click `ChatGate.exe`. No Python installation required.

## Usage

1. **Connect**:
   - **Twitch**: Enter a channel name on the Twitch tab and click **Connect**.
   - **YouTube**: Enter a `@handle`, full stream URL, or video ID on the YouTube tab and click **Connect**.
   - Both platforms can be connected simultaneously.

2. **Positioning**:
   - Click **Unlock Overlay to Move**.
   - A handle will appear on the overlay. Drag it to your preferred location.
   - Click **Lock Position** to make it click-through again and hide the handle.

3. **Filtering**: Adjust the **MPS Limit**. When chat moves faster than this (Messages Per Second), the gate closes. Low-effort messages (short replies, emote spam, common phrases like "lol" or "gg") get filtered out, while substantive messages like questions and unique comments still come through.

4. **Visibility**: Use the **Opacity** slider to blend the chat into your game's UI.

5. **Hotkey**: Press `Ctrl+Shift+O` at any time — even while in a game — to show or hide the overlay.

> ⚠ **Important**: Your game must be running in **Borderless Windowed** mode for the overlay to appear on top of it. True exclusive fullscreen gives the game complete control of the display, which prevents any overlay from rendering on top. This is a Windows limitation, not specific to ChatGate. Most games support borderless windowed in their video settings, and it's the recommended mode for streaming in general.

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

```
pip install -r requirements.txt
```

### Running from source

```
python main.py
```

### Building the exe

A `CreateEXE.bat` file is included in the repo for convenience. Just double-click it or run:

```
CreateEXE.bat
```

This runs the full PyInstaller command with all the correct flags. The output exe will be in the `dist/` folder.

If you want to run the command manually:

```
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

- **Borderless Windowed Required**: The overlay cannot appear on top of games running in exclusive fullscreen mode — this is a fundamental Windows limitation that affects all overlay tools, including OBS. Run your game in **Borderless Windowed** mode for the overlay to work correctly. Most modern games support this in their video/display settings.
- **Anonymous Mode**: ChatGate connects via `justinfan` on Twitch, so it cannot send messages or view Sub-Only chat if the streamer has strict privacy settings enabled.
- **YouTube**: Requires `pytchat` (`pip install pytchat`). The channel must be currently live — pytchat cannot read VOD or offline chat.
- **Windows Primary**: Optimized for Windows GDI+ and Win32 API for transparency and hotkey support. The app has also been tested on Bazzite (Fedora) under ProtonTricks and was fully functional.

## Contributing

Got an idea for a better filter or a new feature? Feel free to open an issue or submit a pull request!