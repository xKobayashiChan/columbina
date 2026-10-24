; X動画変換 のインストーラー (Inno Setup 6)
; build.py から ISCC /DAppVersion=... /DSourceDir=... /DOutputDir=... で呼ばれる。
; 日本語を含むので UTF-8 (BOM 付き) で保存すること。

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\X動画変換"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#define AppName "X動画変換"
#define AppExe "X動画変換.exe"

[Setup]
AppId={{6F2A7C1E-3B8D-4E5A-9C21-7D4F0B8E6A13}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=xKobayashiChan
AppPublisherURL=https://github.com/xKobayashiChan/columbina
AppSupportURL=https://github.com/xKobayashiChan/columbina/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; 管理者権限なしでユーザーのフォルダにインストールする
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=X-video-converter-setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作る (動画をドラッグ&ドロップして使えます)"
Name: "sendto"; Description: "右クリックの「送る」メニューに追加する"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\{#AppName} の使い方"; Filename: "{app}\使い方.txt"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{usersendto}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: sendto

[Run]
Filename: "{app}\使い方.txt"; Description: "使い方を開く"; Flags: postinstall shellexec skipifsilent unchecked
