; Wave installer (Inno Setup 6). Wave is the single app: visualizer and clock widgets, full-screen player,
; Spotify control, screen glow and the lyrics overlay.
;
; Build from desktop\windows:
;   dotnet publish Wave\Wave.csproj -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o out\Wave
;   iscc installer\Wave.iss          ->  out\Wave-Setup.exe
;
; Paths below are relative to this script's folder.

#define AppName "Wave"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
; Same AppId as the earlier "Wave Suite" installer, so installing Wave replaces that entry in Apps & features.
AppId={{5B7E2C64-9D3A-4C1E-8E52-7A0F3D6B1C29}
UsePreviousAppDir=no
UsePreviousGroup=no
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Wave
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user by default (no UAC prompt); the user can choose all users on the first page.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\out
OutputBaseFilename=Wave-Setup
SetupIconFile=icons\Wave.ico
UninstallDisplayIcon={app}\Wave.exe
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startatlogin"; Description: "Start Wave when I sign in"; GroupDescription: "Start at login:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\out\Wave\*"; DestDir: "{app}"; Excludes: "*.pdb,*.xml"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Wave"; Filename: "{app}\Wave.exe"; WorkingDir: "{app}"; Comment: "Music visualizer, clock, screen glow and lyrics"
Name: "{group}\Uninstall Wave"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Wave"; Filename: "{app}\Wave.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
; The same Run value Wave's own "Launch at login" setting uses.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Wave"; ValueData: """{app}\Wave.exe"""; Tasks: startatlogin; Flags: uninsdeletevalue
; Halo and Lyra are part of Wave now: remove the login entries an older "Wave Suite" install created.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Halo"; ValueType: none; Flags: deletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Lyra"; ValueType: none; Flags: deletevalue

[InstallDelete]
; Leftovers of an older "Wave Suite" install (Halo, Lyra and Wave in separate folders, plus its shortcuts).
Type: filesandordirs; Name: "{autopf}\Wave Suite"
Type: filesandordirs; Name: "{autoprograms}\Wave Suite"

[Run]
Filename: "{app}\Wave.exe"; Description: "Open Wave"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Wave lives in the tray, so stop it before its files are removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Wave.exe"; Flags: runhidden; RunOnceId: "StopWave"

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

{ Stop Wave and the old Halo/Lyra tray apps of a "Wave Suite" install so their files can be replaced or removed. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Wave.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Halo.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Lyra.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not WizardSilent()) and (not WebView2Installed()) then
  begin
    if MsgBox('Wave needs the Microsoft Edge WebView2 Runtime, which was not found on this PC.' + #13#10#13#10 +
              'Open the download page now? (Choose the Evergreen Bootstrapper.)',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;
