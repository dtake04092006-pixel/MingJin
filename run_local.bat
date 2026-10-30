@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".env" (
  echo [menh_tan] chua co file .env - copy .env.example thanh .env roi dien DISCORD_TOKEN va API_TOKEN
  exit /b 1
)
echo [menh_tan] dang chay o che do local, Ctrl+C de dung
python -m menh_tan
