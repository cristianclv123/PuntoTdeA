Option Explicit

Dim shell
Set shell = CreateObject("WScript.Shell")
shell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %a /F", 0, True