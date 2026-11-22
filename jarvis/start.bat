@echo off
title Jarvis
REM Starts Jarvis. Pulls the latest code first, restarts after a crash or an update.
REM Saying "go to sleep" closes it for real.
cd /d %~dp0
call .venv\Scripts\activate
:loop
python update.py
set PY=python
if exist .venv\Scripts\Jarvis.exe set PY=.venv\Scripts\Jarvis.exe
%PY% jarvis.py
if %errorlevel%==0 goto :eof
if %errorlevel%==3 goto loop
echo Jarvis stopped unexpectedly. Restarting in 5 seconds. Close this window to stop.
timeout /t 5 /nobreak >nul
goto loop
