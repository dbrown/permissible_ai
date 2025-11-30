# Zero-Trust TEE: Complete Solution

## Executive Summary

**Problem:** Original TEE deployment used startup scripts that could be modified by administrators, violating zero-trust principles.

**Solution:** Immutable image-based deployment where code is baked into GCP images and cryptographically verified by clients before data upload.

## Quick Start

```bash
# 1. Build immutable image
cd /Users/dbrown/Development/permissible/web_api/scripts
./build_tee_image.sh

# 2. Deploy TEE from image
./deploy_tee_from_image.sh shared-tee-prod

# 3. Get TEE internal IP
gcloud compute instances describe shared-tee-prod \
    --zone=us-central1-a \
    --format="get(networkInterfaces[0].networkIP)"

# 4. Update web server
export TEE_ENDPOINT=http://INTERNAL_IP:8080
export APPROVED_IMAGE_ID=<from step 1>
```

## Files Created

### Deployment Scripts
- **`scripts/build_tee_image.sh`** - Builds immutable GCP image with TEE code baked in
- **`scripts/deploy_tee_from_image.sh`** - Deploys Confidential VM from immutable image
- **`scripts/test_tee_deployment.sh`** - Tests complete deployment workflow

### Documentation
- **`docs/ZERO_TRUST_TEE_DEPLOYMENT.md`** - Complete security architecture and deployment guide
- **`docs/TEE_DEPLOYMENT_IMPLEMENTATION.md`** - Implementation status and comparison

### Updated Code
- **`workers/tee_server.py`** - Enhanced to load keys from image and report security properties

## Security Architecture

```
┌─────────────────────────────────────────────────────┐
│              Zero-Trust TEE Architecture             │
└─────────────────────────────────────────────────────┘

1. BUILD (One Time)
   ┌──────────────────┐
   │ Audited Source   │ ──> git commit abc123
   │ workers/         │
   │ tee_server.py    │
   └──────────────────┘
          │
          ▼
   [build_tee_image.sh]
          │
          ├─> Install pinned dependencies
          ├─> Copy TEE server code
          ├─> Generate RSA-4096 keys
          ├─> Compute SHA-256 hashes
          ├─> Disable SSH
          └─> Create systemd service
          │
          ▼
   ┌──────────────────────────────┐
   │ Immutable GCP Image          │
   │ • Image ID: 123456789        │ ◄─ Publish this
   │ • Code Hash: sha256:abc...   │ ◄─ Clients verify this
   │ • RSA Keys baked in          │
   │ • SSH disabled               │
   └──────────────────────────────┘

2. DEPLOY (Repeatable)
   [deploy_tee_from_image.sh]
          │
          ├─> Use approved image only
          ├─> No external IP
          ├─> No SSH keys
          ├─> Confidential computing ON
          └─> Secure boot + vTPM ON
          │
          ▼
   ┌──────────────────────────────┐
   │ Confidential VM              │
   │ • Running immutable code     │
   │ • Cannot be modified         │
   │ • Memory encrypted (SEV-SNP) │
   │ • Internal network only      │
   └──────────────────────────────┘

3. VERIFY (Every Upload)
   Client Browser
          │
          ▼
   GET /attestation
          │
          ▼
   ┌──────────────────────────────┐
   │ {                            │
   │   "image_id": "123456789",   │ ◄─ Verify matches approved
   │   "code_hash": "sha256:...", │ ◄─ Verify matches audit
   │   "public_key": "...",        │ ◄─ Use for encryption
   │   "ssh_disabled": true,       │ ◄─ Verify immutable
   │   "signature": "..."          │ ◄─ Verify TEE signature
   │ }                            │
   └──────────────────────────────┘
          │
          ├─> ✅ All checks pass?
          └─> Upload encrypted data
```

## Zero-Trust Properties

| Property | Implementation | Verification |
|----------|---------------|--------------|
| **Immutable Code** | Code baked into image at build time | Client checks `code_measurement` in attestation |
| **No SSH Access** | SSH disabled in image, cannot be re-enabled | Client checks `ssh_disabled: true` in attestation |
| **Verified Image** | Each image has unique ID | Client checks `image_id` matches approved value |
| **Memory Isolation** | AMD SEV-SNP encrypts all VM memory | Enabled via `--confidential-compute-type=SEV` |
| **Measured Boot** | vTPM verifies boot chain integrity | Enabled via `--shielded-vtpm` |
| **Network Isolation** | No external IP, internal only | Deployed with `--no-address` |
| **Auditable Builds** | Git commit hash in image metadata | Reproducible builds, published hashes |

