; Inno Setup 6 — instalador a partir de dist\NEXUS (gerado por tools\empacotar_windows.bat). NÃO testado (V3.7).
[Setup]
AppName=NEXUS ENGINEERING LAB
AppVersion=3.7
DefaultDirName={autopf}\NEXUS
DefaultGroupName=NEXUS
OutputBaseFilename=NEXUS_Setup_3.7
[Files]
Source: "..\dist\NEXUS\*"; DestDir: "{app}"; Flags: recursesubdirs
[Icons]
Name: "{group}\NEXUS"; Filename: "{app}\NEXUS.exe"
