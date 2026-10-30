Unicode true
!include "MUI2.nsh"
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
RequestExecutionLevel user
SetCompressor /SOLID lzma
!define MUI_ABORTWARNING
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
Section "Application"
  SetOutPath "$INSTDIR"
  File /r "${BUNDLE}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Codex Auto-Resume"
  CreateShortcut "$SMPROGRAMS\Codex Auto-Resume\Codex Auto-Resume.lnk" "$INSTDIR\codex-auto-resume.exe"
  CreateShortcut "$SMPROGRAMS\Codex Auto-Resume\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\Codex Auto-Resume.lnk" "$INSTDIR\codex-auto-resume.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayName" "Codex Auto-Resume"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "Publisher" "Manouselis"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "DisplayIcon" "$INSTDIR\codex-auto-resume.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "UninstallString" '$"$INSTDIR\Uninstall.exe$"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume" "NoRepair" 1
SectionEnd
Section "Uninstall"
  ; Only files owned by this app are removed. Local recovery history survives.
  RMDir /r "$INSTDIR\_internal"
  Delete "$INSTDIR\codex-auto-resume.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\Codex Auto-Resume\Codex Auto-Resume.lnk"
  Delete "$SMPROGRAMS\Codex Auto-Resume\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Codex Auto-Resume"
  Delete "$DESKTOP\Codex Auto-Resume.lnk"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\CodexAutoResume"
SectionEnd
