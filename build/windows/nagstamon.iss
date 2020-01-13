[Setup]
AppName=Nagstamon
AppVerName=Nagstamon {#version}
DefaultDirName={pf}\Nagstamon
DefaultGroupName=Nagstamon
AlwaysUsePersonalGroup=false
ShowLanguageDialog=no
SetupIconFile={#resources}\nagstamon.ico
UsePreviousGroup=false
OutputBaseFilename=Nagstamon-{#version}-win{#arch}_setup
UninstallDisplayIcon={app}\resources\nagstamon.ico
UsePreviousAppDir=false
AppID={{44F7CFFB-4776-4DA4-9930-A07178069517}
UninstallRestartComputer=false
VersionInfoVersion={#version_is}
VersionInfoCopyright=Henri Wahl
VersionInfoProductName=Nagstamon
VersionInfoProductVersion={#version_is}
InternalCompressLevel=max
Compression=lzma
SolidCompression=true
SourceDir={#source}
ArchitecturesAllowed={#archs_allowed}
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
[Icons]
Name: {group}\Nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
Name: {commonstartup}\Nagstamon; Filename: {app}\nagstamon.exe; WorkingDir: {app}; IconFilename: {app}\resources\nagstamon.ico; IconIndex: 0
[Files]
Source: "*"; DestDir: {app}; Flags: recursesubdirs createallsubdirs; BeforeInstall: KillRunningNagstamon()
[Run]
Filename: {app}\{Name}.exe; Description: {cm:Launch,{cm:Name}}; Flags: nowait postinstall skipifsilent
[CustomMessages]
Name=Nagstamon
Launch=Start Nagstamon after finishing installation
[InstallDelete]
Name: "{app}\*Qt*"; Type: filesandordirs
[Code]
procedure KillRunningNagstamon();
var
  ReturnCode: Integer;
begin
    Exec(ExpandConstant('taskkill.exe'), '/f /im nagstamon.exe', '', SW_HIDE, ewWaitUntilTerminated, ReturnCode);
end;