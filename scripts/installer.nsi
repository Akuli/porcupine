; Based on a file that pynsist generated

!include 'LogicLib.nsh'
!include 'x64.nsh'

SetCompressor lzma

Unicode true
ManifestDPIAware true

!define MULTIUSER_EXECUTIONLEVEL Highest
!define MULTIUSER_INSTALLMODE_DEFAULT_CURRENTUSER
!define MULTIUSER_MUI
!define MULTIUSER_INSTALLMODE_COMMANDLINE
!define MULTIUSER_INSTALLMODE_INSTDIR "Porcupine"
!define MULTIUSER_INSTALLMODE_FUNCTION correct_prog_files
!include MultiUser.nsh
!include FileFunc.nsh

!include "MUI2.nsh"  ; MUI = Modern UI
!define MUI_ABORTWARNING
!define MUI_ICON "porcupine-logo.ico"
!define MUI_UNICON "porcupine-logo.ico"

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

Section -SETTINGS
  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer
SectionEnd


Var extension

!macro BeginExtensionLoop
  StrCpy $extension ""
  StrCpy $0 0  ; $0 = index into EXTENSIONS
  ${Do}
    StrCpy $1 "${EXTENSIONS}" 1 $0   ; $1 = next char of extension

    ${If} $1 == ","
    ${OrIf} $1 == ""
      ; End of extension, run loop body
!macroend
!macro EndExtensionLoop
      StrCpy $extension ""
    ${Else}
      StrCpy $extension $extension$1
    ${EndIf}

    IntOp $0 $0 + 1
  ${LoopWhile} $1 != ""
!macroend


Section "!Porcupine" sec_app
  SetRegView 64
  SectionIn RO

  ; see #328
  DetailPrint "Deleting $INSTDIR\Python"
  SetDetailsPrint textonly
  RMDir /r "$INSTDIR\Python"
  SetDetailsPrint both

  SetOutPath "$INSTDIR\Python"
  File /r "python-first\*.*"

  ; creates error popup with googlable message if e.g. msvcrt not installed
  ; Should fail as early as possible
  ; https://stackoverflow.com/a/9116125
  DetailPrint "Running a sanity-check with the extracted Python..."
  ClearErrors
  ExecWait '"$INSTDIR\Python\pythonw.exe" -c pass'
  ${If} ${Errors}
    Abort
  ${EndIf}

  SetOutPath "$INSTDIR\Python"
  File /r "python-second\*.*"
  SetOutPath "$INSTDIR\lib"
  File /r "lib\*.*"
  SetOutPath "$INSTDIR"
  File "launch.pyw"

  ; Marker file for per-user install
  ${If} $MultiUser.InstallMode == CurrentUser
    FileOpen $0 "$INSTDIR\_user_install_marker" w
    FileClose $0
  ${EndIf}

  DetailPrint "Creating shortcut..."
  SetOutPath "%HOMEDRIVE%\%HOMEPATH%"  ; This becomes working directory for shortcut
  CreateShortCut "$SMPROGRAMS\Porcupine.lnk" '"$INSTDIR\Python\Porcupine.exe"'
  SetOutPath "$INSTDIR"

  DetailPrint "Byte-compiling Python modules..."
  nsExec::ExecToLog '"$INSTDIR\Python\python" -m compileall -q "$INSTDIR\Python"'

  DetailPrint "Creating uninstaller..."
  WriteUninstaller "$INSTDIR\uninstall.exe"

  DetailPrint "Creating registry keys..."

  ; Opening file with no associated program and user says "Choose from list of installed programs"
  WriteRegStr SHCTX "Software\Classes\Applications\Porcupine.exe\shell\open\command" "" '"$INSTDIR\Python\Porcupine.exe" "%1"'

  ; "Open with" menu when right-click known file type (.py for example)
  WriteRegStr SHCTX "Software\Classes\Porcupine\shell\open\command" "" '"$INSTDIR\Python\Porcupine.exe" "%1"'
  !insertmacro BeginExtensionLoop
    WriteRegStr SHCTX "Software\Classes\$extension\OpenWithProgIds" "Porcupine" ""
  !insertmacro EndExtensionLoop

  ; Uninstalling
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine"  "DisplayName" "Porcupine"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "InstallLocation" "$INSTDIR"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "DisplayIcon" "$INSTDIR\Python\Porcupine.exe"
  WriteRegStr SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "DisplayVersion" "${VERSION}"
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "NoModify" 1
  WriteRegDWORD SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine" "NoRepair" 1
SectionEnd


Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  ${If} ${FileExists} "$INSTDIR\_user_install_marker"
    SetShellVarContext current
  ${EndIf}

  ; Deleting the whole $INSTDIR is not safe https://nsis.sourceforge.io/Reference/RMDir
  DetailPrint "Deleting $INSTDIR\lib and $INSTDIR\Python..."
  SetDetailsPrint textonly
  RMDir /r "$INSTDIR\lib"
  RMDir /r "$INSTDIR\Python"
  SetDetailsPrint both
  Delete "$INSTDIR\_user_install_marker"
  Delete "$INSTDIR\launch.pyw"
  Delete "$INSTDIR\uninstall.exe"
  RMDir "$INSTDIR"  ; no /r, removed only if empty

  Delete "$SMPROGRAMS\Porcupine.lnk"

  DetailPrint "Deleting registry keys..."
  DeleteRegKey SHCTX "Software\Classes\Applications\Porcupine.exe"
  DeleteRegKey SHCTX "Software\Classes\Porcupine"
  DeleteRegKey SHCTX "Software\Microsoft\Windows\CurrentVersion\Uninstall\Porcupine"
  !insertmacro BeginExtensionLoop
    DeleteRegValue SHCTX "Software\Classes\$extension\OpenWithProgIds" "Porcupine"
  !insertmacro EndExtensionLoop
SectionEnd


Function .onInit
  !insertmacro MULTIUSER_INIT
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "\
The Porcupine installer doesn't support 32-bit Windows. \
Please create an issue on GitHub if you need a 32-bit Porcupine installer."
    Quit
  ${EndIf}
FunctionEnd

Function un.onInit
  !insertmacro MULTIUSER_UNINIT
FunctionEnd

Function correct_prog_files
  ; The multiuser machinery doesn't know about the different Program files
  ; folder for 64-bit applications. Override the install dir it set.
  ${If} $MultiUser.InstallMode == AllUsers
    StrCpy $INSTDIR "$PROGRAMFILES64\${MULTIUSER_INSTALLMODE_INSTDIR}"
  ${EndIf}
FunctionEnd
