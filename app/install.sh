#!/usr/bin/env bash
# Adds a "Second-hand Hunter" app icon to the desktop's app list (Linux, GNOME etc.).
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
icons="$HOME/.local/share/icons/hicolor/scalable/apps"
apps="$HOME/.local/share/applications"
mkdir -p "$icons" "$apps"
cp "$repo/app/icon.svg" "$icons/second-hand-hunter.svg"
cat > "$apps/second-hand-hunter.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Second-hand Hunter
Comment=Find second-hand items that match your spec
Exec=$repo/app/second-hand-hunter
Icon=second-hand-hunter
Terminal=false
Categories=Utility;
StartupWMClass=second-hand-hunter
DESKTOP
update-desktop-database "$apps" 2>/dev/null || true
gtk-update-icon-cache -q "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "Installed: look for \"Second-hand Hunter\" in your apps."
