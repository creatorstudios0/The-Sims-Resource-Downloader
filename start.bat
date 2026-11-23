@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"



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
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo [SUCCESS] Setup complete!
    echo.
)

if /I "%~1"=="--console" goto :LaunchConsole
if /I "%~1"=="--classic" goto :LaunchClassic
venv\Scripts\python.exe -c "import PySide6.QtWidgets" >nul 2>&1
if errorlevel 1 (
    venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)
venv\Scripts\python.exe src\desktop_qt.py
if errorlevel 1 pause
exit /b %errorlevel%

:LaunchClassic
venv\Scripts\python.exe src\desktop.py
if errorlevel 1 pause
exit /b %errorlevel%

:LaunchConsole
venv\Scripts\python.exe src\main.py
if errorlevel 1 pause
exit /b %errorlevel%

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
