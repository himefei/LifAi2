' LifAi2 Silent Launcher - Double-click to run without any console flash
' Shows a splash screen while the main app loads

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get the directory where this script is located
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Build paths
venvPythonw = scriptDir & "\.venv\Scripts\pythonw.exe"
splashScript = scriptDir & "\splash.pyw"

' Check if venv exists
If FSO.FileExists(venvPythonw) Then
    ' Run splash screen with venv's pythonw (completely silent)
    WshShell.Run """" & venvPythonw & """ """ & splashScript & """", 0, False
Else
    ' Try alternative venv folder
    venvPythonw = scriptDir & "\venv\Scripts\pythonw.exe"
    If FSO.FileExists(venvPythonw) Then
        WshShell.Run """" & venvPythonw & """ """ & splashScript & """", 0, False
    Else
        ' Fallback to system pythonw
        WshShell.Run "pythonw """ & splashScript & """", 0, False
    End If
End If
