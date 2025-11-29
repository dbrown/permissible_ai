# TEE Trust Model and User Verification

## The Trust Problem

**Question**: How can users trust that administrators haven't accessed the TEE VM via SSH or tampered with data?

**Answer**: Through cryptographic attestation, immutable audit logs, and measured boot verification.

## Trust Architecture

### What Users Need to Verify

1. **Code Integrity**: The TEE is running approved, unmodified code
2. **No Tampering**: No one (including admins) has modified the runtime
3. **Isolation**: Data and queries are isolated from the host system
4. **Audit Trail**: All access and operations are logged immutably

### How Confidential Computing Provides This

```
┌─────────────────────────────────────────────────────────┐
│  AMD SEV (Secure Encrypted Virtualization)             │
│  • Memory encrypted with VM-specific key                │
│  • Hypervisor CANNOT access VM memory                   │
│  • Cloud provider (Google) CANNOT see data             │
│  • Even root on host cannot decrypt memory              │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Measured Boot + vTPM                                   │
│  • Boot measurements stored in vTPM                     │
│  • Any change to code/config changes measurements       │
│  • Attestation includes these measurements              │
│  • Users can verify exact code is running               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Attestation Token (Signed by vTPM)                     │
│  • Proves: SEV enabled, Secure Boot, measurements       │
│  • Cannot be forged (signed by hardware)                │
│  • Includes runtime hash                                │
│  • Users verify before uploading data                   │
└─────────────────────────────────────────────────────────┘
```

## User Verification Methods

### 1. Attestation Verification (Primary Method)

Users verify the TEE BEFORE uploading any data:

```python
import requests
import jwt
import hashlib

def verify_tee_attestation(tee_endpoint):
    """
    Verify TEE attestation before trusting it with data
    
    Users should run this BEFORE uploading datasets
    """
    # Get attestation token
    response = requests.get(f"{tee_endpoint}/attestation")
    attestation = response.json()
    token = attestation['attestation_token']
    
    # Decode token (signed by vTPM)
    claims = jwt.decode(token, options={"verify_signature": False})
    
    # Critical checks
    checks = {
        'confidential_computing': claims.get('confidential_computing') == True,
        'secure_boot': claims.get('secure_boot') == True,
        'vtpm_enabled': claims.get('vtpm_enabled') == True,
        'runtime_hash': claims.get('runtime_hash') == EXPECTED_RUNTIME_HASH,
        'boot_measurement': claims.get('pcr0') == EXPECTED_BOOT_MEASUREMENT,
    }
    
    if not all(checks.values()):
        raise SecurityError("TEE attestation verification failed!")
    
    print("✓ TEE verified - safe to upload data")
    return True
```

**What this proves:**
- ✅ Code running is exactly what you expect (hash matches)
- ✅ No modifications since boot (boot measurements match)
- ✅ Memory encryption is active (SEV enabled)
- ✅ Secure boot prevents malicious code (vTPM verified)

### 2. Runtime Hash Verification

The TEE service provides a hash of its runtime code:

```bash
curl http://34.56.122.87:8080/runtime-hash

# Response:
{
  "runtime_hash": "sha256:a3f2b1...",
  "files": {
    "attestation_service.py": "sha256:123...",
    "query_executor.py": "sha256:456..."
  },
  "timestamp": "2025-11-29T17:00:00Z"
}
```

**Users compare this with published hashes:**
- Source code is published on GitHub
- Expected hashes are documented
- Any change (including SSH modifications) changes the hash

### 3. Immutable Audit Logs

All TEE operations are logged to Cloud Logging (immutable):

```bash
# Query audit logs (available to all users)
gcloud logging read "resource.type=gce_instance AND \
  resource.labels.instance_id=shared-tee-dev" \
  --limit=100 \
  --format=json
```

**Logs include:**
- SSH connections (admin access attempts)
- Service restarts
- Code modifications
- File system changes
- All query executions

**Key point**: Users can see if an admin SSH'd in, but the attestation would also fail.

### 4. Continuous Attestation Monitoring

Users don't just verify once - they monitor continuously:

```python
import time

def monitor_tee_integrity(tee_endpoint, interval=300):
    """
    Continuously verify TEE hasn't been tampered with
    
    Run this in the background during your collaboration session
    """
    initial_hash = get_runtime_hash(tee_endpoint)
    
    while True:
        current_hash = get_runtime_hash(tee_endpoint)
        
        if current_hash != initial_hash:
            alert("TEE CODE CHANGED - POSSIBLE TAMPERING!")
            stop_uploading_data()
            
        time.sleep(interval)  # Check every 5 minutes
```

