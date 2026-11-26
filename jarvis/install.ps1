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
#   5. Creates a Task Scheduler task named "Jarvis" that starts it (and updates it) every time you log in
#   6. Starts Jarvis now

$ErrorActionPreference = "Stop"
# Jarvis runs as administrator (so it can control every window, admin ones too), which needs this installer to
# run as administrator once. If it isn't, it reopens itself as administrator: click Yes on the prompt.
$me = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Opening as administrator. Click Yes on the Windows prompt." -ForegroundColor Cyan
    $url = "https://raw.githubusercontent.com/YashPatil321/YashPersonal/claude/hopeful-bohr-1ramsu/jarvis/install.ps1"
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command", "irm $url | iex"
    return
}
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
Step "Getting the latest Jarvis (shows progress; if it sits still, press Enter once)"
$env:GIT_TERMINAL_PROMPT = "0"; $env:GCM_INTERACTIVE = "never"   # never wait on a hidden login window: the repo is public
git config --global --add safe.directory "*" 2>$null   # admin vs you owning the folder must never block updates
$gitOk = $false
$ErrorActionPreference = "Continue"   # git prints progress on stderr, which must not count as a failure
if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path "$Repo\.git") {
        git -c safe.directory=* -C $Repo fetch --progress origin $Branch
        if ($LASTEXITCODE -eq 0) { git -c safe.directory=* -C $Repo checkout -q -f $Branch 2>$null; git -c safe.directory=* -C $Repo reset -q --hard "origin/$Branch" }
    } else {
        if (Test-Path $Repo) { Remove-Item $Repo -Recurse -Force }
        git -c safe.directory=* clone --progress --depth 50 -b $Branch https://github.com/YashPatil321/YashPersonal.git $Repo
    }
    $gitOk = ($LASTEXITCODE -eq 0) -and (Test-Path "$Repo\jarvis\jarvis.py")
}
$ErrorActionPreference = "Stop"
if (-not $gitOk) {
    # Git failed or hung up: download the code as a zip instead
    Write-Host "   Git didn't work, downloading the code directly instead" -ForegroundColor Yellow
    $zip = "$env:TEMP\atlas-src.zip"; $tmp = "$env:TEMP\atlas-src"
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest "https://codeload.github.com/YashPatil321/YashPersonal/zip/refs/heads/$Branch" -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp -Force
    $top = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (Test-Path $Repo) { Remove-Item $Repo -Recurse -Force }
    Move-Item $top.FullName $Repo
}
if (-not (Test-Path "$Repo\jarvis\jarvis.py")) { throw "Couldn't download Jarvis. Check the internet connection and run this again." }

