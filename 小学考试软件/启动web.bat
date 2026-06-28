@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ====================================
echo   小学数学智能练习系统 - Web 版
echo ====================================
echo.
echo 启动服务器，请稍候...
echo 启动后请用浏览器访问：http://localhost:8000
echo 局域网访问：http://[本机IP]:8000
echo.
echo 按 Ctrl+C 停止服务器
echo.
python web_main.py
pause
