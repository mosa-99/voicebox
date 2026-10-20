#!/bin/bash
# Build Python server binary for all platforms

set -e

# Determine platform
PLATFORM=$(rustc --print host-tuple 2>/dev/null || echo "unknown")

echo "Building Voicebox sidecars for platform: $PLATFORM"

# Build Python binary
# Resolve PATH to absolute paths before changing directory
export PATH="$(cd "$(dirname "$0")/.." && pwd)/backend/venv/bin:$PATH"
cd backend

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    python -m pip install pyinstaller
fi

# Create binaries directory if it doesn't exist
mkdir -p ../tauri/src-tauri/binaries

copy_sidecar() {
    local name="$1"

    if [ -d "dist/${name}" ]; then
        # --onedir build (macOS server): the app bundles this folder in
        # Contents/Resources (see tauri.macos.conf.json). -a keeps the
        # symlinks PyInstaller creates.
        rm -rf "../tauri/src-tauri/binaries/${name}-onedir"
        cp -a "dist/${name}" "../tauri/src-tauri/binaries/${name}-onedir"
        find "../tauri/src-tauri/binaries/${name}-onedir" -name .DS_Store -delete
        echo "Built ${name}-onedir"
    elif [ -f "dist/${name}" ]; then
        cp "dist/${name}" "../tauri/src-tauri/binaries/${name}-${PLATFORM}"
        chmod +x "../tauri/src-tauri/binaries/${name}-${PLATFORM}"
        echo "Built ${name}-${PLATFORM}"
    elif [ -f "dist/${name}.exe" ]; then
        cp "dist/${name}.exe" "../tauri/src-tauri/binaries/${name}-${PLATFORM}.exe"
        echo "Built ${name}-${PLATFORM}.exe"
    else
        echo "Error: ${name} binary not found in dist/"
        exit 1
    fi
}

# PyInstaller can't replace a --onefile output with a --onedir folder.
rm -rf dist/voicebox-server
python build_binary.py
copy_sidecar voicebox-server

python build_binary.py --shim
copy_sidecar voicebox-mcp

echo "Build complete!"