# 3. Copy into C:\jarvis
Step "Updating C:\jarvis"
New-Item -ItemType Directory -Force $Dir | Out-Null
$src = "$Repo\jarvis"
$backup = "$Dir\backup-" + (Get-Date -Format "yyyyMMdd-HHmm")
$managed = Get-ChildItem $src -File | Where-Object { $_.Name -match '^(jarvis.*\.py|update\.py|requirements.*\.txt|.*\.html|README\.md|HANDOFF\.md|install\.ps1)$' }
$keep = @()
if (Test-Path "$Dir\.local_changes.json") { $keep = Get-Content "$Dir\.local_changes.json" -Raw | ConvertFrom-Json }
foreach ($f in $managed) {
    if ($keep -contains $f.Name) { Write-Host "   kept Jarvis's own edits to $($f.Name)"; continue }
    $dst = Join-Path $Dir $f.Name
    if ((Test-Path $dst) -and ((Get-FileHash $dst).Hash -ne (Get-FileHash $f.FullName).Hash)) {
        New-Item -ItemType Directory -Force $backup | Out-Null
        Copy-Item $dst $backup
    }
    Copy-Item $f.FullName $dst -Force
}
if ((Test-Path "$Dir\start.bat") -and ((Get-FileHash "$Dir\start.bat").Hash -ne (Get-FileHash "$src\start.bat").Hash)) {
    New-Item -ItemType Directory -Force $backup | Out-Null
    Copy-Item "$Dir\start.bat" $backup
}
Copy-Item "$src\start.bat" "$Dir\start.bat" -Force
foreach ($n in "setup.bat", "install-autostart.bat", "remove-autostart.bat", "CLAUDE.md", "local_settings.example.py") {
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
}
$hasNvidia = [bool](Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "NVIDIA" })
$ErrorActionPreference = "Continue"
& $py -m pip install -q --upgrade pip
& $py -c "import torch" *> $null
$hasTorch = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"
if (-not $hasTorch) {
    if ($hasNvidia) {
        Step "Installing the GPU build of PyTorch (about 2.8 GB)"
        & $py -m pip install --retries 10 --resume-retries 20 torch --index-url https://download.pytorch.org/whl/cu128   # RTX 50 series build
    } else {
        Step "No NVIDIA card here: installing the small CPU build of PyTorch"
        & $py -m pip install --retries 10 --resume-retries 20 torch --index-url https://download.pytorch.org/whl/cpu
    }
}
# a copy of Python named Jarvis.exe, so Task Manager shows "Jarvis" instead of "python"
Copy-Item $py "$Dir\.venv\Scripts\Jarvis.exe" -Force
Step "Checking packages"
$req = "$Dir\requirements.txt"
if (-not $hasNvidia) {   # the NVIDIA libraries are about 2 GB and useless without an NVIDIA card
    $req = "$env:TEMP\atlas-req-cpu.txt"
    Get-Content "$Dir\requirements.txt" | Where-Object { $_ -notmatch "^nvidia-" } | Set-Content $req
}
& $py -m pip install -q --retries 10 --no-cache-dir -r $req
& $py -m pip cache purge *> $null   # downloads pip kept around, often gigabytes
Push-Location $Dir
& $py update.py --extras   # camera, face ID, screenshots. A failure here only turns those off
Pop-Location
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "   WARNING: Claude Code (the claude command) isn't installed. Jarvis needs it to answer questions." -ForegroundColor Yellow
}

# 5b. Old Jarvis tasks in Task Scheduler start a second, hidden copy that can't control the screen. Remove them.
Set-StrictMode -Off
$old = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $acts = @($_.Actions | ForEach-Object { try { "$($_.Execute) $($_.Arguments)" } catch { "" } }) -join " "   # some tasks have actions with no program
    $_.TaskName -match "jarvis" -or $acts -match "jarvis"
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

# 5. Start when you log in: a Task Scheduler task named "Jarvis"
Step 'Setting up the "Jarvis" task (starts Jarvis when you log in)'
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c start `"Jarvis`" /min `"$Dir\start.bat`"" -WorkingDirectory $Dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
# Interactive = runs on your desktop, so it can see and control your windows. Never "whether logged on or not".
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest   # admin, on your desktop
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Jarvis.lnk"
$useTask = $true
try {
    Register-ScheduledTask -TaskName "Jarvis" -TaskPath "\" -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
        -Description "Jarvis voice assistant. Starts when you log in and updates itself every start." -Force -ErrorAction Stop | Out-Null
    Write-Host '   Task Scheduler now has a task called "Jarvis" (Task Scheduler Library, at the top).'
    if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host "   Removed the old Startup folder shortcut (the task replaces it)." }
} catch {
    $useTask = $false
    Write-Host "   Windows wouldn't create the task ($($_.Exception.Message)). Using a Startup folder shortcut named Jarvis instead." -ForegroundColor Yellow
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = "$Dir\start.bat"; $sc.WorkingDirectory = $Dir; $sc.WindowStyle = 7
    $sc.Description = "Jarvis voice assistant"; $sc.Save()
}

# 6. Start now (restart it if it's already running, so the new code loads)
Step "Starting Jarvis"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match "jarvis\.py" -or $_.CommandLine -match "jarvis_orb\.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name = 'cmd.exe'" |
    Where-Object { $_.CommandLine -match "jarvis\\start\.bat" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name = 'Jarvis.exe'" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
if ($useTask) { Start-ScheduledTask -TaskName "Jarvis" }
else { Start-Process -FilePath "$Dir\start.bat" -WorkingDirectory $Dir -WindowStyle Minimized }

Write-Host ""
Write-Host "Done. Jarvis is starting (minimized in the taskbar). It updates itself every time it starts," -ForegroundColor Green
Write-Host "at 4 AM, and when you say 'hey jarvis, update yourself'. Say 'hey jarvis, test the computer' to check screen control." -ForegroundColor Green
