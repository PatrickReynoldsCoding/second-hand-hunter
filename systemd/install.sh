#!/usr/bin/env bash
# Installs a daily search (07:30) and an always-on review page for one profile.
# Usage: systemd/install.sh <profile>
set -euo pipefail
profile="${1:?usage: systemd/install.sh <profile>}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
units="$HOME/.config/systemd/user"
mkdir -p "$units"
path="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

cat > "$units/hunter-run@.service" <<UNIT
[Unit]
Description=second-hand-hunter daily search for %i

[Service]
Type=oneshot
WorkingDirectory=$repo
Environment=PATH=$path
ExecStart=/usr/bin/env python3 -m hunter run %i
UNIT

cat > "$units/hunter-run@.timer" <<UNIT
[Unit]
Description=Run second-hand-hunter every morning for %i

[Timer]
OnCalendar=*-*-* 07:30
Persistent=true

[Install]
WantedBy=timers.target
UNIT

cat > "$units/hunter-web@.service" <<UNIT
[Unit]
Description=second-hand-hunter review page for %i

[Service]
WorkingDirectory=$repo
Environment=PATH=$path
ExecStart=/usr/bin/env python3 -m hunter serve %i
Restart=on-failure

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable --now "hunter-run@$profile.timer" "hunter-web@$profile.service"
echo "Daily search at 07:30. Review page: http://localhost:8765"
