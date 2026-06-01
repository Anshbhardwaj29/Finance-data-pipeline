#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=========================================================="
echo " Starting 24/7 Production Deployment of Trading Pipeline "
echo "=========================================================="

# 1. Update system libraries
echo "[+] Updating apt packages..."
sudo apt update -y && sudo apt upgrade -y

# 2. Install Python3, pip and virtualenv
echo "[+] Installing Python3 and Pip..."
sudo apt install python3 python3-pip python3-venv git -y

# 3. Setup Project Directory (If not in /var/www/trading_pipeline)
INSTALL_DIR="/var/www/trading_pipeline"
if [ "$PWD" != "$INSTALL_DIR" ]; then
    echo "[+] Creating installation directory at $INSTALL_DIR..."
    sudo mkdir -p $INSTALL_DIR
    sudo cp -r ./* $INSTALL_DIR/
    cd $INSTALL_DIR
fi

# 4. Install requirements
echo "[+] Installing Python dependencies..."
sudo pip3 install --upgrade pip
sudo pip3 install -r requirements.txt

# 5. Configure Systemd Service for 24/7 Run
echo "[+] Configuring systemd daemon service..."
sudo cp trading_pipeline.service /etc/systemd/system/trading_pipeline.service
sudo systemctl daemon-reload

# 6. Enable and Start the Service
echo "[+] Enabling and starting trading_pipeline service..."
sudo systemctl enable trading_pipeline.service
sudo systemctl restart trading_pipeline.service

# 7. Configure Firewall for Dashboard (Port 8050)
if command -v ufw > /dev/null; then
    echo "[+] Configuring firewall to allow port 8050..."
    sudo ufw allow 8050/tcp || true
fi

echo "=========================================================="
echo "   DEPLOYMENT COMPLETE! Bot is running 24/7 in background "
echo "   Check logs: journalctl -u trading_pipeline -f         "
echo "   Access Dashboard: http://<VPS_IP>:8050                "
echo "=========================================================="
