; masterpark.iss — instalador Inno Setup do MasterPark
; Exige a saída do PyInstaller em ..\dist\MasterPark\ (ver scripts\build_exe.ps1)

#define MyAppName "MasterPark"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MasterPark Sistemas"
#define MyAppExeName "MasterPark.exe"
#define MyAppAssocName MyAppName + " File"

[Setup]
AppId={{C7F7B5EC-8A42-4F0E-8B1C-4D2A3B9E6F10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=MasterParkSetup
SetupIconFile=..\assets\masterpark.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\MasterPark\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; dados do usuário ficam em %LOCALAPPDATA%\MasterPark (não são removidos pelo desinstalador)