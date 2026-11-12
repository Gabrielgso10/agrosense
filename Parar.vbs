Option Explicit
Dim shell, fs, pasta, batch
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
pasta = fs.GetParentFolderName(WScript.ScriptFullName)
batch = pasta & "\EXECUTAR_PARAR_OCULTO.bat"
shell.Run "cmd.exe /d /c " & Chr(34) & Chr(34) & batch & Chr(34) & Chr(34), 0, False
