; ============================================================
;  ChatGate Installer  —  NSIS Script (FIXED)
; ============================================================

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"

; ---------- Metadata ----------
!define APP_NAME        "ChatGate"
!define APP_VERSION     "0.4.0-beta"
!define APP_PUBLISHER   "twhippp"
!define APP_URL         "https://github.com/twhippp/ChatGate"
!define APP_EXE         "ChatGate.exe"
!define UNINSTALL_KEY   "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

Name              "${APP_NAME} ${APP_VERSION}"
OutFile           "ChatGate_Setup.exe"
Unicode           True
RequestExecutionLevel user

InstallDir        "$LOCALAPPDATA\${APP_NAME}"
InstallDirRegKey  HKCU "${UNINSTALL_KEY}" "InstallLocation"

; ---------- UI ----------
!define MUI_ABORTWARNING
!define MUI_ICON          "ChatGate.ico"
!define MUI_UNICON        "ChatGate.ico"

!define MUI_WELCOMEPAGE_TITLE "Welcome to ${APP_NAME} Setup"
!define MUI_WELCOMEPAGE_TEXT  "This will install ${APP_NAME} ${APP_VERSION}.$\r$\n$\r$\nChatGate is a transparent live-chat overlay for streamers.$\r$\n$\r$\nClick Next to continue."

!define MUI_FINISHPAGE_RUN       "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT  "Launch ${APP_NAME} now"

; ---------- Pages ----------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY

Page custom DesktopShortcutPage DesktopShortcutPageLeave

!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ---------- Variables ----------
Var DesktopShortcut
Var Checkbox

; ---------- Custom Page ----------
Function DesktopShortcutPage
    nsDialogs::Create 1018
    Pop $0

    ${NSD_CreateCheckbox} 0 120u 100% 12u "Create a Desktop shortcut"
    Pop $Checkbox

    nsDialogs::Show
FunctionEnd

Function DesktopShortcutPageLeave
    ${NSD_GetState} $Checkbox $DesktopShortcut
FunctionEnd

; ---------- Install ----------
Section "Install" SecMain

    SetOutPath "$INSTDIR"

    ; Files
    File "dist\${APP_EXE}"
    File "ChatGate.ico"

    ; AppData folder
    CreateDirectory "$APPDATA\${APP_NAME}"

    ; Start Menu
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" \
                   "$INSTDIR\${APP_EXE}" "" "$INSTDIR\ChatGate.ico"

    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk" \
                   "$INSTDIR\Uninstall.exe"

    ; Desktop shortcut (optional)
    ${If} $DesktopShortcut == 1
        CreateShortcut "$DESKTOP\${APP_NAME}.lnk" \
                       "$INSTDIR\${APP_EXE}" "" "$INSTDIR\ChatGate.ico"
    ${EndIf}

    ; Uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Registry
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "DisplayName"     "${APP_NAME}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "DisplayVersion"  "${APP_VERSION}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "Publisher"       "${APP_PUBLISHER}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "URLInfoAbout"    "${APP_URL}"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr   HKCU "${UNINSTALL_KEY}" "DisplayIcon"     "$INSTDIR\ChatGate.ico"
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify"        1
    WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair"        1

SectionEnd

; ---------- Uninstall ----------
Section "Uninstall"

    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\ChatGate.ico"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir  "$INSTDIR"

    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Uninstall ${APP_NAME}.lnk"
    RMDir  "$SMPROGRAMS\${APP_NAME}"

    Delete "$DESKTOP\${APP_NAME}.lnk"

    ; Optional: remove settings
    ; RMDir /r "$APPDATA\${APP_NAME}"

    DeleteRegKey HKCU "${UNINSTALL_KEY}"

SectionEnd