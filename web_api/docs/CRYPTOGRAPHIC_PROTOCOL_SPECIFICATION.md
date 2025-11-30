# Cryptographic Protocol Specification: Zero-Trust Dataset Upload for TEE-Based Secure Multi-Party Computation

**Version:** 1.0  
**Date:** November 29, 2025  
**Authors:** Permissible AI Engineering Team

---

## Abstract

This document specifies a cryptographic protocol for securely uploading sensitive datasets to a Trusted Execution Environment (TEE) in a zero-trust architecture. The protocol ensures that no intermediary—including the control plane, cloud provider administrators, or network observers—can access plaintext data. Security is achieved through hybrid encryption (RSA-OAEP + AES-GCM), hardware-backed attestation, and session-level isolation within the TEE.

---

## 1. Threat Model

### 1.1 Adversaries

We consider the following adversaries:

- **A₁ (Honest-but-Curious Server Operator):** Controls the web application server and database. Can log all traffic, inspect server state, but does not actively tamper with the system.

- **A₂ (Cloud Administrator):** Has administrative access to the cloud platform hosting the TEE and storage systems. Can inspect VMs (except TEE internals), read cloud storage, and view network traffic.

- **A₃ (Network Attacker):** Can observe and potentially modify network traffic between clients and servers (man-in-the-middle).

- **A₄ (Malicious Participant):** Authenticated user attempting to access other users' datasets or inject malicious queries.

### 1.2 Security Goals

- **Confidentiality:** Plaintext dataset content is revealed only within the attested TEE.
- **Integrity:** Unauthorized modifications to datasets are detected.
- **Authenticity:** Only authorized users can upload datasets to sessions they participate in.
- **Attestation:** Clients verify TEE integrity before exposing sensitive data.
- **Session Isolation:** Datasets from different collaboration sessions cannot be cross-accessed, even within the TEE.
- **Forward Secrecy:** Compromise of long-term keys does not reveal past session data.

### 1.3 Trust Assumptions

- **Trusted TEE:** We trust that GCP Confidential Computing (AMD SEV-SNP) correctly isolates the TEE from the hypervisor and cloud administrator.
- **Client Software:** We assume the client (browser or CLI tool) correctly implements cryptographic operations.
- **Cryptographic Primitives:** We rely on the security of RSA-OAEP, AES-GCM, and SHA-256.

---

## 2. Protocol Overview

### 2.1 Participants

- **C (Client):** User's browser or command-line tool executing upload.
- **W (Web Server):** Control plane managing session metadata, user authentication, and workflows. Untrusted for data confidentiality.
- **T (TEE):** Confidential VM running attested code. Holds RSA keypair and session keys.
- **S (Storage):** Temporary or persistent storage accessible by TEE (in-memory or encrypted file system).

### 2.2 Protocol Phases

1. **Attestation Phase:** Client verifies TEE identity and obtains public key.
2. **Key Derivation Phase:** Client generates ephemeral AES key for data encryption.
3. **Upload Phase:** Client encrypts data and transmits to TEE.
4. **Processing Phase:** TEE decrypts, re-encrypts with session key, and stores.
5. **Notification Phase:** TEE notifies control plane of upload status (metadata only).

---

## 3. Cryptographic Primitives

### 3.1 Notation

- `||`: Concatenation operator
- `⊕`: XOR operation
- `H(·)`: SHA-256 hash function
- `HMAC-SHA256(k, m)`: HMAC using SHA-256
- `AES-GCM.Enc(k, iv, m, ad)`: AES-256-GCM encryption
- `AES-GCM.Dec(k, iv, c, ad)`: AES-256-GCM decryption
- `RSA-OAEP.Enc(pk, m)`: RSA-OAEP encryption with SHA-256
- `RSA-OAEP.Dec(sk, c)`: RSA-OAEP decryption
- `RSA-PSS.Sign(sk, m)`: RSA-PSS signature with SHA-256
- `RSA-PSS.Verify(pk, m, σ)`: RSA-PSS signature verification

