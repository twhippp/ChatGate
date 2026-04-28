@echo off
setlocal
echo ================================================
echo  ChatGate - Build + Package
echo ================================================

:: ---- Step 1: Build the EXE with PyInstaller ----
echo.
echo [1/2] Building ChatGate.exe with PyInstaller...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name ChatGate ^
    --icon=ChatGate.ico ^
    --add-data "ChatGate.ico;." ^
    --add-data ".venv\Lib\site-packages\appdirs.py;appdirs" ^
    --copy-metadata packaging ^
    --collect-all tls_client ^
    --collect-all PyQtWebEngine ^
    --collect-all PyQt5 ^
    --add-binary ".venv\Lib\site-packages\tls_client\dependencies\tls-client-64.dll;tls_client\dependencies" ^
    --hidden-import PyQt5.QtSvg ^
    --hidden-import tls_client ^
    --hidden-import requests ^
    --hidden-import certifi ^
    --hidden-import charset_normalizer ^
    --hidden-import idna ^
    --hidden-import urllib3 ^
    --hidden-import PyQt5.QtWebEngineWidgets ^
    --hidden-import sip ^
    --hidden-import appdirs ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. See output above.
    pause
    exit /b 1
)

echo.
echo EXE built successfully: dist\ChatGate.exe

:: ---- Step 2: Build the installer with NSIS ----
echo.
echo [2/2] Building installer with NSIS...
echo.

:: Safer NSIS detection (avoids parentheses parsing issues)
set "NSIS_EXE="
set "NSIS_PATH1=C:\Program Files (x86)\NSIS\makensis.exe"
set "NSIS_PATH2=C:\Program Files\NSIS\makensis.exe"

if exist "%NSIS_PATH1%" set "NSIS_EXE=%NSIS_PATH1%"
if exist "%NSIS_PATH2%" set "NSIS_EXE=%NSIS_PATH2%"

if "%NSIS_EXE%"=="" (
    where makensis >nul 2>&1
    if not errorlevel 1 set "NSIS_EXE=makensis"
)

if "%NSIS_EXE%"=="" (
    echo.
    echo WARNING: NSIS not found. Skipping installer packaging.
    echo To build the installer, install NSIS from https://nsis.sourceforge.io
    echo Then run:  makensis ChatGate.nsi
    echo.
    echo The standalone EXE is still available at dist\ChatGate.exe
    pause
    exit /b 0
)

echo Using NSIS: %NSIS_EXE%
"%NSIS_EXE%" ChatGate.nsi

if errorlevel 1 (
    echo.
    echo ERROR: NSIS failed. See output above.
    pause
    exit /b 1
)

echo.
echo ================================================
echo  Done!
echo   Standalone EXE  : dist\ChatGate.exe
echo   Installer       : ChatGate_Setup.exe
echo ================================================
pause