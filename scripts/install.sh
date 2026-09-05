#!/usr/bin/env bash
# omarchy-ctl installation script

set -euo pipefail

PLUGIN_DIR="$HOME/.config/omarchy/plugins/<username>.ctl"
INSTALL_DIR="$HOME/.local/share/ctl"
CONFIG_DIR="$HOME/.config/ctl"

mkdir -p "$PLUGIN_DIR" "$INSTALL_DIR" "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/encryption.key" ]; then
    echo "Initializing CTL encryption key..."
    python3 -c "
from ctl.storage.crypto import CryptoService
c = CryptoService('$CONFIG_DIR/encryption.key')
c.initialize('default')
print('Key created.')
"
fi

echo "Creating systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ctl.service" << 'EOF'
[Unit]
Description=CTL IPC Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/ctl-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

echo "CTL plugin installed."
echo "Enable with: systemctl --user enable --now ctl.service"
