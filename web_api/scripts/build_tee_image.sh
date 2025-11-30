#!/bin/bash
#
# Build Immutable TEE Image
# 
# Creates a custom GCP image with TEE server code baked in.
# This enables attestation to verify the exact code running in the TEE.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
IMAGE_FAMILY="permissible-tee"
IMAGE_NAME="permissible-tee-$(date +%Y%m%d-%H%M%S)"
BUILD_INSTANCE="tee-image-builder"

echo "=========================================="
echo "TEE Immutable Image Builder"
echo "=========================================="
echo ""

# Validate prerequisites
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT not set${NC}"
    exit 1
fi

echo -e "${YELLOW}Building immutable TEE image...${NC}"
echo "  Project: $PROJECT_ID"
echo "  Image Name: $IMAGE_NAME"
echo "  Image Family: $IMAGE_FAMILY"
echo ""

# Create build script that will run on temporary VM
cat > /tmp/tee-image-setup.sh << 'BUILD_SCRIPT_EOF'
#!/bin/bash
set -e

echo "=== Building TEE Image ==="

# Update system
apt-get update
apt-get install -y python3-pip python3-venv curl jq

# Create TEE runtime directory
mkdir -p /opt/tee-runtime
cd /opt/tee-runtime

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies with pinned versions for reproducibility
pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    gunicorn==21.2.0 \
    pyjwt==2.8.0 \
    cryptography==41.0.7 \
    requests==2.31.0

# Copy TEE server code (will be injected by metadata)
cat > attestation_service.py << 'TEE_SERVER_EOF'
# TEE_SERVER_CODE_PLACEHOLDER
TEE_SERVER_EOF

# Generate RSA keypair for this image
python3 << 'KEYGEN_EOF'
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os

# Generate RSA-4096 keypair
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=4096,
    backend=default_backend()
)

# Save private key
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
with open('/opt/tee-runtime/tee_private_key.pem', 'wb') as f:
    f.write(private_pem)
os.chmod('/opt/tee-runtime/tee_private_key.pem', 0o400)

# Save public key
public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
with open('/opt/tee-runtime/tee_public_key.pem', 'wb') as f:
    f.write(public_pem)

print("RSA keypair generated")
KEYGEN_EOF

# Create systemd service
cat > /etc/systemd/system/tee-server.service << 'SERVICE_EOF'
[Unit]
Description=Permissible TEE Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tee-runtime
Environment="PATH=/opt/tee-runtime/venv/bin"
Environment="PORT=8080"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/tee-runtime/venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 1 --timeout 120 attestation_service:app
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Enable service (will start on boot)
systemctl daemon-reload
systemctl enable tee-server.service

# Disable SSH for zero-trust
systemctl stop sshd
systemctl disable sshd
echo "PermitRootLogin no" >> /etc/ssh/sshd_config
echo "PasswordAuthentication no" >> /etc/ssh/sshd_config

# Compute image hash for attestation
cd /opt/tee-runtime
sha256sum attestation_service.py > /opt/tee-runtime/CODE_HASH.txt
sha256sum /etc/systemd/system/tee-server.service >> /opt/tee-runtime/CODE_HASH.txt

# Create image metadata
cat > /opt/tee-runtime/IMAGE_INFO.json << IMAGE_INFO_EOF
{
  "image_name": "$IMAGE_NAME",
  "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "python_version": "$(python3 --version)",
  "flask_version": "$(pip show flask | grep Version | cut -d' ' -f2)"
}
IMAGE_INFO_EOF

echo "=== TEE Image Build Complete ==="
BUILD_SCRIPT_EOF

# Check if builder instance already exists
if gcloud compute instances describe "$BUILD_INSTANCE" --zone="$ZONE" &> /dev/null; then
    echo -e "${YELLOW}Deleting existing builder instance...${NC}"
    gcloud compute instances delete "$BUILD_INSTANCE" --zone="$ZONE" --quiet
fi

# Read the TEE server code
echo -e "${YELLOW}Reading TEE server code...${NC}"
if [ ! -f "../workers/tee_server.py" ]; then
    echo -e "${RED}ERROR: TEE server code not found at ../workers/tee_server.py${NC}"
    exit 1
fi

# Inject TEE server code into build script
TEE_SERVER_CODE=$(cat ../workers/tee_server.py | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
sed -i.bak "s|# TEE_SERVER_CODE_PLACEHOLDER|$TEE_SERVER_CODE|g" /tmp/tee-image-setup.sh
rm /tmp/tee-image-setup.sh.bak

# Create temporary builder VM
echo -e "${YELLOW}Creating temporary builder VM...${NC}"
gcloud compute instances create "$BUILD_INSTANCE" \
    --zone="$ZONE" \
    --machine-type=n2d-standard-2 \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=20GB \
    --metadata-from-file=startup-script=/tmp/tee-image-setup.sh \
    --scopes=https://www.googleapis.com/auth/cloud-platform

# Wait for setup to complete
echo -e "${YELLOW}Waiting for image setup (60 seconds)...${NC}"
sleep 60

# Stop the instance
echo -e "${YELLOW}Stopping builder instance...${NC}"
gcloud compute instances stop "$BUILD_INSTANCE" --zone="$ZONE"

# Create image from the instance
echo -e "${YELLOW}Creating immutable image...${NC}"
gcloud compute images create "$IMAGE_NAME" \
    --source-disk="$BUILD_INSTANCE" \
    --source-disk-zone="$ZONE" \
    --family="$IMAGE_FAMILY" \
    --description="Permissible TEE Server - Built $(date +%Y-%m-%d)"

# Delete builder instance
echo -e "${YELLOW}Cleaning up builder instance...${NC}"
gcloud compute instances delete "$BUILD_INSTANCE" --zone="$ZONE" --quiet

# Get image details
IMAGE_ID=$(gcloud compute images describe "$IMAGE_NAME" --format="get(id)")
IMAGE_SELFLINK=$(gcloud compute images describe "$IMAGE_NAME" --format="get(selfLink)")

echo ""
echo "=========================================="
echo -e "${GREEN}TEE Image Build Complete!${NC}"
echo "=========================================="
echo ""
echo "Image Details:"
echo "  Name: $IMAGE_NAME"
echo "  Family: $IMAGE_FAMILY"
echo "  ID: $IMAGE_ID"
echo ""
echo "To deploy a TEE instance from this image:"
echo ""
echo "  ./deploy_tee_from_image.sh"
echo ""
echo "Image Properties for Attestation:"
echo "  Image ID: $IMAGE_ID"
echo "  Verify with: gcloud compute images describe $IMAGE_NAME"
echo ""

# Clean up temp file
rm -f /tmp/tee-image-setup.sh

echo "=========================================="
