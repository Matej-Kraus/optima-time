; Inno Setup script: per-user install (no admin rights), shortcuts, optional start with Windows.
; Built by CI or scripts\build_windows.ps1:  ISCC.exe /DAppVersion=0.0.1 packaging\optima-time.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6C1E2B6A-4F5D-4C7E-9B1A-0E7D3A2F9C41}
AppName=Optima Time
AppVersion={#AppVersion}
AppPublisher=Optima
DefaultDirName={localappdata}\Programs\OptimaTime
DefaultGroupName=Optima Time
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OptimaTime-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\OptimaTime.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "cs"; MessagesFile: "compiler:Languages\Czech.isl"

[Tasks]
Name: "desktopicon"; Description: "Ikona na ploše"; Flags: checkedonce
Name: "autostart"; Description: "Spouštět Optima Time po přihlášení do Windows"; Flags: unchecked

[Files]
Source: "..\dist\OptimaTime\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Optima Time"; Filename: "{app}\OptimaTime.exe"
Name: "{group}\Kontrola instalace"; Filename: "{cmd}"; Parameters: "/k ""{app}\optima-time.exe"" --self-test"
Name: "{group}\Složka s profily a logy"; Filename: "{userappdata}\OptimaTime"
Name: "{group}\Odinstalovat Optima Time"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Optima Time"; Filename: "{app}\OptimaTime.exe"; Tasks: desktopicon
Name: "{userstartup}\Optima Time"; Filename: "{app}\OptimaTime.exe"; Tasks: autostart

[Run]
Filename: "{app}\OptimaTime.exe"; Description: "Spustit Optima Time"; Flags: nowait postinstall skipifsilent

[Dirs]
Name: "{userappdata}\OptimaTime"
