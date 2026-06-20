$ErrorActionPreference = "Stop"

$browserRoot = $PSScriptRoot
$standardChromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
)
$chromeForTesting = Join-Path $browserRoot "chrome\chrome-win64\chrome.exe"
$chromeExe = ($standardChromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
if (-not $chromeExe -and (Test-Path -LiteralPath $chromeForTesting)) {
    $chromeExe = $chromeForTesting
}
$profileDir = Join-Path $browserRoot "profile-taobao"
$cacheDir = Join-Path $browserRoot "cache-taobao"
$workspaceRoot = Split-Path $browserRoot -Parent
$downloadDir = Join-Path $workspaceRoot "data\exports"
$port = 9222

if (-not (Test-Path -LiteralPath $chromeExe)) {
    throw "Chrome was not found. Install standard Chrome or keep Chrome for Testing under: $chromeForTesting"
}

New-Item -ItemType Directory -Force -Path $profileDir, $cacheDir, $downloadDir | Out-Null

$running = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
    Where-Object {
        $_.ExecutablePath -eq $chromeExe -and
        $_.CommandLine -match "--remote-debugging-port=$port"
    } |
    Select-Object -First 1

if (-not $running) {
    $argsList = @(
        "--remote-debugging-port=$port",
        "--user-data-dir=$profileDir",
        "--disk-cache-dir=$cacheDir",
        "--download-default-directory=$downloadDir",
        "--no-first-run",
        "--no-default-browser-check",
        "https://myseller.taobao.com/home.htm"
    )

    Start-Process -FilePath $chromeExe -ArgumentList $argsList | Out-Null
    Start-Sleep -Seconds 3
}

$version = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/version" -UseBasicParsing
[pscustomobject]@{
    Status = "Running"
    Browser = $version.Browser
    ChromeExe = $chromeExe
    Port = $port
    Profile = $profileDir
    Cache = $cacheDir
    Downloads = $downloadDir
    Url = "https://myseller.taobao.com/home.htm"
}
