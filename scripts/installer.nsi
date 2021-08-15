; Based on a file that pynsist generated

!define BITNESS "64"
!define ARCH_TAG ".amd64"

SetCompressor lzma

Unicode true
ManifestDPIAware true

!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_INSTALLMODE_DEFAULT_CURRENTUSER
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_FUNCTION correct_prog_files
!include MultiUser.nsh
!include FileFunc.nsh

; Modern UI installer stuff
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "porcupine-logo.ico"
!define MUI_UNICON "porcupine-logo.ico"

; UI pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE LICENSE
!insertmacro MULTIUSER_PAGE_INSTALLMODE
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Name "Porcupine ${VERSION}"
OutFile "PorcupineSetup_${VERSION}.exe"
ShowInstDetails show

Var cmdLineInstallDir

Section -SETTINGS
  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer
SectionEnd


Section "!Porcupine" sec_app
  SetRegView 64
  SectionIn RO

  ; Marker file for per-user install
  StrCmp $MultiUser.InstallMode CurrentUser 0 +3
    FileOpen $0 "$INSTDIR\_user_install_marker" w
    FileClose $0

  File "launch.pyw"
  SetOutPath "$INSTDIR\pkgs"
  File /r "pkgs\*.*"
  SetOutPath "$INSTDIR\Python"
  File /r "Python\*.*"
  SetOutPath "$INSTDIR\lib"
  File /r "lib\*.*"
  SetOutPath "$INSTDIR"

  DetailPrint "Creating shortcut..."
  SetOutPath "%HOMEDRIVE%\%HOMEPATH%"  ; This becomes working directory for shortcut
  CreateShortCut "$SMPROGRAMS\Porcupine.lnk" '"$INSTDIR\Python\Porcupine.exe"'
  SetOutPath "$INSTDIR"

  DetailPrint "Byte-compiling Python modules..."
  nsExec::ExecToLog '"$INSTDIR\Python\python" -m compileall -q "$INSTDIR\pkgs"'

  DetailPrint "Creating uninstaller..."
  WriteUninstaller $INSTDIR\uninstall.exe

  DetailPrint "Creating registry keys..."
  WriteRegStr SHCTX "Software\Classes\Applications\Porcupine.exe\shell\open\command" "" '"$INSTDIR\Python\Porcupine.exe" "%1"'
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine"  "DisplayName" "Porcupine"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "DisplayIcon" "$INSTDIR\porcupine-logo.ico"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "DisplayVersion" "${VERSION}"
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "NoModify" 1
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "NoRepair" 1
SectionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  IfFileExists "$INSTDIR\_user_install_marker" 0 +3
    SetShellVarContext current
    Delete "$INSTDIR\_user_install_marker"

  RMDir /r "$INSTDIR"

  Delete "$SMPROGRAMS\Porcupine.lnk"
  DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine"
  DeleteRegKey SHCTX "Software\Classes\Applications\Porcupine.exe"
SectionEnd


Function .onMouseOverSection
    ; Find which section the mouse is over, and set the corresponding description.
    FindWindow $R0 "#32770" "" $HWNDPARENT
    GetDlgItem $R0 $R0 1043 ; description item (must be added to the UI)

    StrCmp $0 ${sec_app} "" +2
      SendMessage $R0 ${WM_SETTEXT} 0 "STR:Porcupine"

FunctionEnd

Function .onInit
  ; Multiuser.nsh breaks /D command line parameter. Parse /INSTDIR instead.
  ; Cribbing from https://nsis-dev.github.io/NSIS-Forums/html/t-299280.html
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} '$0' "/INSTDIR=" $1
  IfErrors +2  ; Error means flag not found
    StrCpy $cmdLineInstallDir $1
  ClearErrors

  !insertmacro MULTIUSER_INIT

  ; If cmd line included /INSTDIR, override the install dir set by MultiUser
  StrCmp $cmdLineInstallDir "" +2
    StrCpy $INSTDIR $cmdLineInstallDir
FunctionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
FunctionEnd

Function correct_prog_files
  ; The multiuser machinery doesn't know about the different Program files
  ; folder for 64-bit applications. Override the install dir it set.
  StrCmp $MultiUser.InstallMode AllUsers 0 +2
    StrCpy $INSTDIR "$PROGRAMFILES64\Porcupine"
FunctionEnd
