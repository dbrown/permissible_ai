# Secure Dataset Upload Protocol

## Overview

This document describes the cryptographic protocol for securely uploading sensitive datasets to the Trusted Execution Environment (TEE) with zero-trust guarantees.

## Security Goals

1. **Zero Trust**: No intermediary (including the web server) ever sees plaintext data
2. **Attestation Verification**: Clients verify TEE identity before uploading
3. **End-to-End Encryption**: Data encrypted client-side with TEE's public key
4. **Session Isolation**: Each collaboration session uses isolated encryption keys
5. **Auditability**: All operations logged immutably

## Protocol Flow

### Phase 1: TEE Identity Establishment

```
Client                    TEE (Confidential VM)              Web Server
  |                              |                                |
  |  1. Request attestation      |                                |
  |----------------------------->|                                |
  |                              |                                |
  |  2. Attestation + Public Key |                                |
  |<-----------------------------|                                |
  |  - Hardware signature        |                                |
  |  - Code measurement hash     |                                |
  |  - TEE public key (RSA-4096) |                                |
  |                              |                                |
  |  3. Verify attestation       |                                |
  |  - Check hardware signature  |                                |
  |  - Verify code hash          |                                |
  |  - Extract public key        |                                |
  |                              |                                |
```

**Attestation Structure:**
```json
{
  "attestation": {
    "tee_type": "gcp_confidential_vm",
    "code_measurement": "sha256:abc123...",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "generated_at": "2024-01-01T00:00:00Z",
    "expires_at": "2024-01-02T00:00:00Z"
  },
  "signature": "base64_encoded_signature",
  "signature_algorithm": "RSA-PSS-SHA256"
}
```

**Client MUST verify:**
- Signature chain traces back to hardware root of trust
- Code measurement matches known-good hash
- Attestation is not expired
- TEE type is correct (GCP Confidential VM)

### Phase 2: Client-Side Encryption

```
Client (Browser/CLI)
  |
  |  1. User selects file
  |     └─> file.csv (plaintext)
  |
  |  2. Generate random AES-256 key
  |     └─> aes_key = random(256 bits)
  |
  |  3. Encrypt file with AES-GCM
  |     └─> encrypted_data = AES-GCM(file.csv, aes_key, iv)
  |
  |  4. Encrypt AES key with TEE public key
  |     └─> encrypted_key = RSA-OAEP(aes_key, tee_public_key)
  |
  |  5. Upload encrypted package
  |     └─> {encrypted_data, encrypted_key, iv, metadata}
  |
```

**Encryption Details:**
- **Data Encryption**: AES-256-GCM (authenticated encryption)
- **Key Wrapping**: RSA-OAEP with SHA-256 (4096-bit key)
- **IV**: 96-bit random nonce (generated per file)
- **No Authentication Tag Separation**: GCM includes authentication

### Phase 3: Secure Upload to TEE

```
Client                     TEE                   Web Server
  |                         |                         |
  |  1. Get upload token    |                         |
  |------------------------------------------>|       |
  |                         |                  |      |
  |  2. Create metadata     |                  |      |
  |  (name, description)    |                  |      |
  |<------------------------------------------|       |
  |  dataset_id = 123       |                  |      |
  |  upload_token = JWT     |                  |      |
  |                         |                  |      |
  |  3. Upload encrypted    |                  |      |
  |     package DIRECTLY    |                  |      |
  |------------------------>|                  |      |
  |  {encrypted_data,       |                  |      |
  |   encrypted_key,        |                  |      |
  |   iv, dataset_id}       |                  |      |
  |                         |                  |      |
  |                         |  4. Decrypt with |      |
  |                         |     TEE private  |      |
  |                         |     key          |      |
  |                         |  5. Re-encrypt   |      |
  |                         |     with session |      |
  |                         |     key          |      |
  |                         |  6. Store        |      |
  |                         |                  |      |
  |                         |  7. Notify control plane  |
  |                         |--------------------------->|
  |                         |  dataset 123 = AVAILABLE  |
  |                         |                  |      |
```

**Upload Endpoint:** `POST {TEE_ENDPOINT}/upload`

**Upload Payload:**
```json
{
  "dataset_id": 123,
  "session_id": 456,
  "encrypted_data": "base64_encoded_ciphertext",
  "encrypted_key": "base64_encoded_wrapped_key",
  "iv": "base64_encoded_iv",
  "algorithm": "AES-256-GCM",
  "filename": "patient_data.csv",
  "file_size": 1048576
}
```

**Authorization Header:**
```
Authorization: Bearer <JWT_upload_token>
```

