@echo off
cd /d "E:\AI工具\淘宝自动上架工具"
pythonw app.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo 启动失败，错误代码: %ERRORLEVEL%
    echo 请尝试直接运行: python app.py
    pause
)
