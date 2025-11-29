# GCP Setup Guide for Permissible TEE

This guide walks you through setting up Google Cloud Platform for the Permissible TEE (Trusted Execution Environment) functionality.

## Prerequisites

- Google Cloud Platform account
- gcloud CLI installed
- Project billing enabled
- Basic knowledge of GCP

## Step 1: Create GCP Project

```bash
# Set your project ID
export PROJECT_ID="permissible-tee"

# Create project
gcloud projects create $PROJECT_ID --name="Permissible TEE"

# Set as default
gcloud config set project $PROJECT_ID

# Link billing account (replace with your billing account ID)
gcloud billing projects link $PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX
```

## Step 2: Enable Required APIs

```bash
# Enable all required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage-api.googleapis.com
gcloud services enable cloudkms.googleapis.com
gcloud services enable iam.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
```

## Step 3: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create permissible-tee-sa \
    --display-name="Permissible TEE Service Account" \
    --description="Service account for Permissible TEE operations"

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/compute.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/cloudkms.admin"

# Create and download key
gcloud iam service-accounts keys create ~/permissible-tee-key.json \
    --iam-account=permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com

echo "Service account key saved to: ~/permissible-tee-key.json"
```

## Step 4: Verify Confidential Computing Support

Not all GCP zones support Confidential Computing. Verify availability:

```bash
# Check zones with N2D instances (AMD SEV support)
gcloud compute zones list --filter="name:(us-central1-a OR us-central1-b OR europe-west4-a)"

# Recommended zones for Confidential Computing:
# - us-central1-a (Iowa)
# - us-central1-b (Iowa)
# - us-west1-a (Oregon)
# - europe-west4-a (Netherlands)
# - asia-southeast1-a (Singapore)
```

## Step 5: Create Storage Buckets

```bash
# Create bucket for TEE data (encrypted datasets)
gsutil mb -p $PROJECT_ID -l us-central1 gs://${PROJECT_ID}-tee-data

# Create bucket for query results
gsutil mb -p $PROJECT_ID -l us-central1 gs://${PROJECT_ID}-tee-results

# Enable versioning for audit trail
gsutil versioning set on gs://${PROJECT_ID}-tee-data
gsutil versioning set on gs://${PROJECT_ID}-tee-results
```

## Step 6: Configure Application

Add to your `.env` file:

```bash
# GCP Configuration
GOOGLE_CLOUD_PROJECT=permissible-tee
GOOGLE_APPLICATION_CREDENTIALS=/path/to/permissible-tee-key.json
GCP_DEFAULT_ZONE=us-central1-a
GCP_DEFAULT_REGION=us-central1
```

Or set environment variables:

```bash
export GOOGLE_CLOUD_PROJECT="permissible-tee"
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/permissible-tee-key.json"
export GCP_DEFAULT_ZONE="us-central1-a"
export GCP_DEFAULT_REGION="us-central1"
```

## Step 7: Test Configuration

Test your GCP setup with a Python script:

```python
from app.services.gcp_tee import GCPTEEService

# Initialize service
service = GCPTEEService()

# Test connectivity
print(f"Connected to project: {service.project_id}")

# Test bucket access
buckets = list(service.storage_client.list_buckets())
print(f"Found {len(buckets)} buckets")
```

## Step 8: Firewall Rules (Optional)

If you need to access TEE VMs directly:

```bash
# Allow SSH to TEE instances
gcloud compute firewall-rules create allow-ssh-tee \
    --direction=INGRESS \
    --priority=1000 \
    --network=default \
    --action=ALLOW \
    --rules=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=tee-instance

# Note: In production, restrict source-ranges to your IPs
```

## Step 9: Create First TEE

Use the API to create your first TEE:

```bash
curl -X POST http://localhost:5000/api/tee/environments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test TEE",
    "gcp_project_id": "permissible-tee",
    "gcp_zone": "us-central1-a"
  }'
```

## Step 10: Monitor and Verify

```bash
# List all running instances
gcloud compute instances list --filter="labels.confidential-computing=true"

# Check instance details
gcloud compute instances describe INSTANCE_NAME --zone=us-central1-a

# View instance logs
gcloud compute instances get-serial-port-output INSTANCE_NAME --zone=us-central1-a
```

## Cost Estimation

Approximate costs (as of 2024, US regions):

- **N2D Confidential VM** (n2d-standard-4): ~$0.20/hour
- **Cloud Storage**: ~$0.02/GB/month
- **Cloud KMS**: $0.06/key version/month + $0.03/10K operations
- **Network egress**: ~$0.12/GB

**Example monthly cost for 1 TEE:**
- 1 VM running 24/7: ~$150/month
- 100GB storage: ~$2/month
- KMS operations: ~$5/month
- **Total: ~$160/month**

## Security Best Practices

### 1. Service Account Permissions

Principle of least privilege:

```bash
# Instead of admin roles, use specific permissions:
# - compute.instances.create
# - compute.instances.delete
# - storage.buckets.create
# - storage.objects.create
# - cloudkms.cryptoKeys.encrypt
# - cloudkms.cryptoKeys.decrypt
```

### 2. Key Rotation

```bash
# Rotate service account keys regularly (90 days)
# Create new key
gcloud iam service-accounts keys create ~/permissible-tee-key-new.json \
    --iam-account=permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com

