#!/usr/bin/env bash
# omarchy-ctl installation script

set -euo pipefail

PLUGIN_DIR="$HOME/.config/omarchy/plugins/MBhalkar.omarchy-ctl"
INSTALL_DIR="$HOME/.local/share/omarchy-ctl"
CONFIG_DIR="$HOME/.config/omarchy-ctl"

mkdir -p "$PLUGIN_DIR" "$INSTALL_DIR" "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/encryption.key" ]; then
    echo "Initializing CTL encryption key..."
    python3 -c "
from omarchy_ctl.storage.crypto import CryptoService
c = CryptoService('$CONFIG_DIR/encryption.key')
c.initialize('default')
print('Key created.')
"
fi

echo "Creating systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/omarchy-ctl.service" << 'EOF'
[Unit]
Description=CTL IPC Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/omarchy-ctl-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

echo "CTL plugin installed."
echo "Enable with: systemctl --user enable --now omarchy-ctl.service"
