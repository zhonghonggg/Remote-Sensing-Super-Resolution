[Setup]
AppId={{5A21D170-091A-47C2-A1C9-E3CC408B2BD1}
AppName=GeoTIFF AI Super Resolution
AppVersion=1.0.0
AppPublisher=GeoSR Project
DefaultDirName={localappdata}\Programs\GeoSR
DefaultGroupName=GeoTIFF AI Super Resolution
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=GeoSR-1.0.0-Windows-x64-Setup
SetupIconFile=assets\geosr.ico
UninstallDisplayIcon={app}\GeoSR.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "dist\GeoSR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\GeoTIFF AI Super Resolution"; Filename: "{app}\GeoSR.exe"; IconFilename: "{app}\GeoSR.exe"
Name: "{autodesktop}\GeoTIFF AI Super Resolution"; Filename: "{app}\GeoSR.exe"; IconFilename: "{app}\GeoSR.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\GeoSR.exe"; Description: "Launch GeoTIFF AI Super Resolution"; Flags: nowait postinstall skipifsilent