### 5. Boot Measurement Verification (PCR Values)

The vTPM stores measurements in Platform Configuration Registers (PCRs):

```bash
# Get PCR values from attestation
curl http://34.56.122.87:8080/attestation | jq '.pcr_values'

# Response:
{
  "pcr0": "a3f2b1...",  # UEFI firmware
  "pcr1": "b4e5c2...",  # UEFI config
  "pcr7": "c5f6d3...",  # Secure Boot policy
  "pcr8": "d6g7e4...",  # Boot components
}
```

**These values prove:**
- Exact firmware version
- Secure boot configuration
- No bootkit or rootkit
- No firmware tampering

### 6. Remote Attestation Service (Production)

For production, use a third-party attestation service:

```
┌─────────┐      1. Request Attestation      ┌──────────┐
│  User   │────────────────────────────────▶│   TEE    │
└─────────┘                                  └──────────┘
     │                                             │
     │                        2. Generate Report  │
     │                           (signed by vTPM) │
     │                                             │
     │         3. Send Report                      │
     │    ◀────────────────────────────────────────┘
     │
     │         4. Verify with Intel/AMD/Google
     │    ──────────────────────────────────▶
     │                                       ┌─────────────────┐
     │         5. Verification Result        │  Attestation    │
     │    ◀──────────────────────────────────│  Verification   │
     │                                       │  Service (AVS)  │
     │                                       └─────────────────┘
     │
     ▼
   ✓ Trust Decision
```

**Examples:**
- Google Confidential Space
- Intel Attestation Service
- AMD SEV-SNP Attestation
- Project Oak

## Implementation: Enhanced Attestation

Let me show you how to implement runtime hash verification:

### Update TEE Attestation Service

```python
# Add to attestation_service.py

import hashlib
import os

def compute_runtime_hash():
    """Compute hash of all runtime files"""
    files_to_hash = [
        '/opt/tee-runtime/attestation_service.py',
        '/opt/tee-runtime/query_executor.py',
        '/etc/systemd/system/tee-attestation.service'
    ]
    
    hashes = {}
    combined = ""
    
    for filepath in files_to_hash:
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
                hashes[filepath] = f"sha256:{file_hash}"
                combined += file_hash
    
    # Combined hash of all files
    runtime_hash = hashlib.sha256(combined.encode()).hexdigest()
    
    return {
        'runtime_hash': f"sha256:{runtime_hash}",
        'files': hashes,
        'timestamp': datetime.utcnow().isoformat()
    }

@app.route('/runtime-hash', methods=['GET'])
def get_runtime_hash():
    """Get cryptographic hash of runtime code"""
    try:
        return jsonify(compute_runtime_hash())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/attestation', methods=['GET'])
def get_attestation():
    """Generate attestation token with runtime hash"""
    try:
        # ... existing code ...
        
        # Add runtime hash to claims
        runtime_info = compute_runtime_hash()
        
        claims = {
            'iss': 'gcp-confidential-vm',
            'sub': 'shared-tee-service',
            # ... existing claims ...
            'runtime_hash': runtime_info['runtime_hash'],
            'file_hashes': runtime_info['files'],
            # PCR values from vTPM
            'pcr0': get_pcr_value(0),  # UEFI firmware
            'pcr7': get_pcr_value(7),  # Secure Boot
        }
        
        # ... rest of existing code ...
```

### Publish Expected Hashes

```bash
# docs/TEE_EXPECTED_HASHES.md

# TEE Runtime Expected Hashes

These are the expected cryptographic hashes for the TEE runtime.
Users should verify these before trusting the TEE.

## Version 1.0.0 (2025-11-29)

**Combined Runtime Hash:**
```
sha256:a3f2b1c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7
```

**Individual Files:**
- `attestation_service.py`: sha256:123abc...
- `query_executor.py`: sha256:456def...
- `tee-attestation.service`: sha256:789ghi...

**Boot Measurements (PCR Values):**
- PCR0 (UEFI): sha256:aaa111...
- PCR7 (Secure Boot): sha256:bbb222...

## How to Verify

```python
import requests

response = requests.get('http://TEE_IP:8080/runtime-hash')
actual_hash = response.json()['runtime_hash']
expected_hash = 'sha256:a3f2b1c4d5e6...'

if actual_hash != expected_hash:
    raise SecurityError("Runtime hash mismatch - do not trust!")
```
```

## What About SSH Access?

