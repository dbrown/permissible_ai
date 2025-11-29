# Trusted Execution Environment (TEE) User Guide
## How to Verify Your Data is Secure

---

## What is a TEE?

A **Trusted Execution Environment (TEE)** is a secure, isolated computing environment where your sensitive data can be analyzed without anyone—including system administrators, cloud providers, or even other participants—being able to see the raw data.

Think of it as a **locked vault** where:
- Multiple parties can contribute data
- Approved computations run inside the vault
- Only the results come out
- No one can peek inside, not even the vault operator

---

## Who Should Read This?

This guide is for:
- **Data Scientists** contributing datasets to collaborative analyses
- **Research Analysts** using the platform for multi-party studies
- **Data Owners** who need to verify their data is protected
- **Compliance Officers** ensuring regulatory requirements are met
- **Anyone** who wants to understand how their data is kept secure

---

## The Trust Problem

### Traditional Cloud Computing Risk

In normal cloud computing, when you upload data:

```
Your Data → Cloud Server → Administrator Can View
                ↓
            Cloud Provider Can View
                ↓
            Other Users Might View
```

**Problem**: You must trust the cloud provider and administrators not to access your data.

### Our TEE Solution

With our Trusted Execution Environment:

```
Your Data → Encrypted → TEE (Locked Vault)
                         ↓
                    Cryptographic Proof
                         ↓
                    You Verify First
                         ↓
                    Data Never Exposed
```

**Solution**: You don't need to trust anyone. You can verify the security yourself.

---

## How the Security Works

### 1. Memory Encryption (AMD SEV)

**What it does**: All data in the TEE's memory is encrypted with a unique key that only the processor knows.

**Why it matters**:
- Cloud provider (Google) cannot read the memory
- System administrators cannot read the memory  
- Even with physical access to the server, data is encrypted
- The encryption key never leaves the processor

**Analogy**: It's like your data is in a safe deposit box. Even the bank employees can't open it.

### 2. Secure Boot & vTPM

**What it does**: 
- Secure Boot ensures only authorized software runs from startup
- Virtual Trusted Platform Module (vTPM) stores cryptographic measurements

**Why it matters**:
- Prevents malicious software from running
- Any change to the code is detected
- Creates an audit trail from the moment the system starts

**Analogy**: Like a tamper-evident seal on medicine bottles—you can see if anyone modified it.

### 3. Attestation Tokens

**What it does**: The TEE generates a cryptographically signed "proof" that:
- Confidential computing is enabled
- Specific code is running
- Security features are active
- The system hasn't been tampered with

**Why it matters**: 
- You verify this proof BEFORE uploading data
- If verification fails, you know not to trust the system
- The proof cannot be forged

**Analogy**: Like a notarized document that proves authenticity.

### 4. Runtime Hash Verification

**What it does**: Creates a unique "fingerprint" of all code running in the TEE.

**Why it matters**:
- Any change to the code (even one character) changes the fingerprint
- You compare the fingerprint to the published version
- If an admin modifies the code, you'll see the fingerprint change

**Analogy**: Like a wax seal on a letter—if broken, you know it was opened.

### 5. Immutable Audit Logs

**What it does**: Records every action (SSH logins, code changes, service restarts) to a permanent log.

**Why it matters**:
- Logs cannot be deleted or modified
- You can see if an administrator accessed the system
- All access is transparent and accountable

**Analogy**: Like security camera footage that can't be erased.

---

## Step-by-Step: Verifying Before You Trust

### Before Uploading Your Data

Follow these steps to verify the TEE is secure:

#### Step 1: Get the Attestation Token

```bash
# Request attestation from the TEE
curl http://TEE-ADDRESS:8080/attestation
```

You'll receive a response like:
```json
{
  "attestation_token": "eyJhbGc...(long encrypted string)",
  "instance_id": "6402129463391720599",
  "verified": true
}
```

#### Step 2: Decode and Verify the Token

The token contains claims about the TEE's security:

```json
{
  "confidential_computing": true,    ← Memory is encrypted
  "secure_boot": true,                ← No unauthorized software
  "vtpm_enabled": true,               ← Hardware security enabled
  "runtime_hash": "sha256:498373...", ← Code fingerprint
  "instance_id": "640212..."          ← Unique TEE identifier
}
```

**What to check**:
- ✅ `confidential_computing` must be `true`
- ✅ `secure_boot` must be `true`  
- ✅ `vtpm_enabled` must be `true`
- ✅ `runtime_hash` must match the published hash (see Step 3)

#### Step 3: Verify the Code Fingerprint

```bash
# Get the current code fingerprint
curl http://TEE-ADDRESS:8080/runtime-hash
```

Response:
```json
{
  "runtime_hash": "sha256:4983730f4c8eed078896dd05c4eba859a5fe3473ae23afc71bdf46922682bee8",
  "files": {
    "/opt/tee-runtime/attestation_service.py": "sha256:f08d866...",
    "/etc/systemd/system/tee-attestation.service": "sha256:6854e54..."
  }
}
```

