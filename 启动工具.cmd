@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动学生信息表脱敏工具……
echo 启动后请打开 http://127.0.0.1:8000/index.html
python run_local.py
pause
