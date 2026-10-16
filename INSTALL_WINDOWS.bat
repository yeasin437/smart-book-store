@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo Lumina Bookstore - Windows first-time setup
echo ==============================================
if exist ".venv\Scripts\python.exe" goto install
py -3.13 -m venv .venv
if not errorlevel 1 goto install
py -3.12 -m venv .venv
if not errorlevel 1 goto install
py -3.11 -m venv .venv
if not errorlevel 1 goto install
echo.
echo ERROR: Install 64-bit Python 3.11, 3.12 or 3.13 from python.org.
pause
exit /b 1
:install
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Setup complete! Double-click RUN_WINDOWS.bat to start.
pause
exit /b 0
:error
echo.
echo Installation failed. Check your internet connection and Python installation.
pause
exit /b 1
