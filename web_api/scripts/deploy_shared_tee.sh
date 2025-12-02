#!/bin/bash
#
# Deploy Shared TEE Infrastructure
# 
# This script creates a GCP Confidential VM for testing attestation
# and secure query execution in a development environment.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="shared-tee-dev"
MACHINE_TYPE="n2d-standard-2"  # Smallest AMD instance supporting SEV (2 vCPU, 8GB RAM)
SERVICE_ACCOUNT="${TEE_SERVICE_ACCOUNT:-}"
NETWORK="${GCP_NETWORK:-default}"

echo "=========================================="
echo "Shared TEE Deployment Script"
echo "=========================================="
echo ""

# Validate prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT environment variable not set${NC}"
    echo "Set it with: export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud CLI not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verify authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${RED}ERROR: Not authenticated with gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Set project
echo -e "${YELLOW}Setting project to: ${PROJECT_ID}${NC}"
gcloud config set project "$PROJECT_ID"
echo ""

# Enable required APIs
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable compute.googleapis.com
gcloud services enable cloudkms.googleapis.com
gcloud services enable storage-api.googleapis.com
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Check if instance already exists
if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &> /dev/null; then
    echo -e "${YELLOW}Instance $INSTANCE_NAME already exists${NC}"
    read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deleting existing instance...${NC}"
        gcloud compute instances delete "$INSTANCE_NAME" --zone="$ZONE" --quiet
        echo -e "${GREEN}✓ Instance deleted${NC}"
    else
        echo "Exiting without changes"
        exit 0
    fi
fi

# Create startup script
echo -e "${YELLOW}Creating TEE startup script...${NC}"

# First, prepare the code files to embed
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKERS_DIR="$(cd "$SCRIPT_DIR/../../workers" && pwd)"

if [ ! -f "$WORKERS_DIR/tee_server.py" ]; then
    echo -e "${RED}ERROR: tee_server.py not found at $WORKERS_DIR${NC}"
    exit 1
fi

if [ ! -f "$WORKERS_DIR/query_executor.py" ]; then
    echo -e "${RED}ERROR: query_executor.py not found at $WORKERS_DIR${NC}"
    exit 1
fi

# Base64 encode the Python files for safe embedding
TEE_SERVER_B64=$(base64 < "$WORKERS_DIR/tee_server.py")
QUERY_EXECUTOR_B64=$(base64 < "$WORKERS_DIR/query_executor.py")

cat > /tmp/tee-startup.sh << 'STARTUP_SCRIPT_EOF'
#!/bin/bash
set -e

echo "=== TEE Runtime Setup ==="
echo "Starting at: $(date)"

# Update system
apt-get update
apt-get install -y python3-pip python3-venv curl jq

# Create TEE runtime directory
mkdir -p /opt/tee-runtime
mkdir -p /opt/tee-data
chmod 700 /opt/tee-data

cd /opt/tee-runtime

# Write Python files from base64-encoded content
STARTUP_SCRIPT_EOF

# Append base64-encoded content and decode commands
cat >> /tmp/tee-startup.sh << STARTUP_SCRIPT_EOF
cat > tee_server.py.b64 << 'TEE_SERVER_B64_EOF'
$TEE_SERVER_B64
TEE_SERVER_B64_EOF

cat > query_executor.py.b64 << 'QUERY_EXECUTOR_B64_EOF'
$QUERY_EXECUTOR_B64
QUERY_EXECUTOR_B64_EOF

base64 -d tee_server.py.b64 > tee_server.py
base64 -d query_executor.py.b64 > query_executor.py
rm tee_server.py.b64 query_executor.py.b64

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install flask flask-cors cryptography pyjwt requests

# Create secure data directory
mkdir -p /opt/tee-data
chmod 700 /opt/tee-data

# Create systemd service placeholder (will be updated after code copy)
cat > /etc/systemd/system/tee-server.service << 'SERVICE_EOF'
[Unit]
Description=TEE Server with SQLite Query Execution
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tee-runtime
Environment="PATH=/opt/tee-runtime/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="TEE_PORT=8080"
Environment="TEE_DATA_DIR=/opt/tee-data"
Environment="CONTROL_PLANE_URL=http://localhost:5000"
ExecStart=/opt/tee-runtime/venv/bin/python3 /opt/tee-runtime/tee_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Enable and start service
systemctl daemon-reload
systemctl enable tee-server.service
systemctl start tee-server.service

echo "✓ TEE server started"

# Disable SSH for security (TEE should not allow remote shell access)
systemctl stop ssh
systemctl disable ssh
echo "SSH disabled for TEE security" > /etc/ssh/sshd_not_to_be_run

echo "=== TEE Runtime Setup Complete ==="
echo "Completed at: \$(date)"
STARTUP_SCRIPT_EOF

echo -e "${GREEN}✓ Startup script created${NC}"
echo ""

# Create the Confidential VM
echo -e "${YELLOW}Creating Confidential VM: ${INSTANCE_NAME}${NC}"
echo "  Project: $PROJECT_ID"
echo "  Zone: $ZONE"
echo "  Machine Type: $MACHINE_TYPE"
echo ""

SERVICE_ACCOUNT_FLAG=""
if [ -n "$SERVICE_ACCOUNT" ]; then
    SERVICE_ACCOUNT_FLAG="--service-account=$SERVICE_ACCOUNT"
fi

gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --confidential-compute-type=SEV \
    --maintenance-policy=TERMINATE \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-balanced \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --network="$NETWORK" \
    --tags=tee-service,http-server,https-server \
    --metadata=block-project-ssh-keys=TRUE,enable-oslogin=FALSE \
    --metadata-from-file=startup-script=/tmp/tee-startup.sh \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    $SERVICE_ACCOUNT_FLAG

echo ""
echo -e "${GREEN}✓ VM created successfully${NC}"
echo ""

# Wait for startup script to complete
echo -e "${YELLOW}Waiting for startup script to complete (2-3 minutes)...${NC}"
echo "The startup script will:"
echo "  - Install dependencies"
echo "  - Deploy TEE code (embedded in startup script)"
echo "  - Start the service"
echo "  - Disable SSH for security"
echo ""
echo "Waiting 120 seconds..."
sleep 120

echo ""

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Instance Details:"
echo "  Name: $INSTANCE_NAME"
echo "  Zone: $ZONE"
echo "  External IP: $EXTERNAL_IP"
echo ""
echo "Next Steps:"
echo ""
echo "1. Create firewall rule for TEE service:"
echo "   gcloud compute firewall-rules create allow-tee-service \\"
echo "     --network=$NETWORK \\"
echo "     --allow=tcp:8080 \\"
echo "     --source-ranges=YOUR_IP/32 \\"
echo "     --target-tags=tee-service"
echo ""
echo "2. Set environment variable in your Flask app:"
echo "   export TEE_SERVICE_ENDPOINT=http://${EXTERNAL_IP}:8080"
echo ""
echo "3. Test the service endpoint:"
echo "   curl http://${EXTERNAL_IP}:8080/health"
echo ""
echo "4. View startup script logs (SSH will be disabled after setup):"
echo "   gcloud compute instances get-serial-port-output $INSTANCE_NAME --zone=$ZONE"
echo ""
echo "Note: SSH is disabled on the TEE for security. Use serial console for debugging."
echo ""
echo "5. Verify confidential computing:"
echo "   gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE \\"
echo "     --format='get(confidentialInstanceConfig)'"
echo ""

# Clean up temp file
rm -f /tmp/tee-startup.sh

echo "=========================================="