**Upload Token Claims:**
```json
{
  "dataset_id": 123,
  "session_id": 456,
  "user_id": 789,
  "exp": 1704150000
}
```

### Phase 4: TEE Processing

Inside the TEE (Confidential VM):

```python
# 1. Decrypt AES key using TEE private key (never leaves enclave)
aes_key = tee_private_key.decrypt(encrypted_key, RSA_OAEP)

# 2. Decrypt data
plaintext = AES_GCM.decrypt(encrypted_data, aes_key, iv)

# 3. Re-encrypt with session-specific key
session_key = get_session_key(session_id)  # Isolated per collaboration
session_encrypted = AES_GCM.encrypt(plaintext, session_key, new_iv)

# 4. Store encrypted (plaintext destroyed from memory)
store_dataset(dataset_id, session_encrypted)

# 5. Notify control plane
webhook_callback(dataset_id, status='available', checksum=sha256(plaintext))
```

**Key Properties:**
- TEE private key **never leaves** the confidential VM
- Plaintext data exists in memory **only during re-encryption**
- Session keys provide **isolation** between collaborations
- Original encryption key is **discarded** after use

### Phase 5: Webhook Callback

```
TEE                          Web Server
  |                              |
  |  POST /api/tee/callback      |
  |----------------------------->|
  |  {                           |
  |    entity_type: 'dataset',   |
  |    entity_id: 123,           |
  |    status: 'available',      |
  |    metadata: {               |
  |      checksum: 'sha256:...', |
  |      file_size: 1048576      |
  |    }                         |
  |  }                           |
  |                              |
  |                              |  Update DB:
  |                              |  Dataset 123
  |                              |  status = AVAILABLE
  |                              |
```

## Security Guarantees

### 1. Zero Trust - No Intermediary Access

**Threat:** Web server admin tries to access data

**Protection:**
- Plaintext data **never transmitted** to web server
- Web server only sees:
  - Dataset metadata (name, description)
  - Upload status notifications from TEE
  - No encryption keys, no ciphertext

**Evidence:** Client connects directly to TEE endpoint (`TEE_SERVICE_ENDPOINT`)

### 2. TEE Verification

**Threat:** Attacker replaces TEE with fake server

**Protection:**
- Hardware attestation signed by Confidential VM TPM/SEV
- Code measurement (SHA-256 hash) proves exact code running
- Client verifies signature chain before upload

**Verification Steps:**
```javascript
// 1. Fetch attestation
const attestation = await fetch(`${TEE_ENDPOINT}/attestation`).then(r => r.json());

// 2. Verify signature (RSA-PSS)
const valid = await crypto.subtle.verify(
  'RSA-PSS',
  publicKey,
  attestation.signature,
  attestation.attestation
);

// 3. Check code measurement
assert(attestation.attestation.code_measurement === EXPECTED_HASH);

// 4. Extract TEE public key
const teePublicKey = attestation.attestation.public_key;
```

### 3. Session Isolation

**Threat:** Data from one collaboration leaked to another

**Protection:**
- Each session has unique encryption key generated in TEE
- Keys never shared between sessions
- Query execution strictly enforces session boundaries

**Implementation:**
```python
SESSION_KEYS = {}  # session_id -> AES-256 key (in-memory only)

def get_session_key(session_id):
    if session_id not in SESSION_KEYS:
        SESSION_KEYS[session_id] = os.urandom(32)  # Never persisted
    return SESSION_KEYS[session_id]
```

### 4. Forward Secrecy

**Threat:** Future compromise reveals past data

**Protection:**
- Ephemeral AES keys discarded after upload
- Session keys destroyed when session closes
- No key material persisted to disk

### 5. Authenticated Encryption

**Threat:** Ciphertext tampering

**Protection:**
- AES-GCM provides authentication
- RSA-OAEP prevents key wrapping attacks
- Checksums verified after decryption

## Attack Scenarios & Defenses

### Scenario 1: Compromised Web Server

**Attack:** Attacker gains root access to web server

**Defense:**
- ✅ Web server never had plaintext data
- ✅ Web server cannot decrypt ciphertext (no keys)
- ✅ Web server cannot fake TEE attestation (no private key)
- ✅ Upload tokens are short-lived (1 hour expiry)

**Result:** Attacker gains only metadata, no sensitive data

### Scenario 2: Man-in-the-Middle

**Attack:** Network attacker intercepts upload

**Defense:**
- ✅ Data encrypted before transmission (TLS + application-level)
- ✅ Attacker cannot decrypt (needs TEE private key)
- ✅ Attacker cannot replace TEE (attestation verification fails)