### 3.2 Parameters

- **RSA Key Size:** 4096 bits (for long-term security)
- **AES Key Size:** 256 bits
- **AES-GCM IV Size:** 96 bits (12 bytes)
- **AES-GCM Tag Size:** 128 bits (16 bytes)
- **Hash Function:** SHA-256 (256-bit output)

### 3.3 Cryptographic Primitives Security

- **RSA-OAEP (RFC 8017):** Provides IND-CCA2 security under the RSA assumption.
- **AES-GCM (NIST SP 800-38D):** Provides authenticated encryption (IND-CCA2 + INT-CTXT).
- **RSA-PSS (RFC 8017):** Provides existential unforgeability under the RSA assumption.
- **HMAC-SHA256 (RFC 2104):** Provides MAC security under the PRF assumption of SHA-256.

---

## 4. Detailed Protocol Specification

### 4.1 Setup Phase (TEE Initialization)

**Performed once when TEE instance boots:**

1. **Keypair Generation:**
   ```
   (sk_T, pk_T) ← RSA.KeyGen(4096)
   ```
   Generate RSA-4096 keypair inside TEE. Private key `sk_T` never leaves TEE memory.

2. **Key Identifier:**
   ```
   kid_T ← H(DER(pk_T))[0:16]
   ```
   Compute key identifier as first 128 bits of SHA-256 hash of DER-encoded public key.

3. **Code Measurement:**
   ```
   μ_code ← H(code_binary)
   ```
   Compute SHA-256 hash of TEE service binary for attestation.

4. **Attestation Token Generation:**
   ```
   claims := {
     iss: "gcp-confidential-vm",
     sub: "tee-service",
     iat: current_time,
     exp: current_time + 1h,
     instance_id: T.instance_id,
     code_hash: μ_code,
     confidential_computing: true,
     secure_boot: true
   }
   
   τ_attest ← RSA-PSS.Sign(sk_T, JSON(claims))
   ```

**Invariants:**
- `sk_T` never serialized to disk or transmitted.
- `pk_T` exposed via `/public-key` endpoint.
- Attestation token `τ_attest` verifiable by clients.

---

### 4.2 Attestation Phase

**Goal:** Client verifies TEE integrity and obtains authentic public key.

**Step 1: Client requests attestation**
```
C → W: GET /api/tee/attestation-proxy
W → T: GET /attestation
T → W: {τ_attest, instance_id, timestamp}
W → C: {τ_attest, instance_id, timestamp}
```

**Step 2: Client verifies attestation**
```
claims ← JWT.Decode(τ_attest)
assert claims.code_hash = μ_expected  // Compare against known-good hash
assert claims.confidential_computing = true
assert claims.exp > current_time
assert RSA-PSS.Verify(pk_T, claims, τ_attest) = true
```

**Step 3: Client requests public key**
```
C → W: GET /api/tee/public-key-proxy
W → T: GET /public-key
T → W: {pk_T, kid_T, algorithm: "RSA-OAEP-SHA256"}
W → C: {pk_T, kid_T, algorithm: "RSA-OAEP-SHA256"}
```

**Step 4: Client validates public key binding**
```
kid_verify ← H(DER(pk_T))[0:16]
assert kid_verify = kid_T  // Ensure key matches claimed identifier
```

**Security Property:** By verifying `μ_code`, client ensures TEE is running trusted code. Attestation signature proves public key authenticity.

---

### 4.3 Dataset Encryption Phase (Client-Side)

**Input:**
- `D`: Dataset plaintext (arbitrary byte sequence)
- `pk_T`: TEE public key (verified)
- `dataset_id, session_id`: Metadata from web server

**Step 1: Generate ephemeral AES key**
```
k_data ← {0,1}^256  // Random 256-bit AES key
iv ← {0,1}^96        // Random 96-bit IV for AES-GCM
```

**Step 2: Encrypt dataset with AES-GCM**
```
AD ← dataset_id || session_id || H(D)  // Associated data for binding
C_data ← AES-GCM.Enc(k_data, iv, D, AD)
```

