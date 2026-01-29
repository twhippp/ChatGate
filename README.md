# ChatGate
Dynamic Chat Gate for Twitch!

ChatGate is a customizable Twitch chat viewer and filter that helps you manage messages in real-time. It filters spam, repeated messages, and low-value messages while allowing meaningful conversation to pass. It also provides role-based tags and adaptive filters to keep chat readable and manageable during fast streams.

## Features

- **Role Tags**: Displays `[MOD]`, `[BROADCASTER]`, `[VIP]`, `[SUB]` tags with customizable colors.  
- **Substantive Message Filter**: Blocks short or low-value messages while allowing full sentences and greetings.  
- **Adaptive Minimum Length**: Automatically increases the required message length as chat activity rises.  
- **Per-User Cooldown**: Suppresses repeated messages from the same user unless content changes.  
- **Similarity Detection**: Blocks messages that are too similar to recent messages to prevent copy-paste spam.  
- **Emote Density Cap**: Filters messages that are mostly emotes.  
- **Filter State Indicator**: Displays `FILTER ACTIVE` or `FILTER OFF` with current messages per second (MPS).  
- **Message Fade**: Older messages fade over time to reduce visual clutter.  
- **Configurable Settings**: Set channel, font size, role bypass options, and MPS threshold.  
- **No Authentication Needed**: Connects to Twitch chat via a random anonymous account.

## Installation

1. Download the latest **ChatGate.exe** from the Releases page.  
2. Place the `.exe` anywhere on your computer.  
3. Double-click `ChatGate.exe` to run. No Python installation is required.

> Optional: You can save settings to the same folder as the `.exe`.  

## Usage

1. Enter the Twitch channel name you want to monitor.  
2. Adjust **font size** and **messages per second (MPS) threshold** to control the filter activation.  
3. Check/uncheck **role bypass options** to allow certain roles to bypass the filter.  
4. Click **Connect** to start monitoring chat.  
5. The chat window will display messages with role tags and filtered messages according to your settings.


## Notes

ChatGate connects anonymously, so some private or subscriber-only messages may not appear.

Designed for desktop use; works best with active Python environments.

## Contributing

Contributions are welcome! Please open issues or submit pull requests for new features, bug fixes, or improvements.
