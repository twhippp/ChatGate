python -m PyInstaller --onefile --windowed --name ChatGate --icon=ChatGate.ico --add-data "ChatGate.ico;." --hidden-import pytchat --hidden-import PyQt5.QtSvg main.py