## Threat Model

### ✅ Protected Against

1. **Malicious Administrator**
   - Cannot SSH into TEE (SSH disabled in image)
   - Cannot modify running code (immutable)
   - Cannot deploy unapproved image (clients verify image_id)

2. **Compromised Startup Scripts**
   - No startup scripts used
   - Code is baked into image

3. **Runtime Code Injection**
   - No SSH access
   - No external network access (no external IP)
   - Systemd service cannot be modified

4. **Memory Access Attacks**
   - AMD SEV-SNP encrypts VM memory
   - Hypervisor cannot read memory
   - DMA attacks prevented

5. **Boot-Time Attacks**
   - Secure boot verifies boot chain
   - vTPM stores measurements
   - Any modification changes measurements

### ⚠️ Risks Remaining

1. **Compromised Build Process**
   - **Mitigation:** Reproducible builds, multiple builders verify same hash
   
2. **Hardware Vulnerabilities**
   - **Mitigation:** Keep firmware updated, monitor AMD security advisories
   
3. **Side-Channel Attacks**
   - **Mitigation:** Use constant-time crypto operations, isolate queries
   
4. **Compromised GCP Control Plane**
   - **Mitigation:** SEV-SNP protects memory even from hypervisor

## Deployment Workflow

### Initial Setup (One Time)

```bash
# 1. Audit source code
cd /Users/dbrown/Development/permissible
git log --oneline -1
# Output: abc123 Latest commit

# 2. Review TEE server
less workers/tee_server.py

# 3. Build immutable image
cd web_api/scripts
./build_tee_image.sh
# Output:
#   Image: permissible-tee-20251129-143022
#   Image ID: 1234567890123456789
#   Code Hash: sha256:abc123def456...

# 4. PUBLISH these values for client verification
cat > ../../APPROVED_TEE.txt <<EOF
Approved TEE Image
==================
Image ID: 1234567890123456789
Code Hash: sha256:abc123def456...
Git Commit: abc123
Build Date: 2024-11-29
Status: APPROVED
EOF

# 5. Deploy production TEE
./deploy_tee_from_image.sh shared-tee-prod

# 6. Configure web server
INTERNAL_IP=$(gcloud compute instances describe shared-tee-prod \
    --zone=us-central1-a \
    --format="get(networkInterfaces[0].networkIP)")

cat >> ../.env <<EOF
TEE_ENDPOINT=http://${INTERNAL_IP}:8080
APPROVED_IMAGE_ID=1234567890123456789
APPROVED_CODE_HASH=sha256:abc123def456...
EOF
```

### Updating TEE Code

```bash
# 1. Fix bug in code
cd /Users/dbrown/Development/permissible
git commit -m "Security: Fix data leak in query executor"
git push

# 2. Build NEW image
cd web_api/scripts
./build_tee_image.sh
# Output: NEW Image ID: 9876543210

# 3. Update APPROVED_TEE.txt with new values
cat > ../../APPROVED_TEE.txt <<EOF
Current Version (2024-11-30)
=============================
Image ID: 9876543210
Code Hash: sha256:def789...
Git Commit: def456
Status: APPROVED

Deprecated Versions
===================
Image ID: 1234567890123456789 (deprecated 2024-11-30)
EOF

# 4. Deploy new TEE
./deploy_tee_from_image.sh shared-tee-prod-v2

# 5. Update web server to use new TEE
# Edit .env with new INTERNAL_IP

# 6. Clients automatically verify new image
# Old image ID will be rejected

# 7. Decommission old TEE after grace period
gcloud compute instances delete shared-tee-prod \
    --zone=us-central1-a
```

## Client Verification Code

### JavaScript (Browser)

