$ErrorActionPreference = "Stop"

$port = 9222
$version = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/version" -UseBasicParsing
$tabs = Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/list" -UseBasicParsing

[pscustomobject]@{
    Status = "OK"
    Browser = $version.Browser
    Port = $port
    TabCount = @($tabs).Count
    CurrentUrls = (@($tabs) | Select-Object -ExpandProperty url) -join " | "
}