**Output:**
- `C_data`: Ciphertext (includes authentication tag)
- `iv`: Initialization vector
- `AD`: Associated data (for verification)

**Step 3: Encrypt AES key with RSA-OAEP**
```
C_key ← RSA-OAEP.Enc(pk_T, k_data)
```

**Step 4: Compute plaintext checksum**
```
ψ_D ← H(D)
```

**Step 5: Prepare upload payload**
```
Payload := {
  dataset_id: dataset_id,
  session_id: session_id,
  encrypted_data: Base64(C_data),
  encrypted_key: Base64(C_key),
  iv: Base64(iv),
  associated_data: Base64(AD),
  algorithm: "AES-256-GCM + RSA-OAEP-SHA256",
  filename: filename,
  file_size: |D|,
  checksum: ψ_D
}
```

**Security Properties:**
- **Hybrid Encryption:** Large dataset encrypted with fast AES; AES key protected with RSA.
- **Authenticated Encryption:** AES-GCM provides both confidentiality and integrity.
- **Associated Data Binding:** `AD` prevents ciphertext substitution attacks.
- **Ephemeral Key:** `k_data` used once and discarded (forward secrecy).

---

### 4.4 Secure Upload Phase

**Step 1: Client obtains upload token**
```
C → W: POST /sessions/{session_id}/datasets/upload
      Body: {name, description}
W: Verify C is participant in session_id
W: Create dataset record with status = PENDING
W: Generate JWT:
   token_claims := {
     dataset_id: dataset_id,
     session_id: session_id,
     user_id: C.user_id,
     exp: current_time + 1h
   }
   upload_token ← JWT.Sign(W.secret_key, token_claims)
W → C: {dataset_id, upload_token, tee_endpoint}
```

**Step 2: Client uploads directly to TEE**
```
C → T: POST /upload
       Headers: Authorization: Bearer upload_token
       Body: Payload
```

**Security Properties:**
- **Direct Upload:** Ciphertext bypasses web server `W` (untrusted).
- **Time-Limited Authorization:** `upload_token` expires in 1 hour.
- **Authentication:** JWT signature prevents unauthorized uploads.

---

### 4.5 TEE Processing Phase

**Input:** `Payload` from client

**Step 1: Verify upload token**
```
claims ← JWT.Verify(W.secret_key, upload_token)
assert claims.exp > current_time
assert claims.dataset_id = Payload.dataset_id
assert claims.session_id = Payload.session_id
```

**Step 2: Decrypt AES key**
```
C_key ← Base64.Decode(Payload.encrypted_key)
k_data ← RSA-OAEP.Dec(sk_T, C_key)
```

**Step 3: Decrypt dataset**
```
C_data ← Base64.Decode(Payload.encrypted_data)
iv ← Base64.Decode(Payload.iv)
AD ← Base64.Decode(Payload.associated_data)
D ← AES-GCM.Dec(k_data, iv, C_data, AD)
```

If decryption fails (authentication tag mismatch), abort with error.

**Step 4: Verify checksum**
```
ψ_verify ← H(D)
assert ψ_verify = Payload.checksum
```

**Step 5: Derive session-specific key**
```
if session_id ∉ K_sessions:
    K_sessions[session_id] ← {0,1}^256  // Generate new session key
k_session ← K_sessions[session_id]
```

**Step 6: Re-encrypt with session key**
```
iv_session ← {0,1}^96
AD_session ← session_id || dataset_id || "v1"
C_session ← AES-GCM.Enc(k_session, iv_session, D, AD_session)
```

**Step 7: Store encrypted dataset**
```
DATASETS[dataset_id] ← {
  session_id: session_id,
  encrypted_data: C_session,
  iv: iv_session,
  associated_data: AD_session,
  checksum: ψ_verify,
  file_size: |D|,
  uploaded_at: timestamp
}
```

**Step 8: Securely erase sensitive data**
```
memset(k_data, 0, |k_data|)  // Overwrite AES key
memset(D, 0, |D|)            // Overwrite plaintext
```

