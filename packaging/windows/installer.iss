; SPDX-License-Identifier: GPL-2.0-or-later
; Inno Setup script: per-user install (no admin rights) of the PyInstaller build.
;   iscc /DAppVersion=0.1.0 packaging\windows\installer.iss
; Output: dist\BasiliskProfiler-<version>-setup.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Basilisk Profiler"
#define AppExe "BasiliskProfiler.exe"

[Setup]
AppId={{6F0B5E3A-3C1D-4D8B-9E52-4B1A7C0D2F91}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=freddirty
AppPublisherURL=https://github.com/freddirty/basilisk-profiler
DefaultDirName={localappdata}\Programs\Basilisk Profiler
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=BasiliskProfiler-{#AppVersion}-setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE
CloseApplications=yes

[Languages]
Name: "hungarian"; MessagesFile: "compiler:Languages\Hungarian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Indítás a Windows-szal"; GroupDescription: "Egyéb:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\BasiliskProfiler\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; same value the tray's "Indítás a Windows-szal" toggle writes (platform/win/autostart.py)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "BasiliskProfiler"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopApp"

[UninstallDelete]
; the user's config in %APPDATA%\basilisk-profiler is kept on purpose
Type: filesandordirs; Name: "{app}"
