$ErrorActionPreference = "Stop"

$browserRoot = $PSScriptRoot
$chromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
)
$chromeExe = ($chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
if (-not $chromeExe) {
    throw "Standard Chrome was not found."
}

$profileDir = Join-Path $browserRoot "profile-taobao"
$cacheDir = Join-Path $browserRoot "cache-taobao"
$workspaceRoot = Split-Path $browserRoot -Parent
$downloadDir = Join-Path $workspaceRoot "data\exports"
$url = "https://chromewebstore.google.com/detail/codex/hehggadaopoacecdllhhajmbjkdcmajg"

New-Item -ItemType Directory -Force -Path $profileDir, $cacheDir, $downloadDir | Out-Null

# Chrome profile cannot be shared by a no-proxy and proxy instance at once.
$profilePattern = [regex]::Escape($profileDir)
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object { $_.CommandLine -match $profilePattern } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$argsList = @(
    "--user-data-dir=$profileDir",
    "--disk-cache-dir=$cacheDir",
    "--download-default-directory=$downloadDir",
    "--no-first-run",
    "--no-default-browser-check",
    $url
)

Start-Process -FilePath $chromeExe -ArgumentList $argsList | Out-Null

[pscustomobject]@{
    Status = "Started"
    ChromeExe = $chromeExe
    Profile = $profileDir
    Proxy = "system proxy enabled for extension install"
    Url = $url
}
