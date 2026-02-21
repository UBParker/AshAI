#!/usr/bin/env bash
set -euo pipefail

# Build the AshAI Python backend as a standalone binary via PyInstaller,
# then copy it into src-tauri/binaries/ with the correct target triple.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Detect target triple
ARCH="$(uname -m)"
OS="$(uname -s)"

case "$OS" in
    Darwin)
        case "$ARCH" in
            arm64) TARGET="aarch64-apple-darwin" ;;
            x86_64) TARGET="x86_64-apple-darwin" ;;
            *) echo "Unsupported arch: $ARCH"; exit 1 ;;
        esac
        ;;
    Linux)
        case "$ARCH" in
            x86_64) TARGET="x86_64-unknown-linux-gnu" ;;
            aarch64) TARGET="aarch64-unknown-linux-gnu" ;;
            *) echo "Unsupported arch: $ARCH"; exit 1 ;;
        esac
        ;;
    MINGW*|MSYS*|CYGWIN*)
        TARGET="x86_64-pc-windows-msvc"
        ;;
    *)
        echo "Unsupported OS: $OS"
        exit 1
        ;;
esac

echo "Building AshAI sidecar for target: $TARGET"

# Run PyInstaller
pyinstaller pyinstaller.spec --distpath dist/sidecar --clean -y

# Copy binary to Tauri binaries dir
BINARIES_DIR="$PROJECT_ROOT/src-tauri/binaries"
mkdir -p "$BINARIES_DIR"

SRC_BINARY="dist/sidecar/ashai-server"
DEST_BINARY="$BINARIES_DIR/ashai-server-$TARGET"

# On Windows the binary has .exe extension
if [[ "$OS" == MINGW* ]] || [[ "$OS" == MSYS* ]] || [[ "$OS" == CYGWIN* ]]; then
    SRC_BINARY="dist/sidecar/ashai-server.exe"
    DEST_BINARY="$BINARIES_DIR/ashai-server-$TARGET.exe"
fi

cp "$SRC_BINARY" "$DEST_BINARY"
echo "Sidecar binary copied to: $DEST_BINARY"
