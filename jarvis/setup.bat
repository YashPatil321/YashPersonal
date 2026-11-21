@echo off
REM One time setup for Jarvis on Windows. Needs Python 3.11 or 3.12.
cd /d %~dp0
where py >nul 2>nul || (echo Python launcher not found. Install Python 3.12 from python.org and check "Add to PATH". & pause & exit /b 1)
if not exist .venv (
  py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv || (echo Need Python 3.12 or 3.11. & pause & exit /b 1)
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
REM RTX 50 series needs the CUDA 12.8 build of PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cu128 || (echo PyTorch install failed. & pause & exit /b 1)
pip install -r requirements.txt || (echo Package install failed. & pause & exit /b 1)
where claude >nul 2>nul || echo WARNING: claude not found. Install Claude Code, open a terminal, run claude and log in.
echo.
echo Running the checkup...
python jarvis.py --doctor
echo.
echo Next: start.bat to run, install-autostart.bat to start Jarvis when you log in.
pause