**Step 9: Notify control plane**
```
T → W: POST /api/tee/callback
       Body: {
         entity_type: "dataset",
         entity_id: dataset_id,
         status: "available",
         metadata: {checksum: ψ_verify, file_size: |D|}
       }
```

**Security Properties:**
- **Re-encryption:** Session key `k_session` provides isolation between collaborations.
- **Memory Safety:** Plaintext `D` and ephemeral key `k_data` explicitly zeroed.
- **Metadata-Only Callback:** Web server `W` learns only upload status, not data.

---

### 4.6 Session Key Derivation

**Purpose:** Ensure datasets from different sessions cannot be cross-accessed, even within TEE.

**Key Lifecycle:**
1. **Generation:** Session key generated when first dataset uploaded to session.
2. **Storage:** Held in TEE volatile memory only (not persisted).
3. **Usage:** All datasets in session encrypted under same `k_session`.
4. **Deletion:** Key erased when session closed or TEE restarts.

**Key Derivation (Optional Enhancement):**
```
k_session ← HKDF-SHA256(
  IKM: master_secret || session_id,
  Salt: "session-key-v1",
  Info: session_id || creation_timestamp
)
```

Where `master_secret` is a TEE-local secret generated at boot.

**Security Property:** Session keys are computationally independent. Compromise of one session key does not affect others.

---

## 5. Security Analysis

### 5.1 Confidentiality Against A₁ (Web Server)

**Claim:** Web server `W` learns no information about plaintext `D`.

**Proof Sketch:**
- Client encrypts `D` before transmission. Web server sees only `C_data` and `C_key`.
- Under IND-CCA2 security of RSA-OAEP and AES-GCM, ciphertexts reveal no information about plaintexts.
- Web server lacks `sk_T` to decrypt `C_key` and thus cannot recover `k_data` or `D`.
- Metadata leaked: `|D|`, upload time, `dataset_id`, `session_id`. These are considered non-sensitive.

**Conclusion:** ✓ Confidentiality preserved against A₁.

---

### 5.2 Confidentiality Against A₂ (Cloud Administrator)

**Claim:** Cloud administrator cannot access plaintext `D` without breaking TEE guarantees.

**Proof Sketch:**
- Data encrypted client-side. Cloud storage (if used) contains only `C_data`.
- Private key `sk_T` and session keys `k_session` reside in TEE memory, protected by hardware isolation (AMD SEV-SNP).
- Administrator cannot dump TEE memory or execute arbitrary code in TEE without detection (attestation would fail).
- Even if administrator captures network traffic, they see only ciphertexts.

**Attack Vector:** Memory dumping or VM snapshotting. **Mitigation:** Confidential Computing prevents hypervisor access to TEE memory.

**Conclusion:** ✓ Confidentiality preserved assuming TEE integrity.

---

### 5.3 Integrity Against A₃ (Network Attacker)

**Claim:** Network attacker cannot undetectably modify ciphertexts.

**Proof Sketch:**
- AES-GCM provides INT-CTXT security (integrity of ciphertexts). Any modification to `C_data` causes decryption to fail.
- Associated data `AD` binds `dataset_id` and `session_id` to ciphertext, preventing substitution.
- RSA-OAEP does not provide explicit integrity, but `k_data` is protected by AES-GCM authentication.

**Attack Vector:** Replay attack (resending old valid ciphertext). **Mitigation:** Upload tokens are time-limited. TEE can additionally track used `(dataset_id, upload_token)` pairs.

**Conclusion:** ✓ Integrity preserved with caveat on replay prevention.

---

### 5.4 Session Isolation Against A₄ (Malicious Participant)

**Claim:** Participant in session S₁ cannot access datasets from session S₂.

**Proof Sketch:**
- Each session has independent key `k_session`.
- TEE enforces access control: query execution in session S₁ can only decrypt datasets with `session_id = S₁`.
- Session keys never exposed outside TEE.

