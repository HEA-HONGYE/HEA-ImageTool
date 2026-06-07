#define MyAppName "HEA"
#define MyAppVersion "4.1.7"
#define MyAppPublisher "HEA-HONGYE"
#define MyAppURL "https://github.com/HEA-HONGYE/HEA-ImageTool"
#define MyAppExeName "HEA.exe"

[Setup]
AppId={{2C6A1446-4063-40B9-BC1C-5B0DDE5F4229}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\release
OutputBaseFilename=HEA-ImageTool-{#MyAppVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: unchecked

[Files]
Source: "..\dist\HEA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "cleanup_user_data.ps1"; DestDir: "{app}\installer"; Flags: ignoreversion

[Icons]
Name: "{group}\HEA"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\一键清理 HEA 用户数据"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\cleanup_user_data.ps1"""; WorkingDir: "{app}"; Comment: "清理 HEA 用户配置、缓存和注册表项"
Name: "{group}\卸载 HEA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\HEA"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 HEA"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\cleanup_user_data.ps1"" -Silent"; Flags: runhidden; RunOnceId: "HEAUserDataCleanup"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\temp"
Type: filesandordirs; Name: "{app}\reports"
Type: filesandordirs; Name: "{app}\output"
Type: filesandordirs; Name: "{app}"