```javascript
// Load approved values from server config
const APPROVED_IMAGE_ID = "1234567890123456789";
const APPROVED_CODE_HASH = "sha256:abc123def456...";

async function verifyTEE(teeEndpoint) {
    // 1. Fetch attestation
    const response = await fetch(`${teeEndpoint}/attestation`);
    const { attestation, signature } = await response.json();
    
    // 2. Verify image ID
    if (attestation.image_id !== APPROVED_IMAGE_ID) {
        throw new Error(
            `TEE is running unapproved image!\n` +
            `Expected: ${APPROVED_IMAGE_ID}\n` +
            `Got: ${attestation.image_id}`
        );
    }
    
    // 3. Verify code hash
    if (attestation.code_measurement !== APPROVED_CODE_HASH) {
        throw new Error(
            `TEE code does not match audit!\n` +
            `Expected: ${APPROVED_CODE_HASH}\n` +
            `Got: ${attestation.code_measurement}`
        );
    }
    
    // 4. Verify SSH is disabled
    if (attestation.ssh_disabled !== true) {
        throw new Error("TEE allows SSH - not immutable!");
    }
    
    // 5. Verify confidential computing
    if (attestation.confidential_computing !== true) {
        throw new Error("Confidential computing not enabled!");
    }
    
    // 6. Verify attestation signature
    const publicKey = await importPublicKey(attestation.public_key);
    const isValid = await verifySignature(
        attestation,
        signature,
        publicKey
    );
    if (!isValid) {
        throw new Error("Attestation signature invalid!");
    }
    
    // All checks passed - safe to upload
    return {
        verified: true,
        publicKey: attestation.public_key,
        imageId: attestation.image_id,
        codeHash: attestation.code_measurement
    };
}

// Usage
try {
    const tee = await verifyTEE(TEE_ENDPOINT);
    console.log("✅ TEE verified, safe to upload");
    await uploadEncryptedData(tee.publicKey, sensitiveData);
} catch (error) {
    console.error("❌ TEE verification failed:", error.message);
    alert("Cannot upload - TEE is not trusted!");
}
```

### Python (Backend)

```python
import requests
import hashlib
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

APPROVED_IMAGE_ID = "1234567890123456789"
APPROVED_CODE_HASH = "sha256:abc123def456..."

def verify_tee(tee_endpoint):
    """Verify TEE before allowing uploads"""
    
    # Fetch attestation
    resp = requests.get(f"{tee_endpoint}/attestation")
    data = resp.json()
    attestation = data['attestation']
    signature = data['signature']
    
    # Verify image ID
    if attestation['image_id'] != APPROVED_IMAGE_ID:
        raise ValueError(f"Unapproved image: {attestation['image_id']}")
    
    # Verify code hash
    if attestation['code_measurement'] != APPROVED_CODE_HASH:
        raise ValueError(f"Code hash mismatch: {attestation['code_measurement']}")
    
    # Verify security properties
    assert attestation['ssh_disabled'] is True, "SSH is enabled!"
    assert attestation['confidential_computing'] is True, "Not confidential!"
    assert attestation['immutable_code'] is True, "Code is mutable!"
    
    # Verify signature
    public_key = serialization.load_pem_public_key(
        attestation['public_key'].encode('utf-8')
    )
    
    attestation_json = json.dumps(attestation, sort_keys=True)
    signature_bytes = base64.b64decode(signature)
    
    try:
        public_key.verify(
            signature_bytes,
            attestation_json.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    except Exception as e:
        raise ValueError(f"Signature verification failed: {e}")
    
    return {
        'verified': True,
        'public_key': attestation['public_key'],
        'image_id': attestation['image_id']
    }

# Usage
try:
    tee = verify_tee(TEE_ENDPOINT)
    print("✅ TEE verified")
except ValueError as e:
    print(f"❌ TEE verification failed: {e}")
    raise
```

## Monitoring & Auditing

### Cloud Logging Queries

```sql
-- View TEE startup logs
resource.type="gce_instance"
resource.labels.instance_id="shared-tee-prod"
"Starting TEE Server"

-- Detect if SSH was attempted (should never happen)
resource.type="gce_instance"
resource.labels.instance_id="shared-tee-prod"
"sshd"

-- Monitor dataset uploads
resource.type="gce_instance"
resource.labels.instance_id="shared-tee-prod"
"Successfully decrypted"

-- Watch for errors
resource.type="gce_instance"
resource.labels.instance_id="shared-tee-prod"
severity>=ERROR
```

