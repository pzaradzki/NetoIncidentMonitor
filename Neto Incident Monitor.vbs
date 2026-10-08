Option Explicit
Dim files, shell, folder, python, launcher
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = files.GetParentFolderName(WScript.ScriptFullName)
python = files.BuildPath(folder, ".venv\Scripts\pythonw.exe")
launcher = files.BuildPath(folder, "launcher.pyw")
If Not files.FileExists(python) Then
    MsgBox "Run start.bat once to install the application, then use this shortcut.", 48, "Neto Incident Monitor"
    WScript.Quit 1
End If
If Not files.FileExists(launcher) Then
    MsgBox "Missing launcher.pyw. Keep this shortcut in the application folder.", 16, "Neto Incident Monitor"
    WScript.Quit 1
End If
shell.CurrentDirectory = folder
On Error Resume Next
shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & launcher & Chr(34), 0, False
If Err.Number <> 0 Then
    MsgBox "Cannot start Neto Incident Monitor: " & Err.Description, 16, "Neto Incident Monitor"
    WScript.Quit 1
End If
