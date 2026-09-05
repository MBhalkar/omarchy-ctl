#!/usr/bin/env bash
# omarchy-ctl installation script

set -euo pipefail

PLUGIN_DIR="$HOME/.config/omarchy/plugins/mbhalkar.ctl"
INSTALL_DIR="$HOME/.local/share/omarchy-ctl"
CONFIG_DIR="$HOME/.config/omarchy-ctl"
BIN_DIR="$HOME/.local/bin"
SERVICE_FILE="$HOME/.config/systemd/user/omarchy-ctl.service"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$INSTALL_DIR/venv"

mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$BIN_DIR" "$HOME/.config/systemd/user"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

echo "Installing omarchy-ctl dependencies..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install --no-cache-dir typer aiofiles aiosqlite cryptography keybert scikit-learn python-magic pydantic pydantic-settings structlog aiohttp watchfiles argon2-cffi

echo "Installing omarchy-ctl package..."
"$VENV_DIR/bin/python" -m pip install --no-cache-dir --no-deps "$REPO_ROOT"

echo "Initializing CTL encryption key..."
"$VENV_DIR/bin/python" -c "
from omarchy_ctl.storage.crypto import CryptoService
c = CryptoService('$CONFIG_DIR/encryption.key')
c.initialize('default')
print('Key created.')
"

echo "Creating systemd user service..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=CTL IPC Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/omarchy-ctl-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

ln -sf "$VENV_DIR/bin/omarchy-ctl" "$BIN_DIR/omarchy-ctl"
ln -sf "$VENV_DIR/bin/omarchy-ctl-daemon" "$BIN_DIR/omarchy-ctl-daemon"

echo "CTL plugin installed."
echo "Enable with: systemctl --user enable --now omarchy-ctl.service"
