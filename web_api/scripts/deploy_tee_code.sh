#!/bin/bash
#
# Deploy updated TEE server code to existing Confidential VM
#
# This script copies tee_server.py and query_executor.py to the running TEE instance
# and restarts the service.
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="shared-tee-dev"

echo "=========================================="
echo "Deploy TEE Server Code"
echo "=========================================="
echo ""

# Validate prerequisites
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT environment variable not set${NC}"
    exit 1
fi

# Check if instance exists
if ! gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" --project="$PROJECT_ID" &> /dev/null; then
    echo -e "${RED}ERROR: Instance $INSTANCE_NAME not found in zone $ZONE${NC}"
    echo "Run deploy_shared_tee.sh first to create the instance"
    exit 1
fi

echo -e "${YELLOW}Copying TEE server files...${NC}"

# Copy tee_server.py
echo "Copying tee_server.py..."
gcloud compute scp \
    ../../workers/tee_server.py \
    "${INSTANCE_NAME}:/opt/tee-runtime/tee_server.py" \
    --zone="$ZONE" \
    --project="$PROJECT_ID"

# Copy query_executor.py
echo "Copying query_executor.py..."
gcloud compute scp \
    ../../workers/query_executor.py \
    "${INSTANCE_NAME}:/opt/tee-runtime/query_executor.py" \
    --zone="$ZONE" \
    --project="$PROJECT_ID"

echo -e "${GREEN}✓ Files copied${NC}"
echo ""

# Update systemd service to use tee_server.py
echo -e "${YELLOW}Updating systemd service...${NC}"
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="sudo bash -c 'cat > /etc/systemd/system/tee-server.service << \"EOF\"
[Unit]
Description=TEE Server with SQLite Query Execution
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tee-runtime
Environment=\"PATH=/opt/tee-runtime/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\"
Environment=\"TEE_PORT=8080\"
Environment=\"TEE_DATA_DIR=/opt/tee-data\"
Environment=\"CONTROL_PLANE_URL=http://YOUR_WEB_API_URL\"
ExecStart=/opt/tee-runtime/venv/bin/python3 /opt/tee-runtime/tee_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
'"

# Create data directory with restricted permissions
echo -e "${YELLOW}Creating secure data directory...${NC}"
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="sudo mkdir -p /opt/tee-data && sudo chmod 700 /opt/tee-data"

# Stop old service if running
echo -e "${YELLOW}Stopping old service...${NC}"
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="sudo systemctl stop tee-attestation.service || true"

# Reload and start new service
echo -e "${YELLOW}Starting TEE server...${NC}"
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="sudo systemctl daemon-reload && sudo systemctl enable tee-server.service && sudo systemctl restart tee-server.service"

# Wait for service
sleep 3

# Check status
echo -e "${YELLOW}Checking service status...${NC}"
gcloud compute ssh "${INSTANCE_NAME}" \
    --zone="$ZONE" \
    --project="$PROJECT_ID" \
    --command="sudo systemctl status tee-server.service --no-pager || true"

echo ""
echo -e "${GREEN}=========================================="
echo "TEE Server Code Deployment Complete"
echo "==========================================${NC}"
echo ""
echo "Service running on port 8080"
echo "Test with: curl http://INSTANCE_IP:8080/health"
echo ""
