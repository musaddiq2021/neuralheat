; Compile through scripts/build_installer.ps1. SourceDir is the existing,
; verified PyInstaller onedir release, never the development environment.
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef ReleaseDir
  #error ReleaseDir is required
#endif
#ifndef ArtworkDir
  #error ArtworkDir is required
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E55B462-28F0-4C8A-98C5-E896B4D52631}
AppName=NeuralHeat Studio
AppVersion={#AppVersion}
AppPublisher=NeuralHeat
AppComments=Scientific computing workstation for heat diffusion and neural surrogates
VersionInfoDescription=NeuralHeat Studio Setup
VersionInfoProductName=NeuralHeat Studio
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\NeuralHeat Studio
DefaultGroupName=NeuralHeat Studio
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=NeuralHeat-Studio-Setup
SetupIconFile={#SourceDir}\_internal\scientific_assets\desktop\neuralheat.ico
UninstallDisplayIcon={app}\NeuralHeat Studio.exe
UninstallDisplayName=NeuralHeat Studio
LicenseFile={#SourceDir}\LICENSE.txt
InfoBeforeFile={#ArtworkDir}\installation-notes.txt
#if VER >= EncodeVer(6, 6, 0)
WizardStyle=modern dark
#else
WizardStyle=modern
#endif
WizardResizable=yes
WizardSizePercent=115
WizardImageFile={#ArtworkDir}\wizard.bmp
WizardSmallImageFile={#ArtworkDir}\wizard-small.bmp
WizardImageStretch=yes
DisableWelcomePage=no
DisableDirPage=no
DisableReadyPage=no
SetupLogging=yes
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=1
CompressionThreads=2
LZMAUseSeparateProcess=yes
DiskSpanning=no
CloseApplications=yes
RestartApplications=no
CloseApplicationsFilter=*.exe,*.dll,*.pyd
Uninstallable=yes
UninstallLogging=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ChangesEnvironment=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; The entire onedir tree is required, including scientific assets and CUDA DLLs.
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#ifdef WebView2Installer
Source: "{#WebView2Installer}"; DestName: "NeuralHeat-WebView2-Offline.exe"; Flags: dontcopy noencryption
#endif

[Icons]
Name: "{group}\NeuralHeat Studio"; Filename: "{app}\NeuralHeat Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NeuralHeat Studio.exe"; AppUserModelID: "NeuralHeat.Studio.1"
Name: "{autodesktop}\NeuralHeat Studio"; Filename: "{app}\NeuralHeat Studio.exe"; WorkingDir: "{app}"; IconFilename: "{app}\NeuralHeat Studio.exe"; AppUserModelID: "NeuralHeat.Studio.1"; Tasks: desktopicon

[Run]
Filename: "{app}\NeuralHeat Studio.exe"; Description: "Launch NeuralHeat Studio"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[Messages]
WelcomeLabel2=Install the complete NeuralHeat scientific workstation on your computer.%n%nThe physics engine, trained CNN, scientific reports, and CPU/CUDA runtime are included. No Python, Node.js, npm, or terminal setup is required.%n%nClose NeuralHeat Studio before continuing.
FinishedLabel=NeuralHeat Studio is ready.%n%nOpen it from the Start Menu. Your experiments, logs, caches, and settings are stored in your own AppData folder.
ConfirmUninstall=Remove NeuralHeat Studio and its installed dependencies?%n%nYour personal experiments, checkpoints, logs, and settings in AppData will be kept.

[Code]
const
  WebViewKey = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function RuntimeVersionPresent(RootKey: Integer): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, WebViewKey, 'pv', Version) and
    (Trim(Version) <> '') and (Version <> '0.0.0.0');
end;

function HasWebView2: Boolean;
begin
  { Microsoft documents HKLM's 32-bit view and the current user's key. }
  Result := RuntimeVersionPresent(HKLM32) or RuntimeVersionPresent(HKCU32) or
    RuntimeVersionPresent(HKCU64);
end;

function InitializeSetup: Boolean;
begin
  Result := True;
#ifndef WebView2Installer
  if not HasWebView2 then begin
    SuppressibleMsgBox('Microsoft Edge WebView2 Runtime is required to display NeuralHeat Studio.' + #13#10#13#10 +
      'Install Microsoft''s Evergreen Standalone Installer (x64), then run this installer again.' + #13#10 +
      'The standalone runtime installer also works offline.' + #13#10#13#10 +
      'https://developer.microsoft.com/microsoft-edge/webview2/', mbError, MB_OK, IDOK);
    Result := False;
  end;
#endif
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
#ifdef WebView2Installer
var
  ExitCode: Integer;
#endif
begin
  Result := '';
#ifdef WebView2Installer
  if not HasWebView2 then begin
    WizardForm.StatusLabel.Caption := 'Installing Microsoft Edge WebView2 Runtime...';
    ExtractTemporaryFile('NeuralHeat-WebView2-Offline.exe');
    if not Exec(ExpandConstant('{tmp}\NeuralHeat-WebView2-Offline.exe'), '/silent /install', '',
      SW_HIDE, ewWaitUntilTerminated, ExitCode) then begin
      Result := 'Could not start the bundled offline WebView2 installer.';
      Exit;
    end;
    if (ExitCode <> 0) and (ExitCode <> 3010) then begin
      Result := Format('The WebView2 installer returned error %d. No application files have been installed.', [ExitCode]);
      Exit;
    end;
    if ExitCode = 3010 then NeedsRestart := True;
    if not HasWebView2 then
      Result := 'WebView2 Runtime could not be detected after installation. Restart Windows and try again.';
  end;
#endif
end;

// Intentionally no UninstallDelete entry: never erase user-created scientific data.