### Alerts to Configure

1. **SSH Access Detected** (should be impossible)
   - Trigger: Any log containing "sshd" or "SSH"
   - Action: Page security team, investigate immediately

2. **Instance Modified**
   - Trigger: Instance metadata changed
   - Action: Alert operations, verify change was authorized

3. **High Error Rate**
   - Trigger: >10 errors per minute
   - Action: Check if attack in progress

4. **Unexpected Restarts**
   - Trigger: TEE service restarted
   - Action: Investigate cause

## Production Checklist

Before deploying to production:

- [ ] Source code audited by security team
- [ ] Image built from audited git commit
- [ ] Image ID and code hash published to clients
- [ ] Client verification code deployed and tested
- [ ] SSH disabled in image (verify with `systemctl status sshd`)
- [ ] No external IP (verify with `gcloud compute instances describe`)
- [ ] Confidential computing enabled (verify in instance config)
- [ ] Secure boot + vTPM enabled
- [ ] Network firewall rules configured
- [ ] Cloud Logging alerts configured
- [ ] Incident response plan documented
- [ ] Backup TEE instance prepared
- [ ] Key rotation procedure documented
- [ ] Emergency contact list updated
- [ ] Performed test deployment and verification
- [ ] Load testing completed

## Testing

```bash
# Run complete test
cd /Users/dbrown/Development/permissible/web_api/scripts
./test_tee_deployment.sh

# Manual verification
gcloud compute ssh shared-tee-test --zone=us-central1-a \
    --command='curl http://localhost:8080/attestation | jq .'

# Verify SSH is disabled
gcloud compute ssh shared-tee-test --zone=us-central1-a \
    --command='systemctl status sshd'
# Should show: "Unit sshd.service could not be found"

# Verify code hash
gcloud compute ssh shared-tee-test --zone=us-central1-a \
    --command='cat /opt/tee-runtime/CODE_HASH.txt'
```

## Cost Estimate

**Development:**
- Image storage: ~$0.10/month per image
- n2d-standard-2 VM: ~$73/month (24/7) or ~$0.10/hour
- Network egress: ~$5-20/month

**Production:**
- 2x VMs for redundancy: ~$146/month
- Load balancer: ~$20/month
- Cloud Logging: ~$5/month
- **Total: ~$171/month**

**Cost Optimization:**
```bash
# Stop test VMs when not in use
gcloud compute instances stop shared-tee-test --zone=us-central1-a

# Delete old images
gcloud compute images list --filter="family=permissible-tee" --limit=5
gcloud compute images delete OLD_IMAGE_NAME
```

## FAQ

**Q: How is this different from the old deployment script?**

A: Old script injected code at runtime via startup scripts. New approach bakes code into immutable images that clients can verify.

**Q: Can I still use SSH for debugging?**

A: No, SSH is disabled for zero-trust. View logs via Cloud Logging instead.

**Q: What if there's a critical bug?**

A: Build new image, publish new image_id, deploy new instance. Takes ~10 minutes.

**Q: How do clients know which image_id to trust?**

A: You publish approved values in `APPROVED_TEE.txt` or your web server config. Clients verify before uploading.

**Q: Can GCP see my data?**

A: No, AMD SEV-SNP encrypts VM memory. GCP hypervisor cannot read it.

**Q: Is this really zero-trust?**

A: Yes:
- Don't trust admins (no SSH, no access)
- Don't trust network (memory encrypted)
- Don't trust runtime config (code immutable)
- Only trust cryptographically verified image_id + code_hash

## References

- **AMD SEV-SNP:** https://www.amd.com/en/technologies/infinity-guard
- **GCP Confidential VMs:** https://cloud.google.com/confidential-computing
- **Zero Trust Architecture:** NIST SP 800-207

## Summary

**Key Principle:** Don't trust what you can't verify.

Old approach: "Trust me, I deployed the right code"  
New approach: **"Prove it via attestation, or I won't upload"**

Files to review:
- `docs/ZERO_TRUST_TEE_DEPLOYMENT.md` - Complete guide
- `scripts/build_tee_image.sh` - Image builder
- `scripts/deploy_tee_from_image.sh` - Deployer
- `workers/tee_server.py` - TEE server code
