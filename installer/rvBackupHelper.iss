; Installer for RV Backup Helper. Built with Inno Setup 6:
;
;     ISCC.exe installer\rvBackupHelper.iss
;
; It expects dist\rvBackupHelper\ to exist - run tools\buildExe.py first.
;
; The wizard is ordered so that everything cheap and reversible happens before
; anything expensive. The hardware check is first and costs nothing: somebody
; with no grabber finds out in the first five seconds rather than after a
; 295 MB download. The core is last, and skippable, because it is the only
; large thing here and only uploading needs it.
;
; Nothing here blocks on missing hardware. Calibrating and generating a sketch
; need no board and no grabber at all, so refusing to install would turn a
; warning into a lie.

#define AppName "RV Backup Helper"
#define AppVersion "0.1.0"
#define Publisher "Charette AI Group, LLC"
#define AppUrl "https://github.com/Charette-AI-Group/rvBackupHelper"
#define ExeName "rvBackupHelper.exe"
#define BundleDir "..\dist\rvBackupHelper"
#define CoreName "arduino:avr"

[Setup]
AppId={{E1C07398-6A2C-4CF8-BADA-56F8E6DAA3E4}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#ExeName}
OutputDir=..\dist
OutputBaseFilename=rvBackupHelperSetup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Per-user, so there is no UAC prompt and no Program Files. The application
; writes to LOCALAPPDATA either way - see appConfig's two roots - but a
; per-user install keeps a hobby tool out of a machine-wide decision.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "avrcore"; Description: "Download the Arduino AVR compiler (about 295 MB). Needed only to upload sketches to the board - the rest of the application works without it."; GroupDescription: "Arduino toolchain:"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Extracted to a temporary folder for the first wizard page, before anything
; is installed. It needs only Get-PnpDevice, so it runs on a machine with
; nothing on it - which is the whole point of asking this first.
Source: "..\tools\checkHardware.ps1"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{code:GetWinget}"; Parameters: "install --id ArduinoSA.CLI --exact --accept-package-agreements --accept-source-agreements"; StatusMsg: "Installing arduino-cli..."; Flags: runhidden waituntilterminated; Check: NeedsArduinoCli
Filename: "{code:GetArduinoCli}"; Parameters: "core install {#CoreName}"; StatusMsg: "Downloading the Arduino AVR compiler (about 295 MB) - this takes a few minutes..."; Flags: runhidden waituntilterminated; Tasks: avrcore; Check: HaveArduinoCli
Filename: "{app}\{#ExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  HardwarePage: TOutputMsgMemoWizardPage;
  HardwareOk: Boolean;
  CachedCliPath: String;
  CliSearched: Boolean;

function FileToString(const Path: String): String;
var
  Lines: TArrayOfString;
  Index: Integer;
begin
  Result := '';
  if not LoadStringsFromFile(Path, Lines) then
    Exit;
  for Index := 0 to GetArrayLength(Lines) - 1 do
    Result := Result + Lines[Index] + #13#10;
end;

{ Runs the hardware check and returns what it printed. The exit code is the
  verdict; the text is for the reader. }
function RunHardwareCheck(var Report: String): Boolean;
var
  ScriptPath, OutputPath, Command: String;
  ResultCode: Integer;
begin
  ExtractTemporaryFile('checkHardware.ps1');
  ScriptPath := ExpandConstant('{tmp}\checkHardware.ps1');
  OutputPath := ExpandConstant('{tmp}\hardware.txt');
  { cmd is the only way to redirect: Exec cannot capture output itself. }
  Command := '/c powershell -NoProfile -ExecutionPolicy Bypass -File "' +
    ScriptPath + '" > "' + OutputPath + '" 2>&1';
  if not Exec(ExpandConstant('{cmd}'), Command, '', SW_HIDE,
              ewWaitUntilTerminated, ResultCode) then
  begin
    Report := 'The hardware check could not be run. It needs Windows PowerShell.';
    Result := False;
    Exit;
  end;
  Report := FileToString(OutputPath);
  if Trim(Report) = '' then
    Report := 'The hardware check produced no output.';
  Result := (ResultCode = 0);
end;

procedure RefreshHardware;
var
  Report: String;
begin
  HardwareOk := RunHardwareCheck(Report);
  HardwarePage.RichEditViewer.Text := Report;
end;

procedure CheckAgainClick(Sender: TObject);
begin
  RefreshHardware;
end;

procedure InitializeWizard;
var
  CheckAgain: TNewButton;
begin
  HardwarePage := CreateOutputMsgMemoPage(
    wpWelcome,
    'Hardware',
    'Is what this needs plugged in?',
    'Plug in the USB video grabber and the Arduino now, then read the report below.' + #13#10 +
    'You can install anyway: calibrating and generating a sketch need neither.',
    '');

  CheckAgain := TNewButton.Create(WizardForm);
  CheckAgain.Parent := HardwarePage.Surface;
  CheckAgain.Caption := 'Check &again';
  CheckAgain.Width := ScaleX(100);
  CheckAgain.Height := ScaleY(23);
  CheckAgain.Left := HardwarePage.SurfaceWidth - CheckAgain.Width;
  CheckAgain.Top := HardwarePage.SurfaceHeight - CheckAgain.Height;
  CheckAgain.Anchors := [akRight, akBottom];
  CheckAgain.OnClick := @CheckAgainClick;

  HardwarePage.RichEditViewer.Height := HardwarePage.SurfaceHeight -
    CheckAgain.Height - ScaleY(8);
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = HardwarePage.ID then
    RefreshHardware;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = HardwarePage.ID) and (not HardwareOk) then
    Result := MsgBox(
      'Some of the hardware was not found.' + #13#10#13#10 +
      'Installing is still fine - calibrating footage and generating a sketch ' +
      'need no board and no grabber. Only capturing and uploading do, and ' +
      'Help > Check Hardware will answer this again at any time.' + #13#10#13#10 +
      'Continue?',
      mbConfirmation, MB_YESNO) = IDYES;
end;

function FindArduinoCli: String;
var
  Candidate: String;
begin
  if CliSearched then
  begin
    Result := CachedCliPath;
    Exit;
  end;
  CliSearched := True;
  CachedCliPath := '';
  Candidate := ExpandConstant('{pf}\Arduino CLI\arduino-cli.exe');
  if FileExists(Candidate) then
    CachedCliPath := Candidate
  else
  begin
    Candidate := ExpandConstant('{localappdata}\Microsoft\WinGet\Links\arduino-cli.exe');
    if FileExists(Candidate) then
      CachedCliPath := Candidate;
  end;
  Result := CachedCliPath;
end;

function NeedsArduinoCli: Boolean;
begin
  Result := FindArduinoCli = '';
end;

{ Re-checked rather than cached: winget may have just installed it. }
function HaveArduinoCli: Boolean;
begin
  CliSearched := False;
  Result := FindArduinoCli <> '';
end;

function GetArduinoCli(Param: String): String;
begin
  Result := FindArduinoCli;
end;

function GetWinget(Param: String): String;
begin
  Result := ExpandConstant('{localappdata}\Microsoft\WindowsApps\winget.exe');
end;