# Update application config
# Delete old key
gcloud iam service-accounts keys delete OLD_KEY_ID \
    --iam-account=permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

### 3. VPC Service Controls

For enterprise deployments:

```bash
# Create access policy
gcloud access-context-manager policies create \
    --organization=ORGANIZATION_ID \
    --title="TEE Access Policy"

# Create service perimeter
gcloud access-context-manager perimeters create tee_perimeter \
    --title="TEE Service Perimeter" \
    --resources=projects/$PROJECT_ID \
    --restricted-services=compute.googleapis.com,storage.googleapis.com,cloudkms.googleapis.com
```

### 4. Enable Audit Logging

```bash
# Enable data access logs
gcloud logging sinks create tee-audit-sink \
    gs://${PROJECT_ID}-audit-logs \
    --log-filter='resource.type="gce_instance" AND labels.purpose="trusted-execution-environment"'
```

## Troubleshooting

### Issue: "Permission denied" errors

```bash
# Check service account has correct roles
gcloud projects get-iam-policy $PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com"
```

### Issue: VM creation fails

```bash
# Check quotas
gcloud compute project-info describe --project=$PROJECT_ID

# Request quota increase if needed
# Visit: https://console.cloud.google.com/iam-admin/quotas
```

### Issue: "Confidential Computing not available"

```bash
# Verify zone supports N2D instances
gcloud compute machine-types list --zones=us-central1-a --filter="name:n2d"

# Try different zones if needed
```

### Issue: KMS operations fail

```bash
# Verify KMS API is enabled
gcloud services list --enabled | grep cloudkms

# Check KMS key exists
gcloud kms keys list --location=us-central1 --keyring=tee-keyring
```

## Advanced Configuration

### Custom Machine Types

For specific workloads:

```python
# In your code, specify custom machine type:
service.create_confidential_vm(
    tee_id=1,
    project_id=PROJECT_ID,
    zone="us-central1-a",
    name="custom-tee",
    machine_type="n2d-highmem-8"  # 8 vCPUs, 64GB RAM
)
```

### Regional Deployment

For high availability:

```bash
# Create instances in multiple zones
us-central1-a (primary)
us-central1-b (backup)
us-west1-a (DR)
```

### Cloud Armor Protection

Add DDoS protection:

```bash
# Create security policy
gcloud compute security-policies create tee-policy \
    --description="TEE API protection"

# Add rules
gcloud compute security-policies rules create 1000 \
    --security-policy=tee-policy \
    --expression="origin.region_code == 'US'" \
    --action=allow
```

## Cleanup

To remove all resources:

```bash
# Delete all TEE instances
gcloud compute instances list --filter="labels.purpose=trusted-execution-environment" \
    --format="value(name,zone)" | while read name zone; do
    gcloud compute instances delete $name --zone=$zone --quiet
done

# Delete buckets
gsutil -m rm -r gs://${PROJECT_ID}-tee-data
gsutil -m rm -r gs://${PROJECT_ID}-tee-results

# Delete KMS resources
gcloud kms keyrings list --location=us-central1 --format="value(name)" | while read keyring; do
    gcloud kms keys list --keyring=$(basename $keyring) --location=us-central1 --format="value(name)" | while read key; do
        # KMS keys can't be deleted, only disabled
        gcloud kms keys update $(basename $key) \
            --keyring=$(basename $keyring) \
            --location=us-central1 \
            --state=DISABLED
    done
done

# Delete service account
gcloud iam service-accounts delete \
    permissible-tee-sa@${PROJECT_ID}.iam.gserviceaccount.com --quiet
```

## Support

For GCP-specific issues:
- GCP Documentation: https://cloud.google.com/confidential-computing/docs
- Support: https://cloud.google.com/support

For Permissible issues:
- Email: support@permissible.ai
- GitHub: https://github.com/permissible-ai

## References

- [GCP Confidential Computing](https://cloud.google.com/confidential-computing)
- [AMD SEV Documentation](https://cloud.google.com/compute/confidential-vm/docs/about-cvm)
- [Cloud KMS Best Practices](https://cloud.google.com/kms/docs/best-practices)
- [GCP Security Best Practices](https://cloud.google.com/security/best-practices)
