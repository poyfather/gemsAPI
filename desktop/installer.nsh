; Lapidary Console installer additions (electron-builder includes this file).
; The installer runs once with administrator rights, per machine, like Chrome's.
; It registers Lapidary Helper, the service that later installs and updates
; without asking for administrator rights again, and removes it on uninstall.

!include LogicLib.nsh
!define HELPER_EXE "$INSTDIR\resources\helper\lapidary-helper.exe"

!macro customInit
  ; An update replaces the helper's files: stop it first. Nothing to stop on a first install.
  nsExec::Exec '"$SYSDIR\sc.exe" stop LapidaryHelper'
  Pop $0
  Sleep 2000
!macroend

!macro customInstall
  DetailPrint "Registering Lapidary Helper"
  nsExec::ExecToLog '"${HELPER_EXE}" --startup auto install'
  Pop $0
  ${If} $0 != 0
    ; The old copy may still be marked for deletion; wait, then install or repoint it.
    Sleep 5000
    nsExec::ExecToLog '"${HELPER_EXE}" --startup auto install'
    Pop $0
    ${If} $0 != 0
      nsExec::ExecToLog '"${HELPER_EXE}" --startup auto update'
      Pop $0
    ${EndIf}
  ${EndIf}
  ; Restart it if it ever stops unexpectedly.
  nsExec::ExecToLog '"$SYSDIR\sc.exe" failure LapidaryHelper reset= 86400 actions= restart/60000/restart/60000//0'
  Pop $0
  nsExec::ExecToLog '"$SYSDIR\sc.exe" start LapidaryHelper'
  Pop $0
!macroend

!macro customUnInstall
  DetailPrint "Removing Lapidary Helper"
  nsExec::ExecToLog '"$SYSDIR\sc.exe" stop LapidaryHelper'
  Pop $0
  Sleep 2000
  nsExec::ExecToLog '"${HELPER_EXE}" remove'
  Pop $0
  ${If} $0 != 0
    nsExec::ExecToLog '"$SYSDIR\sc.exe" delete LapidaryHelper'
    Pop $0
  ${EndIf}
!macroend
