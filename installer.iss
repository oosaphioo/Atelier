[Setup]
AppId={{4C44E8E7-1D92-4423-82CC-8E2BE016F490}
AppName=Atelier
AppVersion=0.1.0
AppPublisher=Atelier
DefaultDirName={localappdata}\Programs\Atelier
DefaultGroupName=Atelier
PrivilegesRequired=lowest
OutputDir=output
OutputBaseFilename=Atelier-Installation-Windows
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Atelier.exe
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "dist\Atelier\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Atelier"; Filename: "{app}\Atelier.exe"
Name: "{userdesktop}\Atelier"; Filename: "{app}\Atelier.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Atelier.exe"; Description: "Ouvrir Atelier"; Flags: nowait postinstall skipifsilent
