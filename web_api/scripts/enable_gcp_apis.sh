#!/bin/bash
# Enable required GCP APIs for TEE functionality

PROJECT_ID="permissible-468314"

echo "Enabling required GCP APIs for project: $PROJECT_ID"
echo "================================================"

# List of required APIs
apis=(
  "compute.googleapis.com"           # Compute Engine for VMs
  "storage-component.googleapis.com" # Cloud Storage
  "cloudkms.googleapis.com"          # Cloud KMS for encryption
  "iam.googleapis.com"               # IAM for service accounts
)

for api in "${apis[@]}"; do
  echo "Enabling $api..."
  gcloud services enable "$api" --project="$PROJECT_ID"
done

echo ""
echo "✓ All APIs enabled successfully!"
echo ""
echo "Note: It may take a few minutes for the APIs to become fully available."
