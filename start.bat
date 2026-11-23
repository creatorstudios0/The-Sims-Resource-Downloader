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

if /I "%~1"=="--doctor" goto :ConsoleTools
if /I "%~1"=="--audit" goto :ConsoleTools
if /I "%~1"=="--queue" goto :ConsoleTools
if /I "%~1"=="--settings" goto :ConsoleTools
if /I "%~1"=="--console-tools" goto :ConsoleTools
if /I "%~1"=="--help" goto :Usage
if /I "%~1"=="--console" goto :CheckConsoleUpdates
rem Update source ZIPs are no longer applied over a live installation.
rem Old in-place updates could overwrite config.json and personal settings.
rem The unified GitHub release contains both current editions and checksums.
echo CreatorStudios Sims 4 Console v1.1.0
echo Download new versions at:
echo https://github.com/creatorstudios0/The-Sims-Resource-Downloader/releases
echo Existing configuration, queues, sessions, and Downloads are not changed.
goto :LaunchApp

rem ======================================================================
rem  Launch the downloader
rem ======================================================================
:LaunchApp
            )

            echo [2/5] Extracting update...
            if exist "%TEMP%\tsr_update" rmdir /s /q "%TEMP%\tsr_update"
            powershell -NoProfile -Command "Expand-Archive -Path '%TEMP%\tsr_update.zip' -DestinationPath '%TEMP%\tsr_update' -Force" >nul 2>&1
            del "%TEMP%\tsr_update.zip" >nul 2>&1

            echo [3/5] Applying update files...
            for /d %%d in ("%TEMP%\tsr_update\*") do (
                xcopy "%%d\src" "%~dp0src" /E /Y /Q >nul 2>&1
                if exist "%%d\requirements.txt" copy /Y "%%d\requirements.txt" "%~dp0requirements.txt" >nul 2>&1
                if exist "%%d\README.md"        copy /Y "%%d\README.md"        "%~dp0README.md"        >nul 2>&1
                if exist "%%d\CHANGELOG.md"     copy /Y "%%d\CHANGELOG.md"     "%~dp0CHANGELOG.md"     >nul 2>&1
                if exist "%%d\NOTICE.md"        copy /Y "%%d\NOTICE.md"        "%~dp0NOTICE.md"        >nul 2>&1
                if exist "%%d\start.bat"        copy /Y "%%d\start.bat"        "%TEMP%\start_new.bat"  >nul 2>&1
            )
            rmdir /s /q "%TEMP%\tsr_update" >nul 2>&1

            echo [4/5] Installing any new dependencies...
            venv\Scripts\python.exe -m pip install -r requirements.txt --quiet

            echo [5/5] Finalizing update...
            rem Apply new start.bat last via a detached helper so this file isn't locked
            if exist "%TEMP%\start_new.bat" (
                echo @echo off > "%TEMP%\tsr_apply.bat"
                echo timeout /t 1 /nobreak ^>nul >> "%TEMP%\tsr_apply.bat"
                echo copy /Y "%TEMP%\start_new.bat" "%~dp0start.bat" ^>nul 2^>^&1 >> "%TEMP%\tsr_apply.bat"
                echo del "%TEMP%\start_new.bat" >> "%TEMP%\tsr_apply.bat"
                echo del "%TEMP%\tsr_apply.bat" >> "%TEMP%\tsr_apply.bat"
                start /b "" cmd /c "%TEMP%\tsr_apply.bat"
            )

            echo.
            echo ======================================================================
            echo  [SUCCESS] Updated to !LATEST_TAG! successfully!
            echo  The downloader will now launch with the new version.
            echo ======================================================================
            echo.
            rem Persist the new version so the next run won't re-prompt for an update.
            echo !LATEST_TAG!> ".version"
            set "CURRENT_VERSION=!LATEST_TAG!"
        )
        echo.
    ) else (
        echo  You are on the latest version: !CURRENT_VERSION!
        echo.
    )
)

rem ======================================================================
rem  STEP 4: Launch the downloader
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
