Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"
!ifndef VERSION
  !error "VERSION is required"
!endif
!ifndef BUNDLE
  !error "BUNDLE is required"
!endif
!ifndef OUTPUT
  !error "OUTPUT is required"
!endif
Name "Codex Auto-Resume"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\Codex Auto-Resume"
InstallDirRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayIcon"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Set up Codex Auto-Resume"
!define MUI_WELCOMEPAGE_TEXT "Install the desktop companion for your Windows account. Setup includes the app and a Start menu shortcut. Python is included.$\r$\n$\r$\nBefore using Auto-Resume, open the Codex desktop app and sign in. Then add the conversations you want to watch."
!define MUI_DIRECTORYPAGE_TEXT_TOP "Choose where to install the dashboard. An upgrade uses this same folder and keeps your saved recovery settings."
!define MUI_FINISHPAGE_TITLE "Codex Auto-Resume is installed"
!define MUI_FINISHPAGE_TEXT "Open Codex Auto-Resume below or find it in Start. Choose Add conversation to arm a chat for recovery."
ShowInstDetails show
!define MUI_FINISHPAGE_RUN "$INSTDIR\codex-auto-resume.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Codex Auto-Resume"
!define MUI_ICON "${ICON}"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${LICENSE}"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Var UpdatePID

Function .onInit
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/UPDATEPID=" $UpdatePID
  IfErrors no_update
  ; Wait until the window and its Python/Tk runtime release their files.
  System::Call 'kernel32::OpenProcess(i 0x00100000, i 0, i $UpdatePID) p .r1'
  StrCmp $1 0 no_update
  System::Call 'kernel32::WaitForSingleObject(p r1, i 60000) i .r2'
  System::Call 'kernel32::CloseHandle(p r1)'
  StrCmp $2 0 no_update
  MessageBox MB_ICONSTOP "Auto-Resume is still running. Close it and try the update again."
  SetErrorLevel 1
  Abort
  no_update:
FunctionEnd

Function .onInstSuccess
  StrCmp $UpdatePID "" +2
  Exec '"$INSTDIR\codex-auto-resume.exe"'
FunctionEnd

Section "Application"
  SetDetailsPrint textonly
  SetOutPath "$INSTDIR"
  DetailPrint "Installing the application and bundled runtime"
  File /r "${BUNDLE}\*"
  IfErrors 0 +3
  SetErrorLevel 1
  Abort "Could not replace Auto-Resume's application files. Close any other copies and run the installer again."
  DetailPrint "Creating shortcuts and registering the uninstaller"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Codex Auto-Resume"
  CreateShortcut "$SMPROGRAMS\Codex Auto-Resume\Codex Auto-Resume.lnk" "$INSTDIR\codex-auto-resume.exe"
  CreateShortcut "$SMPROGRAMS\Codex Auto-Resume\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Codex Auto-Resume.lnk" "$INSTDIR\codex-auto-resume.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayName" "Codex Auto-Resume"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "Publisher" "Manouselis"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayIcon" "$INSTDIR\codex-auto-resume.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "NoRepair" 1
SectionEnd
Section "Uninstall"
  ; Only files owned by this app are removed. Local recovery history survives.
  ; Windows can briefly retain DLL handles after the application exits.
  StrCpy $0 20
  remove_runtime:
  IfFileExists "$INSTDIR\_internal\*.*" 0 runtime_removed
  ClearErrors
  RMDir /r "$INSTDIR\_internal"
  IfErrors 0 runtime_removed
  IntOp $0 $0 - 1
  IntCmp $0 0 runtime_busy
  Sleep 500
  Goto remove_runtime
  runtime_busy:
  SetErrorLevel 1
  Abort "Could not remove the bundled runtime. Close Auto-Resume and try again."
  runtime_removed:
  Delete "$INSTDIR\codex-auto-resume.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\Codex Auto-Resume\Codex Auto-Resume.lnk"
  Delete "$SMPROGRAMS\Codex Auto-Resume\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Codex Auto-Resume"
  Delete "$DESKTOP\Codex Auto-Resume.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume"
SectionEnd
