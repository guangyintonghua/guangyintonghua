@echo off
chcp 65001 >nul
title 淘宝上架工具 - 启动浏览器

:: 检查端口 9222 是否已在监听
netstat -ano 2>nul | findstr ":9222 " | findstr "LISTENING" >nul
if %ERRORLEVEL% == 0 (
    echo 调试浏览器已在运行（端口 9222 已就绪），可直接使用工具
    timeout /t 3 >nul
    exit /b 0
)

set CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" set CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
if not exist "%CHROME%" (
    echo 未找到 Chrome，请安装 Google Chrome 后重试
    pause & exit /b 1
)

set PROFILE=%~dp0profiles\chrome_debug
if not exist "%PROFILE%" mkdir "%PROFILE%"

echo 正在启动调试模式 Chrome...
echo 请在浏览器中登录淘宝/千牛，然后回到上架工具。

start "" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%" --no-first-run --disable-infobars https://myseller.taobao.com/

timeout /t 2 >nul
