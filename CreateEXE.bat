pip3 install pyinstaller
python -m PyInstaller --onefile --windowed --name ChatGate --icon=ChatGate.ico --add-data "ChatGate.ico;." --collect-all chat_downloader --hidden-import chat_downloader --hidden-import PyQt5.QtSvg main.py
