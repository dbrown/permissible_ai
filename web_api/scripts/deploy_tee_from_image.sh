#!/bin/bash
#
# Deploy TEE from Immutable Image
# 
# Deploys a Confidential VM from a pre-built immutable image.
# This ensures the TEE runs only audited, verified code.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="${1:-shared-tee-prod}"
IMAGE_FAMILY="permissible-tee"
MACHINE_TYPE="n2d-standard-2"
NETWORK="${GCP_NETWORK:-default}"

echo "=========================================="
echo "Deploy TEE from Immutable Image"
echo "=========================================="
echo ""

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT not set${NC}"
    exit 1
fi

# Check if image exists
LATEST_IMAGE=$(gcloud compute images describe-from-family "$IMAGE_FAMILY" \
    --format="get(name)" 2>/dev/null || echo "")

if [ -z "$LATEST_IMAGE" ]; then
    echo -e "${RED}ERROR: No image found in family $IMAGE_FAMILY${NC}"
    echo "Build an image first with: ./build_tee_image.sh"
    exit 1
fi

echo -e "${YELLOW}Using image: $LATEST_IMAGE${NC}"

# Get image ID for attestation
IMAGE_ID=$(gcloud compute images describe "$LATEST_IMAGE" --format="get(id)")
IMAGE_SELFLINK=$(gcloud compute images describe "$LATEST_IMAGE" --format="get(selfLink)")

echo "Image ID: $IMAGE_ID"
echo ""

# Check if instance exists
if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &> /dev/null; then
    echo -e "${YELLOW}Instance $INSTANCE_NAME already exists${NC}"
    read -p "Delete and recreate? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud compute instances delete "$INSTANCE_NAME" --zone="$ZONE" --quiet
    else
        echo "Exiting"
        exit 0
    fi
fi

# Deploy Confidential VM from image
echo -e "${YELLOW}Deploying Confidential VM: $INSTANCE_NAME${NC}"
gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --confidential-compute-type=SEV \
    --maintenance-policy=TERMINATE \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --image="$LATEST_IMAGE" \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-balanced \
    --network="$NETWORK" \
    --no-address \
    --tags=tee-service \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --metadata=block-project-ssh-keys=true

# Wait for VM to boot
echo -e "${YELLOW}Waiting for VM to boot...${NC}"
sleep 20

# Get internal IP
INTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="get(networkInterfaces[0].networkIP)")

echo ""
echo "=========================================="
echo -e "${GREEN}TEE Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Instance Details:"
echo "  Name: $INSTANCE_NAME"
echo "  Zone: $ZONE"
echo "  Internal IP: $INTERNAL_IP"
echo "  Image: $LATEST_IMAGE (ID: $IMAGE_ID)"
echo ""
echo "ZERO-TRUST PROPERTIES:"
echo "  ✓ No external IP (internal access only)"
echo "  ✓ SSH disabled in image"
echo "  ✓ Immutable code (baked into image)"
echo "  ✓ Confidential computing enabled"
echo "  ✓ Secure boot + vTPM + integrity monitoring"
echo ""
echo "Next Steps:"
echo ""
echo "1. Create Cloud NAT for internal VM to reach callback endpoint:"
echo "   gcloud compute routers create nat-router --network=$NETWORK --region=us-central1"
echo "   gcloud compute routers nats create nat-config --router=nat-router --region=us-central1 \\"
echo "     --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges"
echo ""
echo "2. Configure your web server to use internal IP:"
echo "   export TEE_ENDPOINT=http://${INTERNAL_IP}:8080"
echo ""
echo "3. Verify attestation includes image ID:"
echo "   curl http://${INTERNAL_IP}:8080/attestation"
echo ""
echo "Attestation Verification:"
echo "  Clients should verify the attestation token contains:"
echo "    - image_id: $IMAGE_ID"
echo "    - confidential_computing: true"
echo "    - instance_id: (varies per instance)"
echo ""
echo "=========================================="
