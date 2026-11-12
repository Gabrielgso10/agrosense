Option Explicit
Dim shell, fs, pasta, batch, comando
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
pasta = fs.GetParentFolderName(WScript.ScriptFullName)
batch = pasta & "\EXECUTAR_AGROSENSE_OCULTO.bat"
If Not fs.FileExists(batch) Then
  MsgBox "Arquivo EXECUTAR_AGROSENSE_OCULTO.bat nao encontrado na pasta do AgroSense.", 16, "AgroSense"
  WScript.Quit 1
End If
comando = "cmd.exe /d /c " & Chr(34) & Chr(34) & batch & Chr(34) & Chr(34)
shell.Run comando, 0, False
