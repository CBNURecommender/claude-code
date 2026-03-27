#!/bin/bash
set -e

# === Configuration ===
SERVER="jihoon@34.172.56.22"
REMOTE_DIR="/home/jihoon/news-briefing"
SERVICE_NAME="news-briefing"

echo "Deploying News Briefing System..."

# === 1. File transfer (rsync) ===
echo "Syncing files..."
rsync -avz --delete \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude 'briefings/' \
    --exclude 'logs/' \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    --exclude 'venv/' \
    --exclude '.git/' \
    --exclude '.planning/' \
    ./ ${SERVER}:${REMOTE_DIR}/

# === 2. Remote server setup ===
echo "Configuring server..."
ssh ${SERVER} << 'EOF'
    cd /home/jihoon/news-briefing

    # Create required directories
    mkdir -p data briefings logs

    # Create virtualenv if missing
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "Virtualenv created"
    fi

    # Install dependencies
    venv/bin/pip install -r requirements.txt --quiet
    echo "Dependencies installed"

    # Check .env file
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo "WARNING: .env was missing, copied from .env.example."
        echo "  Edit it on the server: nano /home/jihoon/news-briefing/.env"
    fi

    # Register systemd service
    sudo cp deploy/news-briefing.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable ${SERVICE_NAME}

    # Restart service
    sudo systemctl restart ${SERVICE_NAME}
    echo "Service restarted"

    # Show status
    sleep 2
    sudo systemctl status ${SERVICE_NAME} --no-pager -l
EOF

echo ""
echo "Deployment complete!"
echo "Service status: ssh ${SERVER} 'sudo systemctl status ${SERVICE_NAME}'"
echo "View logs: ssh ${SERVER} 'tail -f ${REMOTE_DIR}/logs/service.log'"
