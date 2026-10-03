@echo off
REM Windows build script for UE4 ESP Detection Tester

setlocal enabledelayedexpansion

cls
echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║     UE4 ESP Detection Tester - Build Script                           ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.

REM Check if Visual Studio is installed
where cl.exe >nul 2>nul
if errorlevel 1 (
    echo [!] Visual Studio C++ compiler not found!
    echo [*] Please ensure you have:
    echo     1. Visual Studio 2019+ installed
    echo     2. C++ tools selected during installation
    echo     3. Run this script from Visual Studio Command Prompt
    echo.
    pause
    exit /b 1
)

echo [*] Compiler found:
cl.exe 2>&1 | findstr /R "Compiler"
echo.

REM Create build directory
if not exist build (
    echo [+] Creating build directory...
    mkdir build
)

cd build

REM Run CMake
echo [+] Running CMake...
cmake -G "Visual Studio 17 2022" ..
if errorlevel 1 (
    echo [!] CMake failed!
    cd ..
    pause
    exit /b 1
)

REM Build project
echo.
echo [+] Building project...
cmake --build . --config Release
if errorlevel 1 (
    echo [!] Build failed!
    cd ..
    pause
    exit /b 1
)

cd ..

echo.
echo ╔════════════════════════════════════════════════════════════════════════╗
echo ║  Build completed successfully!                                        ║
echo ╚════════════════════════════════════════════════════════════════════════╝
echo.
echo [+] Executable location:
echo     build\Release\UE4ESPDetectionTester.exe
echo.
echo [*] Next steps:
echo     1. Configure your game offsets in config.json
echo     2. Use find_offsets.py to locate GWorld address
echo     3. Run: build\Release\UE4ESPDetectionTester.exe
echo.
pause
