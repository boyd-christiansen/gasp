#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
app="$PWD/dist/Subvocal.app"
[[ -x "$app/Contents/MacOS/Subvocal" ]] || { print 'Build the app with ./scripts/build-macos.sh first.'; exit 1; }
target="$HOME/Applications/Subvocal.app"
if [[ -e "$target" ]]; then
  identifier=$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$target/Contents/Info.plist")
  [[ "$identifier" == com.boydchristiansen.desktop-subvocal ]] || { print 'A different application already uses this path.'; exit 1; }
fi
mkdir -p "$HOME/Applications"
ditto "$app" "$target"
codesign --verify --deep --strict "$target"
print "Installed $target"