**Attack Vector:** Malicious query attempting to leak data. **Mitigation:** Query sandboxing and result auditing (out of scope for this protocol).

**Conclusion:** ✓ Session isolation enforced cryptographically.

---

### 5.5 Forward Secrecy

**Claim:** Compromise of `sk_T` at time `t` does not reveal datasets uploaded before `t`.

**Proof Analysis:**
- **Partial Forward Secrecy:** If session keys `k_session` are deleted after session closes, past datasets are protected.
- **Weakness:** Ephemeral key `k_data` can be recovered if `sk_T` is compromised and attacker captured `C_key` earlier.

**Enhancement:** Use Diffie-Hellman key exchange for `k_data` instead of RSA encryption. Client and TEE perform ECDH, derive `k_data` from shared secret. Neither side transmits `k_data` encrypted.

**Conclusion:** ⚠️ Partial forward secrecy. Full forward secrecy requires protocol modification.

---

## 6. Implementation Considerations

### 6.1 Cryptographic Libraries

**Client (Browser/JavaScript):**
- **Web Crypto API:** Use `SubtleCrypto` for AES-GCM and RSA-OAEP.
- **Key Import:**
  ```javascript
  const publicKey = await crypto.subtle.importKey(
    "spki",
    pemToArrayBuffer(pk_T),
    {name: "RSA-OAEP", hash: "SHA-256"},
    false,
    ["encrypt"]
  );
  ```

**TEE (Python):**
- **Library:** `cryptography` (maintained by Python Cryptographic Authority)
- **Example:**
  ```python
  from cryptography.hazmat.primitives.asymmetric import padding
  from cryptography.hazmat.primitives import hashes
  
  k_data = private_key.decrypt(
      C_key,
      padding.OAEP(
          mgf=padding.MGF1(algorithm=hashes.SHA256()),
          algorithm=hashes.SHA256(),
          label=None
      )
  )
  ```

### 6.2 Key Sizes and Performance

**RSA-4096:**
- **Encryption Time:** ~10ms per key wrap (client-side)
- **Decryption Time:** ~50ms per key wrap (TEE-side)
- **Justification:** Provides ~128-bit security against quantum adversaries (post-quantum consideration).

**AES-256-GCM:**
- **Throughput:** ~500 MB/s (hardware-accelerated AES-NI)
- **Latency:** Negligible for datasets < 100 MB

**Trade-off:** RSA key wrap adds minimal overhead due to small key size (32 bytes).

### 6.3 Error Handling

**Client-Side:**
- **Encryption Failure:** Notify user, do not proceed.
- **Upload Failure:** Retry with exponential backoff (max 3 attempts).

**TEE-Side:**
- **Decryption Failure:** Log error, notify control plane with `status = "failed"`.
- **Token Expiry:** Reject upload, return 401 Unauthorized.

### 6.4 Attestation Verification

**Production Requirements:**
- Verify RSA-PSS signature on attestation token.
- Check `code_hash` against whitelist of approved TEE binaries.
- Validate `confidential_computing = true` and `secure_boot = true`.
- Ensure attestation timestamp is recent (< 5 minutes old).

**Known Limitations:**
- Current implementation uses self-signed attestation. Production should integrate GCP Confidential Computing attestation APIs.

---

## 7. Formal Security Properties (Summary)

| Property | Adversary | Security Mechanism | Formal Model |
|----------|-----------|-------------------|--------------|
| **Data Confidentiality** | A₁, A₂, A₃ | AES-GCM + RSA-OAEP | IND-CCA2 |
| **Data Integrity** | A₃ | AES-GCM authentication | INT-CTXT |
| **Upload Authorization** | A₄ | JWT + time-limited tokens | EUF-CMA (HMAC) |
| **TEE Authenticity** | A₃ | Attestation + RSA-PSS | EUF-CMA (RSA-PSS) |
| **Session Isolation** | A₄ | Independent `k_session` | Computational independence |
| **Forward Secrecy** | A₂ (future) | Ephemeral keys + key deletion | Partial (see §5.5) |

