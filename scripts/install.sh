#!/usr/bin/env bash
# omarchy-ctl installation script

set -euo pipefail

PLUGIN_DIR="$HOME/.config/omarchy/plugins/mbhalkar.ctl"
INSTALL_DIR="$HOME/.local/share/omarchy-ctl"
CONFIG_DIR="$HOME/.config/omarchy-ctl"
BIN_DIR="$HOME/.local/bin"
SERVICE_FILE="$HOME/.config/systemd/user/omarchy-ctl.service"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$BIN_DIR" "$HOME/.config/systemd/user"

if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "Error: python-pip is required but not installed." >&2
    echo "Install it with: sudo pacman -S python-pip" >&2
    echo "Then re-run this script." >&2
    exit 1
fi

echo "Installing omarchy-ctl package..."
python3 -m pip install --user --force-reinstall --no-deps -e "$REPO_ROOT"

echo "Initializing CTL encryption key..."
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -c "
from omarchy_ctl.storage.crypto import CryptoService
c = CryptoService('$CONFIG_DIR/encryption.key')
c.initialize('default')
print('Key created.')
"

echo "Creating systemd user service..."
cat > "$SERVICE_FILE" << 'EOF'
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
