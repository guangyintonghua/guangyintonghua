@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动小学数学智能练习系统...
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败，请检查Python环境
    pause
)