**Formal Verification:** Future work should mechanize security proofs in frameworks like ProVerif or EasyCrypt.

---

## 8. Protocol Extensions

### 8.1 Multi-Recipient Encryption

**Scenario:** Dataset accessible to multiple TEE instances (e.g., federated learning across multiple clouds).

**Approach:**
- Encrypt `k_data` multiple times under each TEE's public key.
- Include all `C_key` values in upload payload.

**Modification:**
```
for each pk_i in TEE_public_keys:
    C_key_i ← RSA-OAEP.Enc(pk_i, k_data)
Payload.encrypted_keys ← [C_key_1, ..., C_key_n]
```

### 8.2 Differential Privacy Integration

**Scenario:** Query results must be differentially private.

**Approach:**
- TEE adds calibrated noise to query results before encryption.
- Noise parameters specified in query approval metadata.

**Cryptographic Impact:** None. Differential privacy operates on plaintext results before re-encryption.

### 8.3 Blockchain-Based Audit Log

**Scenario:** Immutable audit trail of dataset uploads and queries.

**Approach:**
- TEE logs hash of each operation to blockchain (e.g., Ethereum or Hyperledger).
- Log entry: `H(dataset_id || session_id || checksum || timestamp)`.

**Benefit:** Tamper-evident history for compliance and forensics.

---

## 9. Comparison with Alternative Protocols

| Protocol | Key Exchange | Data Encryption | Trust Model | Performance |
|----------|--------------|-----------------|-------------|-------------|
| **Ours (RSA + AES-GCM)** | RSA-OAEP | AES-256-GCM | TEE-based | High (hybrid) |
| **TLS 1.3** | ECDHE | AES-GCM | CA + Server | High |
| **PGP/GPG** | RSA/ECDH | AES-CFB | Web of Trust | Medium |
| **Signal Protocol** | X3DH + Double Ratchet | AES-CBC + HMAC | Forward secrecy | High |
| **Homomorphic Encryption** | N/A | FHE schemes | No TEE needed | Very Low |

**Advantages of Our Protocol:**
- **Hardware-backed trust:** TEE attestation provides stronger guarantees than software-only solutions.
- **Performance:** Hybrid encryption avoids computational overhead of FHE.
- **Simplicity:** No complex key ratcheting; session keys provide adequate isolation.

**Disadvantages:**
- **TEE Dependency:** Security relies on confidential computing hardware.
- **Limited Forward Secrecy:** Requires enhancement for full forward secrecy.

---

## 10. Deployment Checklist

### 10.1 TEE Server Deployment

- [ ] Deploy TEE server code to GCP Confidential Computing instance (AMD SEV-SNP).
- [ ] Generate RSA-4096 keypair on TEE boot (store in volatile memory only).
- [ ] Expose `/public-key` and `/upload` endpoints with CORS support.
- [ ] Configure `CONTROL_PLANE_URL` for status callbacks.
- [ ] Enable structured logging for audit trails.
- [ ] Set up monitoring for decryption failures (potential attacks).

### 10.2 Client Application

- [ ] Implement attestation verification (check `code_hash`, signature).
- [ ] Use Web Crypto API for encryption (do not use JS libraries without auditing).
- [ ] Display attestation details to user before upload (informed consent).
- [ ] Handle upload failures gracefully (retry logic).
- [ ] Securely erase `k_data` from client memory after upload.

### 10.3 Control Plane (Web Server)

- [ ] Never log or store ciphertext or encryption keys.
- [ ] Implement rate limiting on upload token generation (prevent DoS).
- [ ] Validate JWT signatures on callbacks from TEE.
- [ ] Use TLS 1.3 for all connections (defense in depth).

### 10.4 Monitoring & Alerts

- [ ] **Alert:** Attestation verification failures (potential compromised TEE).
- [ ] **Alert:** Decryption errors (malformed ciphertext or attack).
- [ ] **Metric:** Upload latency (detect performance regressions).
- [ ] **Metric:** Dataset sizes (capacity planning).