**Compare this hash to the published hash** (found in project documentation or GitHub).

If they match → Safe to proceed  
If they don't match → DO NOT upload data, contact administrator

#### Step 4: Check for Administrator Access

```bash
# Check if anyone has accessed the TEE
curl http://TEE-ADDRESS:8080/audit-events
```

Look for SSH login events. If you see recent admin access:
- Review what was done
- Re-verify the runtime hash
- Consider waiting for a fresh deployment

#### Step 5: Only Then Upload Your Data

Once all verifications pass, you can safely upload your data knowing:
- ✅ Memory is encrypted
- ✅ Code hasn't been modified
- ✅ No unauthorized access
- ✅ Hardware security is active

---

## During Your Collaboration

### Continuous Monitoring

Don't just verify once—monitor continuously:

#### Every 5 Minutes: Check Runtime Hash

```bash
# Set up automatic checking
while true; do
  NEW_HASH=$(curl -s http://TEE-ADDRESS:8080/runtime-hash | jq -r .runtime_hash)
  if [ "$NEW_HASH" != "$ORIGINAL_HASH" ]; then
    echo "⚠️  WARNING: CODE CHANGED - STOP UPLOADING DATA"
    # Send alert email/SMS
  fi
  sleep 300  # Check every 5 minutes
done
```

#### Check Status Endpoint

```bash
curl http://TEE-ADDRESS:8080/status
```

Warnings will appear if suspicious activity is detected:
```json
{
  "status": "running",
  "warning": "SSH access detected in last hour - users should verify integrity"
}
```

---

## What Each Protection Prevents

### Protection Matrix

| Attack Scenario | Protection | How You Verify |
|----------------|-----------|----------------|
| **Admin views raw data** | AMD SEV Memory Encryption | Check `confidential_computing: true` in attestation |
| **Admin modifies code** | Runtime Hash Verification | Compare hash to published version |
| **Malicious software runs** | Secure Boot + vTPM | Check `secure_boot: true` and `vtpm_enabled: true` |
| **Secret access attempts** | Immutable Audit Logs | Query `/audit-events` endpoint |
| **Fake attestation** | Cryptographic Signatures | Token signed by hardware (cannot be forged) |
| **Data exfiltration** | Encrypted Storage + KMS | Data encrypted at rest, keys separate |

---

## Common Questions

### Q: Can the cloud provider (Google) see my data?

**A: No.** AMD SEV encryption means the data in memory is encrypted with a key that only the processor knows. Google's hypervisor cannot decrypt it.

### Q: Can system administrators SSH into the TEE and view data?

**A: No, and you can verify this.** 
1. Even if they SSH in, memory is encrypted
2. SSH access is logged in immutable audit logs
3. Any code changes modify the runtime hash
4. You monitor the hash continuously

### Q: How do I know the attestation isn't fake?

**A: Cryptographic signatures.** The attestation token is signed by the hardware vTPM. This signature cannot be forged without breaking modern cryptography (effectively impossible).

### Q: What if an administrator changes the code?

**A: You'll detect it immediately.**
- Runtime hash changes
- Your monitoring script alerts you
- You stop uploading data
- Audit logs show what changed

### Q: Can other researchers see my raw data?

**A: No.** 
- Data is encrypted with your keys
- Only approved, privacy-preserving queries run
- Results are aggregated (no individual records)
- You approve queries before execution

### Q: Do I need to trust anyone?

**A: No—that's the point!** You verify everything yourself:
- Attestation proves security features
- Runtime hash proves code integrity  
- Audit logs prove no tampering
- Continuous monitoring proves ongoing safety

---

## Real-World Workflow Example

### Healthcare Research Scenario

**Participants**: Hospital A, Hospital B  
**Goal**: Analyze combined patient outcomes without sharing raw data

#### Hospital A's Perspective

**1. Before Contributing Data (5 minutes)**

```bash
# Verify TEE security
curl http://tee.research.org:8080/attestation | jq .

# Check the fingerprint
curl http://tee.research.org:8080/runtime-hash | jq .runtime_hash
# Compare to: sha256:4983730f4c8eed078896dd05c4eba859a5fe3473ae23afc71bdf46922682bee8 ✓

# Check for suspicious access
curl http://tee.research.org:8080/audit-events | jq .ssh_events
# Result: No SSH access ✓
```

**Verification Complete** ✅ Safe to proceed

**2. Upload Encrypted Dataset**

```bash
# Data is encrypted locally before upload
# Only the TEE can decrypt it
upload_dataset("hospital-a-data.csv.encrypted")
```

**3. Continuous Monitoring (During Study)**

```bash
# Script runs every 5 minutes
monitor_tee_integrity()
# Alerts if anything changes
```

**4. Query Approval**

