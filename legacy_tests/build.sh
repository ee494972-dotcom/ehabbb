#!/bin/bash
# Linux build script for UE4 ESP Detection Tester (requires Windows subsystem)

set -e  # Exit on error

clear

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║     UE4 ESP Detection Tester - Build Script (Linux/WSL)               ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if on Windows/WSL
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Check for WSL
    if grep -qi microsoft /proc/version; then
        echo "[+] WSL detected"
    else
        echo -e "${YELLOW}[!] Warning: This project is designed for Windows${NC}"
        echo "    Memory reading APIs are Windows-specific"
    fi
fi

# Check for required tools
echo "[*] Checking for required tools..."

if ! command -v cmake &> /dev/null; then
    echo -e "${RED}[!] CMake not found!${NC}"
    echo "    Install with: sudo apt-get install cmake"
    exit 1
fi

if ! command -v g++ &> /dev/null && ! command -v clang++ &> /dev/null; then
    echo -e "${RED}[!] C++ compiler not found!${NC}"
    echo "    Install with: sudo apt-get install build-essential"
    exit 1
fi

echo -e "${GREEN}[✓] CMake found$(NC)"
echo -e "${GREEN}[✓] C++ compiler found${NC}"
echo ""

# Create and enter build directory
echo "[+] Creating build directory..."
mkdir -p build
cd build

# Run CMake
echo "[+] Running CMake..."
cmake -DCMAKE_BUILD_TYPE=Release ..

# Build
echo "[+] Building project..."
cmake --build . --config Release -- -j$(nproc)

cd ..

echo ""
echo "╔════════════════════════════════════════════════════════════════════════╗"
echo -e "${GREEN}║  Build completed successfully!                                        ║${NC}"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "[+] Executable location:"
echo "    ./build/UE4ESPDetectionTester"
echo ""
echo "[*] Note: This binary requires Windows APIs."
echo "    If building on Linux, you'll need Windows subsystem support."
echo ""
echo "[*] For Windows, use: build.bat"
echo ""