---

## 11. Open Questions and Future Work

1. **Post-Quantum Cryptography:** Evaluate replacing RSA-OAEP with CRYSTALS-Kyber (NIST PQC standard).
2. **Full Forward Secrecy:** Implement ECDH-based key exchange to eliminate RSA key wrap.
3. **Formal Verification:** Mechanize proofs in CryptoVerif or Tamarin.
4. **Multi-TEE Federation:** Extend protocol for cross-cloud secure computation.
5. **Hardware Attestation:** Integrate GCP Shielded VM attestation for stronger guarantees.
6. **Result Decryption:** Specify protocol for securely delivering query results to clients (symmetric extension).

---

## 12. References

1. **Confidential Computing Consortium.** *Confidential Computing: Hardware-Based Trusted Execution for Applications and Data.* 2023.
2. **Costan, V., & Devadas, S.** *Intel SGX Explained.* IACR Cryptology ePrint Archive, 2016.
3. **AMD.** *AMD SEV-SNP: Strengthening VM Isolation with Integrity Protection.* White Paper, 2020.
4. **Bellare, M., & Rogaway, P.** *Optimal Asymmetric Encryption.* EUROCRYPT 1994.
5. **McGrew, D., & Viega, J.** *The Galois/Counter Mode of Operation (GCM).* NIST SP 800-38D, 2007.
6. **Jonsson, J., & Kaliski, B.** *Public-Key Cryptography Standards (PKCS) #1: RSA Cryptography Specifications Version 2.2.* RFC 8017, 2016.
7. **Goldreich, O.** *Foundations of Cryptography: Volume 2, Basic Applications.* Cambridge University Press, 2004.
8. **Katz, J., & Lindell, Y.** *Introduction to Modern Cryptography.* 3rd Edition, CRC Press, 2020.

---

## Appendix A: Notation Reference

| Symbol | Meaning |
|--------|---------|
| `C` | Client |
| `W` | Web Server (Control Plane) |
| `T` | Trusted Execution Environment (TEE) |
| `D` | Dataset plaintext |
| `pk_T`, `sk_T` | TEE's RSA public/private keypair |
| `k_data` | Ephemeral AES key for dataset encryption |
| `k_session` | Session-specific AES key (TEE-internal) |
| `C_data` | AES-GCM ciphertext of dataset |
| `C_key` | RSA-OAEP ciphertext of AES key |
| `iv` | Initialization vector (nonce) |
| `AD` | Associated data for authenticated encryption |
| `τ_attest` | Attestation token (JWT) |
| `μ_code` | Code measurement hash |
| `ψ_D` | Dataset checksum |
| `H(·)` | SHA-256 hash function |

---

## Appendix B: Example Attack Scenarios

### B.1 Ciphertext Substitution Attack

**Scenario:** Attacker replaces `C_data` with ciphertext from different dataset.

**Defense:**
- Associated data `AD` includes `dataset_id` and `H(D)`.
- AES-GCM decryption fails if `AD` doesn't match.

**Result:** Attack detected.

### B.2 Replay Attack

**Scenario:** Attacker captures legitimate upload and replays it.

**Defense:**
- Upload tokens expire (1 hour).
- TEE can track used `(dataset_id, token)` pairs (optional).

**Result:** Replayed upload rejected after token expiry.

### B.3 Key Extraction via Side Channels

**Scenario:** Attacker uses power analysis or timing attacks to extract `sk_T`.

**Defense:**
- AMD SEV-SNP provides encrypted memory and register state.
- Use constant-time cryptographic implementations.

**Result:** Attack mitigated by hardware isolation.

---

**Document Status:** Draft for Review  
**Next Review Date:** 2025-12-31  
**Contact:** security@permissible.ai

---

*This protocol specification is intended for cryptographers, security engineers, and compliance auditors. For implementation guides, refer to companion documents: `TEE_PUBLIC_KEY_UPDATE.py` and `SECURE_UPLOAD_PROTOCOL.md`.*
