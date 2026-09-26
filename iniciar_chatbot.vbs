Option Explicit

Dim shell, fileSystem, projectPath, pythonPath, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectPath = fileSystem.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = projectPath

pythonPath = "python"
If fileSystem.FileExists(projectPath & "\.venv\Scripts\python.exe") Then
    pythonPath = projectPath & "\.venv\Scripts\python.exe"
End If

command = "cmd /c """" & pythonPath & """ manage.py migrate --noinput && """ & pythonPath & """ manage.py seed_knowledge && """ & pythonPath & """ manage.py runserver 127.0.0.1:8000"""
shell.Run command, 0, False
shell.Run "http://127.0.0.1:8000/base-de-conocimiento/chatbot/", 1, False