Hospital B submits a query:
```sql
SELECT diagnosis, COUNT(*), AVG(outcome_score)
FROM combined_data
GROUP BY diagnosis
HAVING COUNT(*) >= 10  -- k-anonymity protection
```

Hospital A reviews:
- ✅ Only aggregated results (no individual records)
- ✅ Minimum group size of 10 (privacy protection)
- ✅ No raw data exposed

**Approve Query** → Executes in TEE

**5. Receive Results**

Only aggregated statistics returned:
```
Diagnosis | Count | Avg Outcome
----------|-------|------------
DX001     | 150   | 85.3%
DX002     | 98    | 78.2%
```

Individual patient data **never leaves the TEE**.

---

## Red Flags: When to Stop

### Immediate Stop Indicators

🚨 **STOP and do not upload data if**:

1. **Attestation check fails**
   - `confidential_computing: false`
   - `secure_boot: false`
   - Missing security claims

2. **Runtime hash doesn't match**
   - Different fingerprint than published
   - Hash changes during your session

3. **Suspicious access detected**
   - Recent SSH logins without notice
   - Unexplained service restarts
   - Audit events show modifications

4. **Status warnings**
   - Service reports degraded security
   - Warnings about integrity issues

5. **Cannot verify attestation**
   - Endpoints not responding
   - Invalid cryptographic signatures
   - Missing audit logs

### What to Do Instead

1. **Contact administrator immediately**
2. **Request explanation of changes**
3. **Wait for new deployment with verified hash**
4. **Review audit logs for timeline**
5. **Re-verify before proceeding**

---

## Compliance & Regulations

### How TEE Helps Meet Requirements

#### HIPAA (Healthcare)
- ✅ Encryption at rest and in transit
- ✅ Access controls and audit logs
- ✅ Minimum necessary disclosure (aggregated results)
- ✅ Business Associate Agreement (BAA) supported

#### GDPR (European Data Protection)
- ✅ Data minimization (only approved queries)
- ✅ Technical safeguards (encryption)
- ✅ Transparency (audit logs)
- ✅ Right to audit (immutable logs)

#### FERPA (Education)
- ✅ Limited disclosure to authorized parties
- ✅ Audit trail of access
- ✅ Aggregate reporting only

---

## Glossary of Terms

**AMD SEV (Secure Encrypted Virtualization)**  
Hardware-based memory encryption that protects data from the cloud provider

**Attestation Token**  
Cryptographically signed proof that security features are enabled

**Confidential Computing**  
Technology that encrypts data during processing (not just at rest or in transit)

**Runtime Hash**  
Cryptographic fingerprint of code running in the TEE; changes if code is modified

**vTPM (Virtual Trusted Platform Module)**  
Hardware-backed security chip that stores cryptographic measurements

**Immutable Audit Log**  
Permanent record of system events that cannot be deleted or modified

**KMS (Key Management Service)**  
Secure service for managing encryption keys

**k-anonymity**  
Privacy guarantee that results include at least k individuals (e.g., k=10 means at least 10 people)

---

## Getting Started Checklist

- [ ] Understand what a TEE is and how it protects data
- [ ] Know how to request and verify attestation tokens
- [ ] Learn to check runtime hashes
- [ ] Set up continuous monitoring
- [ ] Review audit events before each session
- [ ] Understand when to stop and not upload data
- [ ] Save published runtime hashes for comparison
- [ ] Document your verification process for compliance
- [ ] Test the verification steps in a sandbox first
- [ ] Contact support if any verification step fails

---

## Support & Questions

### Who to Contact

**Security Questions**: security@yourorg.com  
**Technical Issues**: support@yourorg.com  
**Compliance**: compliance@yourorg.com  

### Resources

- **Published Runtime Hashes**: `docs/TEE_EXPECTED_HASHES.md`
- **Technical Documentation**: `docs/TEE_TRUST_AND_VERIFICATION.md`
- **API Reference**: `docs/api/tee.md`
- **Video Tutorial**: [Coming Soon]

---

## Summary: Your Safety Checklist

Before uploading data, verify:

1. ✅ **Attestation**: All security claims are `true`
2. ✅ **Runtime Hash**: Matches published version exactly
3. ✅ **Audit Logs**: No suspicious access or changes
4. ✅ **Status**: No warnings or degraded security

During collaboration, monitor:

5. ✅ **Hash Changes**: Alert if runtime hash changes
6. ✅ **Access Events**: Watch for unexpected SSH logins
7. ✅ **Status Updates**: Check for new warnings

If any check fails:

8. 🛑 **Stop**: Do not upload new data
9. 📞 **Contact**: Reach out to administrators
10. 🔍 **Investigate**: Review what changed and why

---

**Remember**: The TEE is designed so you don't have to trust anyone. You can verify everything yourself. Take the time to understand these protections—your data security depends on it.

---

*Last Updated: November 29, 2025*  
*Version: 1.0.0*
