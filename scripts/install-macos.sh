#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
app="$PWD/dist/Gasp.app"
[[ -x "$app/Contents/MacOS/Gasp" ]] || { print 'Build the app with ./scripts/build-macos.sh first.'; exit 1; }
target="$HOME/Applications/Gasp.app"
if [[ -e "$target" ]]; then
  identifier=$(/usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' "$target/Contents/Info.plist")
  [[ "$identifier" == com.boydchristiansen.gasp ]] || { print 'A different application already uses this path.'; exit 1; }
fi
mkdir -p "$HOME/Applications"
ditto "$app" "$target"
codesign --verify --deep --strict "$target"
print "Installed $target"
