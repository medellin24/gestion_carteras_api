; Script generado para NeonBlue (Gestión de Carteras)

#define MyAppName "NeonBlue"
#define MyAppVersion "1.0"
#define MyAppPublisher "SIRC"
#define MyAppExeName "NeonBlue.exe"
#define MyIcon "assets\icons\home.ico"

[Setup]
; Identificadores únicos (GUID) - No cambiar si quieres que las actualizaciones funcionen sobre la anterior
AppId={{8B321045-8142-4217-9132-736025211045}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Ubicación del instalador final
OutputDir=dist
OutputBaseFilename=Instalador_NeonBlue_v{#MyAppVersion}
; Ícono del instalador
SetupIconFile={#MyIcon}
; Compresión alta para reducir tamaño
Compression=lzma2
SolidCompression=yes
; Estilo moderno
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copiar todo el contenido de la carpeta onedir generada
Source: "dist\NeonBlue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTA: Asegúrate de que "dist\NeonBlue" exista antes de compilar.

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\home.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\home.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
