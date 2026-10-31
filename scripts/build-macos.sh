#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
export MACOSX_DEPLOYMENT_TARGET=13.0
export PYINSTALLER_CONFIG_DIR="$PWD/.cache/pyinstaller"
export CLANG_MODULE_CACHE_PATH="$PWD/.cache/clang"
export SWIFT_MODULECACHE_PATH="$PWD/.cache/swift"
mkdir -p .cache/swift .cache/clang build/macos dist
.venv/bin/python -m PyInstaller --noconfirm --clean --onedir --name subvocal-capture \
  --distpath build/macos/worker --workpath build/macos/pyinstaller --specpath build/macos \
  --paths "$PWD" --collect-data subvocal --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on \
  --exclude-module pytest --exclude-module tkinter macos/backend.py
app="$PWD/dist/Subvocal.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp macos/Info.plist "$app/Contents/Info.plist"
rm -rf "$app/Contents/Resources/capture"
ditto build/macos/worker/subvocal-capture "$app/Contents/Resources/capture"
swiftc -swift-version 5 -O -module-cache-path "$SWIFT_MODULECACHE_PATH" \
  -framework AppKit -framework WebKit -framework AVFoundation -framework SwiftUI \
  macos/Sources/RecordingGesture.swift macos/Sources/main.swift -o "$app/Contents/MacOS/Subvocal"
.venv/bin/python scripts/collect-app-licenses.py "$app/Contents/Resources/ThirdPartyLicenses"
codesign --force --deep --sign - "$app"
print "Built $app"
