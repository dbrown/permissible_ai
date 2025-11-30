#!/bin/bash
# Quick Test of Zero-Trust TEE Deployment

set -e

echo "=========================================="
echo "Testing Zero-Trust TEE Deployment"
echo "=========================================="
echo ""

# Check prerequisites
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "❌ GOOGLE_CLOUD_PROJECT not set"
    exit 1
fi

echo "✓ Project: $GOOGLE_CLOUD_PROJECT"
echo ""

# Build test image
echo "📦 Building immutable TEE image..."
./build_tee_image.sh

# Get image details
IMAGE_NAME=$(gcloud compute images describe-from-family permissible-tee --format="get(name)")
IMAGE_ID=$(gcloud compute images describe "$IMAGE_NAME" --format="get(id)")

echo ""
echo "✓ Image built: $IMAGE_NAME"
echo "✓ Image ID: $IMAGE_ID"
echo ""

# Deploy test instance
echo "🚀 Deploying test TEE instance..."
./deploy_tee_from_image.sh shared-tee-test

# Get internal IP
INTERNAL_IP=$(gcloud compute instances describe shared-tee-test \
    --zone=us-central1-a \
    --format="get(networkInterfaces[0].networkIP)")

echo ""
echo "✓ TEE deployed at: $INTERNAL_IP:8080"
echo ""

# Wait for service to start
echo "⏳ Waiting for TEE service to start..."
sleep 30

# Test health endpoint
echo "🔍 Testing health endpoint..."
gcloud compute ssh shared-tee-test --zone=us-central1-a \
    --command="curl -s http://localhost:8080/health" || true

echo ""
echo ""
echo "=========================================="
echo "✅ Test Complete!"
echo "=========================================="
echo ""
echo "TEE Details:"
echo "  Internal IP: $INTERNAL_IP:8080"
echo "  Image ID: $IMAGE_ID"
echo ""
echo "Next Steps:"
echo "1. Update web server .env:"
echo "   export TEE_ENDPOINT=http://${INTERNAL_IP}:8080"
echo "   export APPROVED_IMAGE_ID=${IMAGE_ID}"
echo ""
echo "2. Test attestation:"
echo "   gcloud compute ssh shared-tee-test --zone=us-central1-a \\"
echo "     --command='curl http://localhost:8080/attestation | jq .'"
echo ""
echo "3. Verify in attestation:"
echo "   - image_id matches: $IMAGE_ID"
echo "   - ssh_disabled: true"
echo "   - immutable_code: true"
echo ""
