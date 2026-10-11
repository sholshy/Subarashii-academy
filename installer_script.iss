[Setup]
AppName=YGO Tools by Sholshy
AppVersion=1.1.0
DefaultDirName={pf}\YGO Tools
DefaultGroupName=YGO Tools
OutputDir=.\Output
OutputBaseFilename=YGOTools_Installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Files]
; Asegúrate de que la ruta apunte a la carpeta donde PyInstaller generó el ejecutable y sus archivos
Source: "dist\YGO_Tools\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YGO Tools"; Filename: "{app}\YGO_Tools.exe"
Name: "{commondesktop}\YGO Tools"; Filename: "{app}\YGO_Tools.exe"

[Run]
Filename: "{app}\YGO_Tools.exe"; Description: "Ejecutar YGO Tools"; Flags: nowait postinstall skipifsilent
