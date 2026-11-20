@echo off
REM Runs Jarvis and restarts it if it crashes. Saying "go to sleep" closes it for real.
cd /d %~dp0
call .venv\Scripts\activate
:loop
python jarvis.py
if errorlevel 1 (
  echo Jarvis stopped unexpectedly. Restarting in 5 seconds. Close this window to stop.
  timeout /t 5 /nobreak >nul
  goto loop
)
