# ChatGate

**Dynamic Transparent Overlay & Smart Filter for Twitch**

ChatGate is a high-performance, dual-window Twitch chat monitor designed for streamers. It features a transparent, click-through overlay that sits directly over your games, paired with a powerful controller to filter out spam and low-value messages in real-time.

## Key Features

  - **Dual-Window Architecture**: A dedicated **Controller** for settings and an **Invisible Overlay** for the game.
  - **Click-Through Overlay**: The chat stays on top of your game but doesn't intercept mouse clicks!
  - **Smart Logic Gate**: Automatically activates filters only when chat speed (MPS) exceeds your threshold.
  - **Role Bypass**: Ensure `[MOD]`, `[VIP]`, and `[SUB]` messages always break through the filter, no matter how fast chat is moving.
  - **Customizable Appearance**: Real-time sliders for background opacity, window width, and font scaling.
  - **No-Auth Connection**: Connects anonymously to any Twitch channel
  - **Global Hotkey**: Press `Ctrl+Shift+O` to instantly toggle the overlay visibility while in-game.

## Installation

1.  **Download**: Grab the latest `ChatGate.exe` from the [Releases](https://github.com/twhippp/ChatGate/releases) page.
2.  **Place**: Put the `.exe` in its own folder (it will create a `settings.json` file to remember your position).
3.  **Run**: Double-click `ChatGate.exe`. No Python installation is required.

## Usage

1.  **Connect**: Enter a Twitch channel and click **Connect**.
2.  **Positioning**:
      - Click **Unlock Overlay to Move**.
      - A purple handle will appear on the chat window. Drag it to your preferred location.
      - Click **Lock Overlay Position** to make it click-through and hide the handle.
3.  **Filtering**: Adjust the **MPS Threshold**. If chat moves faster than this (Messages Per Second), the "Gate" closes and starts filtering.
4.  **Visibility**: Use the **Opacity** slider to blend the chat into your game's UI.

## Controls

| Action | Control |
| :--- | :--- |
| **Toggle Overlay** | `Ctrl + Shift + O` |
| **Move Chat** | Unlock via Controller -\> Drag Purple Bar |
| **Adjust Size** | Width Slider in Controller |

## Notes

  * **Anonymous Mode**: Because ChatGate connects via `justinfan`, it cannot send messages or view "Sub-Only" chat modes if the streamer has strict privacy settings enabled.
  * **Windows Only**: Currently optimized for Windows GDI+ and Win32 API for transparency stability. However, the program was tested on Bazzite (Fedora) and was fully functional under ProtonTricks!

## Contributing

Got an idea for a better filter or a new UI theme? Feel free to open an issue or submit a pull request\!
