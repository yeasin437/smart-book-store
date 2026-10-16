@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo You need to run INSTALL_WINDOWS.bat first.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
 echo.
 echo Bookstore exited with an error. The message above may explain why.
 pause
)