**Result:** Attacker sees only ciphertext

### Scenario 3: Malicious TEE Code

**Attack:** Attacker deploys modified TEE with backdoor

**Defense:**
- ✅ Code measurement changes (SHA-256 hash differs)
- ✅ Client attestation verification fails
- ✅ Upload aborted before sending data

**Result:** Client never uploads to compromised TEE

### Scenario 4: Replay Attack

**Attack:** Attacker replays old upload

**Defense:**
- ✅ Upload tokens expire (JWT exp claim)
- ✅ Dataset IDs unique per session
- ✅ Duplicate uploads rejected by TEE

**Result:** Replay fails

## Implementation Checklist

### Client-Side (Browser/CLI)
- [ ] Fetch and parse TEE attestation
- [ ] Verify attestation signature
- [ ] Check code measurement hash
- [ ] Extract TEE public key
- [ ] Generate random AES-256 key (crypto.subtle or libsodium)
- [ ] Encrypt file with AES-GCM
- [ ] Wrap AES key with RSA-OAEP
- [ ] Upload encrypted package to TEE (NOT web server)
- [ ] Display verification status to user

### TEE Server (Confidential VM)
- [ ] Generate RSA-4096 keypair on startup (in-memory only)
- [ ] Calculate code measurement (SHA-256 of binary)
- [ ] Expose attestation endpoint with hardware signature
- [ ] Accept encrypted uploads at `/upload`
- [ ] Decrypt with TEE private key
- [ ] Re-encrypt with session key
- [ ] Store encrypted dataset
- [ ] Webhook callback to control plane
- [ ] Audit log all operations

### Web Server (Control Plane)
- [ ] Create dataset metadata records
- [ ] Generate short-lived upload tokens (JWT)
- [ ] Provide TEE endpoint to clients
- [ ] Receive webhook callbacks from TEE
- [ ] Update dataset status (PENDING → AVAILABLE)
- [ ] NEVER handle plaintext data

## Testing

### Unit Tests
```bash
# Test client-side encryption
npm test test/encryption.test.js

# Test TEE decryption
pytest tests/test_tee_encryption.py

# Test attestation verification
pytest tests/test_attestation.py
```

### Integration Tests
```bash
# End-to-end upload flow
pytest tests/integration/test_secure_upload.py
```

### Security Audit
```bash
# Verify no plaintext in logs
grep -r "plaintext" /var/log/web_server/  # Should be empty

# Verify TEE private key never exported
grep -r "BEGIN PRIVATE KEY" /var/log/tee/  # Should be empty

# Verify session isolation
python scripts/test_session_isolation.py
```

## Deployment

### TEE Server Deployment
```bash
# 1. Deploy to Confidential VM
gcloud compute instances create tee-server \
  --machine-type=n2d-standard-4 \
  --confidential-compute \
  --maintenance-policy=TERMINATE \
  --image-family=ubuntu-2004-lts \
  --image-project=confidential-vm-images

# 2. Copy TEE server code
gcloud compute scp workers/tee_server.py tee-server:/opt/tee/

# 3. Start TEE server
gcloud compute ssh tee-server -- \
  "cd /opt/tee && sudo python3 tee_server.py"

# 4. Note the code measurement hash
gcloud compute ssh tee-server -- \
  "sha256sum /opt/tee/tee_server.py"
```

### Client Configuration
```javascript
// In client code, hardcode expected code hash
const EXPECTED_CODE_HASH = "sha256:abc123...";  // From deployment

// Before upload, verify
assert(attestation.code_measurement === EXPECTED_CODE_HASH);
```

### Web Server Configuration
```bash
# .env
TEE_SERVICE_ENDPOINT=https://tee.example.com:8080
TEE_INSTANCE_ID=tee-prod-001
CONTROL_PLANE_URL=https://api.example.com
```

## Monitoring

### Key Metrics
- Attestation verification success rate
- Upload success rate
- Average encryption time
- TEE memory usage (watch for leaks)

### Alerts
- ⚠️ Attestation signature verification failures
- ⚠️ Code measurement mismatches
- ⚠️ Unusual TEE restart patterns
- ⚠️ Session key memory leaks

## References

- [GCP Confidential Computing](https://cloud.google.com/confidential-computing)
- [Web Crypto API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Crypto_API)
- [AES-GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode)
- [RSA-OAEP](https://en.wikipedia.org/wiki/Optimal_asymmetric_encryption_padding)
- [Remote Attestation](https://en.wikipedia.org/wiki/Trusted_Computing#Remote_attestation)
