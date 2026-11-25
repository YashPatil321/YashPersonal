; Wave Suite installer (Inno Setup 6). Installs Halo, Lyra and Wave for Windows.
;
; Build from desktop\windows after publishing the three apps:
;   dotnet publish Halo\Halo.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Halo
;   dotnet publish Lyra\Lyra.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Lyra
;   dotnet publish Wave\Wave.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Wave
;   iscc installer\WaveSuite.iss          ->  out\WaveSuite-Setup.exe
;
; Paths below are relative to this script's folder.

#define SuiteName "Wave Suite"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{5B7E2C64-9D3A-4C1E-8E52-7A0F3D6B1C29}
AppName={#SuiteName}
AppVersion={#AppVersion}
AppVerName={#SuiteName} {#AppVersion}
AppPublisher=Halo + Lyra + Wave
DefaultDirName={autopf}\{#SuiteName}
DefaultGroupName={#SuiteName}
DisableProgramGroupPage=yes
; Per-user by default (no UAC prompt); the user can choose all users on the first page.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\out
OutputBaseFilename=WaveSuite-Setup
SetupIconFile=icons\Wave.ico
UninstallDisplayIcon={app}\Wave\Wave.exe
UninstallDisplayName={#SuiteName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startwave"; Description: "Start Wave when I sign in"; GroupDescription: "Start at login:"
Name: "starthalo"; Description: "Start Halo when I sign in"; GroupDescription: "Start at login:"; Flags: unchecked
Name: "startlyra"; Description: "Start Lyra when I sign in"; GroupDescription: "Start at login:"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop shortcut for Wave"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\out\Halo\*"; DestDir: "{app}\Halo"; Excludes: "*.pdb,*.xml"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\out\Lyra\*"; DestDir: "{app}\Lyra"; Excludes: "*.pdb,*.xml"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\out\Wave\*"; DestDir: "{app}\Wave"; Excludes: "*.pdb,*.xml"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Wave"; Filename: "{app}\Wave\Wave.exe"; WorkingDir: "{app}\Wave"; Comment: "Music visualizer, desktop clock and full-screen player"
Name: "{group}\Halo"; Filename: "{app}\Halo\Halo.exe"; WorkingDir: "{app}\Halo"; Comment: "A soft glow around your screen that follows the music"
Name: "{group}\Lyra"; Filename: "{app}\Lyra\Lyra.exe"; WorkingDir: "{app}\Lyra"; Comment: "Word-by-word synced lyrics over your screen"
Name: "{group}\Uninstall {#SuiteName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Wave"; Filename: "{app}\Wave\Wave.exe"; WorkingDir: "{app}\Wave"; Tasks: desktopicon

[Registry]
; The same Run values the apps' own "Launch at login" switches use, so the two stay in sync.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Wave"; ValueData: """{app}\Wave\Wave.exe"""; Tasks: startwave; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Halo"; ValueData: """{app}\Halo\Halo.exe"""; Tasks: starthalo; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Lyra"; ValueData: """{app}\Lyra\Lyra.exe"""; Tasks: startlyra; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Wave\Wave.exe"; Description: "Open Wave"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Halo\Halo.exe"; Description: "Start Halo"; Flags: nowait postinstall skipifsilent unchecked
Filename: "{app}\Lyra\Lyra.exe"; Description: "Start Lyra"; Flags: nowait postinstall skipifsilent unchecked

[UninstallRun]
; The apps live in the tray, so stop them before their files are removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Wave.exe"; Flags: runhidden; RunOnceId: "StopWave"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Halo.exe"; Flags: runhidden; RunOnceId: "StopHalo"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Lyra.exe"; Flags: runhidden; RunOnceId: "StopLyra"

[Code]
const
  WebView2ClientKey = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2ClientKeyWow = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(const Root: Integer; const Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ The Evergreen WebView2 runtime ships with Windows 10 and 11; Wave needs it. }
function WebView2Installed(): Boolean;
begin
  Result := HasVersion(HKLM, WebView2ClientKeyWow) or HasVersion(HKLM, WebView2ClientKey) or HasVersion(HKCU, WebView2ClientKey);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent()) and (not WebView2Installed()) then
  begin
    if MsgBox('Wave needs the Microsoft Edge WebView2 Runtime, which was not found on this PC.' + #13#10#13#10 +
              'Open the download page now? (Choose the Evergreen Bootstrapper.) Halo and Lyra work without it.',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;
