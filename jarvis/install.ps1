# Jarvis: one command to install, update, and start it automatically when you log in.
# Run in PowerShell (it's safe to run again any time, it just brings everything up to date):
#   irm https://raw.githubusercontent.com/YashPatil321/YashPersonal/claude/hopeful-bohr-1ramsu/jarvis/install.ps1 | iex
#
# What it does:
#   1. Installs Git if it's missing
#   2. Gets the latest Jarvis into C:\yash-system (that's where updates come from)
#   3. Copies the code into C:\jarvis. Your local_settings.py, CLAUDE.md, notes and .venv are never touched,
#      and any file it replaces is backed up first to C:\jarvis\backup-<date>
#   4. Installs Python packages if this is the first time, plus the camera packages
#   5. Adds "Jarvis" to your Startup folder, so it starts (and updates itself) every time you log in
#   6. Starts Jarvis now

$ErrorActionPreference = "Stop"
$Branch = "claude/hopeful-bohr-1ramsu"
$Repo = "C:\yash-system"
$Dir = "C:\jarvis"
function Step($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function RefreshPath { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

# 1. Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Step "Installing Git"
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
    RefreshPath
}

# 2. Latest code
Step "Getting the latest Jarvis"
if (Test-Path "$Repo\.git") {
    git -C $Repo fetch -q origin $Branch
    git -C $Repo checkout -q $Branch
    git -C $Repo reset -q --hard "origin/$Branch"
} else {
    git clone -q -b $Branch https://github.com/YashPatil321/YashPersonal.git $Repo
}

# 3. Copy into C:\jarvis
Step "Updating C:\jarvis"
New-Item -ItemType Directory -Force $Dir | Out-Null
$src = "$Repo\jarvis"
$backup = "$Dir\backup-" + (Get-Date -Format "yyyyMMdd-HHmm")
$managed = Get-ChildItem $src -File | Where-Object { $_.Name -match '^(jarvis.*\.py|update\.py|requirements.*\.txt|.*\.html|README\.md|HANDOFF\.md|install\.ps1)$' }
foreach ($f in $managed) {
    $dst = Join-Path $Dir $f.Name
    if ((Test-Path $dst) -and ((Get-FileHash $dst).Hash -ne (Get-FileHash $f.FullName).Hash)) {
        New-Item -ItemType Directory -Force $backup | Out-Null
        Copy-Item $dst $backup
    }
    Copy-Item $f.FullName $dst -Force
}
foreach ($n in "start.bat", "setup.bat", "install-autostart.bat", "remove-autostart.bat", "CLAUDE.md", "local_settings.example.py") {
    if (-not (Test-Path "$Dir\$n")) { Copy-Item "$src\$n" "$Dir\$n" }
}
if (-not (Test-Path "$Dir\local_settings.py")) { Copy-Item "$src\local_settings.example.py" "$Dir\local_settings.py" }
if (Test-Path $backup) { Write-Host "   Your old copies of changed files are in $backup" }

# 4. Python packages
$py = "$Dir\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Step "First time: installing Python and packages (10 to 20 minutes, leave it running)"
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        RefreshPath
    }
    Push-Location $Dir
    py -3.12 -m venv .venv
    if (-not (Test-Path $py)) { py -3.11 -m venv .venv }
    Pop-Location
    & $py -m pip install --upgrade pip
    & $py -m pip install torch --index-url https://download.pytorch.org/whl/cu128   # RTX 50 series build
}
Step "Checking packages"
& $py -m pip install -q -r "$Dir\requirements.txt"
Push-Location $Dir
& $py update.py --extras   # camera, face ID, screenshots. A failure here only turns those off
Pop-Location
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "   WARNING: Claude Code (the claude command) isn't installed. Jarvis needs it to answer questions." -ForegroundColor Yellow
}

# 5. Start when you log in
Step "Starting Jarvis when you log in"
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Jarvis.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = "$Dir\start.bat"
$s.WorkingDirectory = $Dir
$s.WindowStyle = 7   # minimized
$s.Description = "Jarvis voice assistant (updates itself every start)"
$s.Save()
Write-Host "   Added: $lnk"
Write-Host "   (See it with Win+R, type shell:startup. Delete Jarvis there to stop it starting.)"

# 5b. Old Jarvis tasks in Task Scheduler start a second, hidden copy that can't control the screen. Remove them.
$old = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $_.TaskName -match "jarvis" -or ((($_.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" }) -join " ") -match "jarvis")
}
if ($old) {
    Step "Removing old Jarvis tasks from Task Scheduler: $(($old | ForEach-Object TaskName) -join ', ')"
    foreach ($t in $old) {
        try { Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -Confirm:$false -ErrorAction Stop }
        catch {
            Write-Host "   Windows needs your OK to remove '$($t.TaskName)'. Click Yes on the prompt." -ForegroundColor Yellow
            $cmd = "Unregister-ScheduledTask -TaskName '$($t.TaskName)' -TaskPath '$($t.TaskPath)' -Confirm:`$false"
            Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile", "-Command", $cmd
        }
    }
}

# 6. Start now (restart it if it's already running, so the new code loads)
Step "Starting Jarvis"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match "jarvis\.py" -or $_.CommandLine -match "jarvis_orb\.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" |
    Where-Object { $_.CommandLine -match "jarvis\\start\.bat" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath "$Dir\start.bat" -WorkingDirectory $Dir -WindowStyle Minimized

Write-Host ""
Write-Host "Done. Jarvis is starting (minimized in the taskbar). It updates itself every time it starts," -ForegroundColor Green
Write-Host "at 4 AM, and when you say 'hey jarvis, update yourself'. Say 'hey jarvis, test the computer' to check screen control." -ForegroundColor Green
