# Quick Start: Deploy TEE for Development Testing

## TL;DR

```bash
# 1. Set your GCP project
export GOOGLE_CLOUD_PROJECT="your-project-id"

# 2. Deploy the TEE VM (~3 minutes)
cd /Users/dbrown/Development/permissible/web_api
./scripts/deploy_shared_tee.sh

# 3. Get the external IP
EXTERNAL_IP=$(gcloud compute instances describe shared-tee-dev \
  --zone=us-central1-a \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

# 4. Create firewall rule
MY_IP=$(curl -s ifconfig.me)
gcloud compute firewall-rules create allow-tee-service \
  --network=default \
  --allow=tcp:8080 \
  --source-ranges=$MY_IP/32 \
  --target-tags=tee-service

# 5. Set environment variable
export TEE_SERVICE_ENDPOINT="http://${EXTERNAL_IP}:8080"

# 6. Test attestation
python scripts/test_tee_attestation.py

# 7. Run example workflow
python scripts/examples/example_tee_workflow.py
```

## What You Get

- ✅ **Real Confidential VM** with AMD SEV memory encryption
- ✅ **Attestation Service** generating signed JWT tokens
- ✅ **Health & Status Endpoints** for monitoring
- ✅ **Query Execution Endpoint** (mock execution for now)
- ✅ **Secure Boot + vTPM** enabled
- ✅ **Systemd Service** with auto-restart

## Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/health` | Health check | `curl http://$IP:8080/health` |
| `/attestation` | Get attestation token | `curl http://$IP:8080/attestation` |
| `/status` | Service status | `curl http://$IP:8080/status` |
| `/execute-query` | Execute query | `curl -X POST http://$IP:8080/execute-query -d '{...}'` |

## Verify It's Working

```bash
# Check health
curl http://${EXTERNAL_IP}:8080/health | jq .

# Get attestation
curl http://${EXTERNAL_IP}:8080/attestation | jq .

# Look for these in the attestation response:
# - "confidential_computing": true
# - "secure_boot": true
# - "vtpm_enabled": true
```

## When Done Testing

```bash
# Stop the VM (saves money)
gcloud compute instances stop shared-tee-dev --zone=us-central1-a

# Or delete completely
gcloud compute instances delete shared-tee-dev --zone=us-central1-a --quiet
gcloud compute firewall-rules delete allow-tee-service --quiet
```

## Cost

- **Running 24/7**: ~$73/month
- **8 hours/day**: ~$24/month
- **Stop when not testing**: ~$2/month (storage only)

## Next Steps

See [TEE_DEPLOYMENT_GUIDE.md](./TEE_DEPLOYMENT_GUIDE.md) for:
- Production hardening
- Real query execution
- KMS integration
- GCS bucket setup
- Monitoring and alerting
