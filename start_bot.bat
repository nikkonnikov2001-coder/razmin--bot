@echo off
REM Запускает бота в фоне без чёрного окна.
REM Положи этот .bat рядом со stretch_bot.py.

cd /d "%~dp0"

REM Если используешь venv — раскомментируй следующую строку:
REM call .venv\Scripts\activate.bat

start "" /B pythonw stretch_bot.py