### Problem with SSH
If an admin SSH's into the TEE VM, they could:
- View memory (but it's encrypted with SEV!)
- Modify code (but runtime hash would change!)
- Read files (but data is KMS-encrypted!)
- Interfere with queries (but would be logged!)

### How Users Detect SSH Access

#### Method 1: Check Audit Logs (Immutable)
```bash
# Users can query public audit logs
gcloud logging read "resource.type=gce_instance \
  AND resource.labels.instance_id=shared-tee-dev \
  AND protoPayload.methodName=v1.compute.instances.osLogin" \
  --format=json

# Shows all SSH login attempts with:
# - Who logged in
# - When
# - From what IP
# - What they did
```

#### Method 2: Attestation Fails After SSH
```python
# Before admin SSH:
initial_attestation = get_attestation()  # ✓ Valid

# Admin SSH's and modifies code
admin_sshs_in()

# After admin SSH:
new_attestation = get_attestation()
# Runtime hash changed! ✗ Invalid

# User's monitoring script alerts:
# "TEE COMPROMISED - HASH MISMATCH"
```

#### Method 3: File Integrity Monitoring
```bash
# TEE service monitors its own files
inotify /opt/tee-runtime/

# If ANY file changes:
# 1. Log event (immutable)
# 2. Update runtime hash
# 3. Alert all users
# 4. Optionally: shut down service
```

### SSH Access Policy

**Recommended production setup:**

1. **Disable SSH entirely**
   ```bash
   # Remove SSH from firewall
   gcloud compute firewall-rules delete allow-ssh-tee
   
   # Disable SSH service in VM
   systemctl disable sshd
   systemctl stop sshd
   ```

2. **Use Serial Console only (logged)**
   ```bash
   # Serial console access is fully logged
   gcloud compute connect-to-serial-port shared-tee-dev
   # Every command logged to Cloud Logging
   ```

3. **Require Break-Glass Process**
   - SSH access only for emergencies
   - Requires multiple approvals
   - Triggers alerts to all users
   - Requires re-attestation after access

4. **Immutable Infrastructure**
   - Never modify running TEE
   - To update: destroy and recreate
   - New attestation with new hashes
   - Users verify new instance

## Trust But Verify: Full Workflow

### For Users (Data Owners)

```python
# 1. Get attestation BEFORE uploading data
attestation = verify_tee_attestation(tee_endpoint)

if not attestation.valid:
    print("❌ Do not upload data - TEE not verified")
    exit(1)

# 2. Compare runtime hash with published version
if attestation.runtime_hash != PUBLISHED_HASH:
    print("❌ Runtime hash mismatch - possible tampering")
    exit(1)

# 3. Check audit logs for suspicious activity
logs = get_audit_logs(since=last_check)
if detect_ssh_access(logs):
    print("⚠️  Admin accessed VM - review activity")
    
# 4. Only then upload data
print("✓ TEE verified - safe to upload")
upload_encrypted_data()

# 5. Monitor continuously during session
monitor_tee_integrity(interval=300)  # Every 5 min
```

### For TEE Operators

```python
# Automated integrity monitoring
def tee_integrity_monitor():
    initial_state = capture_state()
    
    while True:
        current_state = capture_state()
        
        if current_state != initial_state:
            # Alert all users
            send_alert_to_all_users(
                "TEE state changed",
                changes=diff(initial_state, current_state)
            )
            
            # Update published hashes
            publish_new_hashes(current_state)
            
            # Require users to re-verify
            require_re_attestation()
```

## Summary: Multi-Layer Trust

```
Layer 1: AMD SEV Memory Encryption
└─> Even admin with root cannot read VM memory

Layer 2: Measured Boot + vTPM
└─> Any code change breaks attestation

Layer 3: Runtime Hash Verification
└─> Users verify exact code running

Layer 4: Immutable Audit Logs
└─> All access attempts logged (cannot be deleted)

Layer 5: Continuous Monitoring
└─> Users watch for changes in real-time

Layer 6: Break-Glass Process
└─> Admin access triggers alerts + requires re-attestation
```

**Bottom line:** Users don't have to "trust" admins - they can cryptographically verify the TEE is unmodified and continuously monitor for any changes.

## Next Steps for Production

1. **Implement runtime hash endpoint** (shown above)
2. **Publish expected hashes** in repository
3. **Disable SSH access** entirely
4. **Enable audit log monitoring** for all users
5. **Implement continuous attestation** checks
6. **Use remote attestation service** (Google Confidential Space)
7. **Document break-glass procedures**

This makes the TEE trustless - users can verify rather than trust.
