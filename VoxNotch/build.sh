#!/bin/bash
# Build Vox.app - a proper macOS app bundle
set -e

cd "$(dirname "$0")"

echo "Building Vox..."
swift build -c release 2>&1

# Paths
BUILD_DIR=".build/release"
APP_DIR="$BUILD_DIR/Vox.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

# Clean previous bundle
rm -rf "$APP_DIR"

# Create .app bundle structure
mkdir -p "$MACOS"
mkdir -p "$RESOURCES"

# Copy binary (rename to match CFBundleExecutable)
cp "$BUILD_DIR/VoxNotch" "$MACOS/Vox"

# Copy Info.plist
cp Sources/VoxNotch/Info.plist "$CONTENTS/Info.plist"

# Copy app icon
cp Sources/VoxNotch/AppIcon.icns "$RESOURCES/AppIcon.icns"

# Copy menu bar icon
cp Sources/VoxNotch/menubar.png "$RESOURCES/menubar.png"
cp "Sources/VoxNotch/menubar@2x.png" "$RESOURCES/menubar@2x.png"

# Sign ad-hoc (required for CGSSpace private API)
codesign --force --sign - "$APP_DIR" 2>/dev/null || true

echo ""
echo "Built: $APP_DIR"
echo ""
echo "To install:"
echo "  cp -r $APP_DIR /Applications/"
