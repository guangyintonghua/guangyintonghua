@echo off
chcp 65001 >nul
cd /d "%~dp0.."
node scripts\wechat-store-lowfreq-check.mjs
pause
