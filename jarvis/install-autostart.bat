@echo off
REM Adds a minimized Jarvis shortcut to your Startup folder so it runs when you log in.
cd /d %~dp0
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Jarvis.lnk'); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Description='Jarvis voice assistant'; $s.Save()"
echo Jarvis will start minimized when you log in. Run remove-autostart.bat to undo.
pause
