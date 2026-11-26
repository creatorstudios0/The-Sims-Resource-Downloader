@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Use smaller dependencies for console-only commands.
set "REQUIREMENTS_FILE=requirements.txt"
for %%A in (--console --doctor --audit --queue --settings --console-tools) do (
    if /I "%~1"=="%%A" set "REQUIREMENTS_FILE=requirements-console.txt"
)
if /I "%~1"=="--help" goto :Usage



rem ======================================================================
rem  STEP 1: Verify Python is installed
rem ======================================================================
python --version >nul 2>&1
if !errorlevel! neq 0 goto :InstallPython

rem ======================================================================
rem  STEP 2: Verify or repair virtual environment
rem ======================================================================
:ContinueSetup
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [WARNING] The existing virtual environment is broken or was created on
        echo           a different machine. Removing and rebuilding it now...
        echo.
        rmdir /s /q venv
    )
)

if not exist "venv\Scripts\python.exe" (
    echo [Setup 1/2] Creating virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo [Setup 2/2] Installing required dependencies...
    venv\Scripts\python.exe -m pip install -r "%REQUIREMENTS_FILE%" --quiet
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo [SUCCESS] Setup complete!
    echo.
)

if /I "%~1"=="--doctor" goto :ConsoleTools
if /I "%~1"=="--audit" goto :ConsoleTools
if /I "%~1"=="--queue" goto :ConsoleTools
if /I "%~1"=="--settings" goto :ConsoleTools
if /I "%~1"=="--console-tools" goto :ConsoleTools
if /I "%~1"=="--console" goto :CheckConsoleUpdates
if /I "%~1"=="--classic" goto :LaunchClassic
venv\Scripts\python.exe -c "import PySide6.QtWidgets" >nul 2>&1
if errorlevel 1 (
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)
venv\Scripts\python.exe src\desktop_qt.py
if errorlevel 1 pause
exit /b %errorlevel%

:ConsoleTools
rem Preserve literal exclamation marks in game and report paths.
setlocal DisableDelayedExpansion
set "TOOL=%~1"
if /I "%TOOL%"=="--doctor" set "TOOL=doctor"
if /I "%TOOL%"=="--audit" set "TOOL=audit"
if /I "%TOOL%"=="--queue" set "TOOL=queue"
if /I "%TOOL%"=="--settings" set "TOOL=settings"
if /I "%TOOL%"=="--console-tools" set "TOOL=doctor"
rem No SHIFT: pass %2 as the first optional tool argument.
venv\Scripts\python.exe src\console_tools.py %TOOL% %2 %3 %4 %5 %6 %7 %8 %9
exit /b %errorlevel%

:Usage
echo CreatorStudios Sims 4 Suite
echo   start.bat                 Open desktop application
echo   start.bat --console       Run TSR clipboard downloader
echo   start.bat --classic       Open legacy desktop application
echo   start.bat --doctor        Diagnose local settings and folders
echo   start.bat --audit         Inspect duplicate mods ^(read-only^)
echo   start.bat --queue         Show saved download queue
echo   start.bat --settings      Show console preferences
echo   start.bat --help          Show command reference
exit /b 0

:LaunchClassic
venv\Scripts\python.exe src\desktop.py
if errorlevel 1 pause
exit /b %errorlevel%

:CheckConsoleUpdates
rem Existing console preferences and downloads are never overwritten in-place.
echo CreatorStudios Sims 4 Console v1.1.0
echo Releases: https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases
goto :LaunchApp

rem ======================================================================
rem  Launch the console downloader
rem ======================================================================
:LaunchApp
echo Starting CreatorStudios Sims 4 Console...
echo.
venv\Scripts\python.exe src\main.py
echo.
echo The downloader has exited.
pause
exit /b


rem ======================================================================
rem  Python auto-install block
rem ======================================================================
:InstallPython
echo ======================================================================
echo  ERROR: Python is not installed or not found in your system PATH.
echo  The Sims Resource Downloader requires Python to run.
echo ======================================================================
echo.
set /p "py_choice=Would you like to automatically download and install Python now? (Y/N): "
if /i "!py_choice!" neq "Y" goto :NoPython

echo.
echo ======================================================================
echo  AUTOMATIC PYTHON INSTALLATION
echo ======================================================================
echo  We will download and silently install Python 3.11 in the background.
echo  This may take 1-3 minutes depending on your internet speed.
echo  Please do not close this window.
echo ======================================================================
echo.

echo [1/4] Downloading Python 3.11 installer...
curl -# -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Download failed. Check your internet connection and try again.
    pause
    exit /b 1
)

if not exist "%TEMP%\python-installer.exe" (
    echo [ERROR] Installer file was not saved correctly.
    pause
    exit /b 1
)

echo [2/4] Installing Python silently ^(please wait^)...
start /wait "" "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
echo [3/4] Cleaning up installer files...
del "%TEMP%\python-installer.exe" >nul 2>&1

echo [4/4] Reloading PATH and verifying installation...
for /f "tokens=2*" %%A in ('reg query HKCU\Environment /v PATH 2^>nul') do (
    set "USER_PATH=%%B"
)
if defined USER_PATH set "PATH=!USER_PATH!;!PATH!"

python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo.
    echo ======================================================================
    echo  VERIFICATION FAILED
    echo  Python was installed but could not be detected automatically.
    echo  This can happen due to antivirus software or a Windows PATH delay.
    echo  Please CLOSE this window and run start.bat again.
    echo ======================================================================
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo  [SUCCESS] Python installed and verified successfully!
echo  Proceeding with application setup...
echo ======================================================================
echo.
goto :ContinueSetup

:NoPython
echo.
echo Please install Python from https://www.python.org/downloads/
echo Make sure to check "Add python.exe to PATH" during installation.
echo Then run start.bat again.
echo.
pause
exit /b 1
