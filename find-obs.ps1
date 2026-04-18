# ============================================================
#  Find OBS Studio Installation & Enable ChatGate Script
# ============================================================

param(
    [switch]$EnableOnly,  # Just enable, don't search
    [switch]$Disable      # Disable the script
)

$obsPaths = @(
    "C:\Program Files (x86)\Steam\steamapps\common\OBS Studio",
    "C:\Program Files\Steam\steamapps\common\OBS Studio",
    "$env:ProgramFiles\OBS Studio",
    "${env:ProgramFiles(x86)}\OBS Studio",
    "$env:LOCALAPPDATA\OBS Studio",
    "C:\OBS Studio"
)

$scriptName = "obs-chatgate-launcher.lua"
$scriptContent = @"
-- ============================================================
--  ChatGate Auto-Launcher for OBS Studio
--  
--  This automatically launches ChatGate when OBS starts.
--  Reads settings.json to check if launch_with_obs is enabled.
-- ============================================================

obs = obslua

function script_description()
    return "Automatically launches ChatGate when OBS Studio starts"
end

function script_load()
    launch_chatgate()
end

function script_unload()
end

function read_settings()
    local settings_path = os.getenv("APPDATA") .. "\\ChatGate\\settings.json"
    local file = io.open(settings_path, "r")
    if not file then
        return nil
    end
    local content = file:read("*all")
    file:close()
    
    local settings = {}
    for key, value in string.gmatch(content, '"(%w+)":%s*([%w]+)') do
        settings[key] = value
    end
    
    local enabled = string.match(content, '"launch_with_obs":%s*([%w]+)')
    if enabled == "true" then
        return true
    end
    return false
end

function launch_chatgate()
    if read_settings() == false then
        return
    end
    
    local chatgate_paths = {
        os.getenv("LOCALAPPDATA") .. "\\ChatGate\\ChatGate.exe",
        os.getenv("PROGRAMFILES") .. "\\ChatGate\\ChatGate.exe",
        os.getenv("PROGRAMFILES(X86)") .. "\\ChatGate\\ChatGate.exe"
    }
    
    local chatgate_exe = nil
    for _, path in ipairs(chatgate_paths) do
        local file = io.open(path, "r")
        if file then
            io.close(file)
            chatgate_exe = path
            break
        end
    end
    
    if chatgate_exe then
        os.execute("start \"\" \"" .. chatgate_exe .. "\"")
    end
end
"@

# Also install to user AppData/scripts as primary location
$userScripts = "$env:APPDATA\obs-studio\scripts"
New-Item -ItemType Directory -Force -Path $userScripts | Out-Null
$userLuaPath = Join-Path $userScripts $scriptName
$scriptContent | Out-File -FilePath $userLuaPath -Encoding UTF8 -Force
Write-Output "Installed to user AppData: $userLuaPath"

# Also install to OBS installation folders
$scriptPath = "data\obs-plugins\frontend-tools\scripts"
foreach ($basePath in $obsPaths) {
    if ($basePath -and (Test-Path $basePath)) {
        $fullPath = Join-Path $basePath $scriptPath
        if (Test-Path $fullPath) {
            $luaPath = Join-Path $fullPath $scriptName
            $scriptContent | Out-File -FilePath $luaPath -Encoding UTF8 -Force
            Write-Output "Installed to OBS: $luaPath"
        }
    }
}

# Enable in OBS config - point to user AppData location
$obsConfig = "$env:APPDATA\obs-studio\obs-studio.json"
if (Test-Path $obsConfig) {
    try {
        $config = Get-Content $obsConfig -Raw | ConvertFrom-Json
        if (!($config | Get-Member -Name "ScriptedSources" -MemberType NoteProperty)) {
            $config | Add-Member -Name "ScriptedSources" -Value @() -MemberType NoteProperty
        }
        
        $found = $false
        if ($config.ScriptedSources) {
            foreach ($src in $config.ScriptedSources) {
                if ($src.settings.script_path -like "*$scriptName") {
                    $found = $true
                    break
                }
            }
        }
        
        if (!$found) {
            $newScript = @{
                "name" = "ChatGate Launcher"
                "settings" = @{
                    "script_path" = $userLuaPath
                }
            }
            $config.ScriptedSources += $newScript
            $config | ConvertTo-Json -Depth 10 | Set-Content $obsConfig -Force
            Write-Output "Enabled in config"
        }
    } catch {
        Write-Output "Config enable failed (non-fatal): $_"
    }
}

Write-Output "Done"
exit 0

# Disable: Remove the script from all locations
if ($Disable) {
    Write-Output "Disabling ChatGate integration..."

    $luaPaths = @(
        "$env:APPDATA\obs-studio\scripts\$scriptName",
        "$env:LOCALAPPDATA\OBS Studio\data\obs-plugins\frontend-tools\scripts\$scriptName"
    )

    foreach ($base in $obsPaths) {
        if ($base -and (Test-Path $base)) {
            $luaPaths += Join-Path $base "data\obs-plugins\frontend-tools\scripts\$scriptName"
        }
    }

    foreach ($path in $luaPaths) {
        if (Test-Path $path) {
            Remove-Item $path -Force
            Write-Output "Removed: $path"
        }
    }

    # Remove from config
    $obsConfig = "$env:APPDATA\obs-studio\obs-studio.json"
    if (Test-Path $obsConfig) {
        try {
            $config = Get-Content $obsConfig -Raw | ConvertFrom-Json
            if ($config.ScriptedSources) {
                $config.ScriptedSources = @($config.ScriptedSources | Where-Object { $_.settings.script_path -notlike "*$scriptName" })
                $config | ConvertTo-Json -Depth 10 | Set-Content $obsConfig -Force
                Write-Output "Removed from config"
            }
        } catch {
            Write-Output "Config update failed (non-fatal)"
        }
    }

    Write-Output "ChatGate integration disabled."
    exit 0
}