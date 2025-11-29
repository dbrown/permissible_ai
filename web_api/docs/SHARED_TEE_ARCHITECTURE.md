# Shared TEE Architecture

## Overview

The system has been refactored to use a **single shared Trusted Execution Environment (TEE)** instead of spinning up individual VMs per collaboration session. This provides significant benefits:

### Benefits

✅ **Dramatically Lower Costs**
- One long-running Confidential VM instead of many
- No VM startup/shutdown overhead
- Efficient resource utilization

✅ **Reduced Complexity**  
- No VM lifecycle management per session
- Simpler deployment and operations
- Easier monitoring and maintenance

✅ **Better Performance**
- No VM startup latency (2-5 minutes eliminated)
- Immediate session creation
- Faster query execution

✅ **Improved Security**
- Single attestation to verify and monitor
- Centralized security controls
- Easier compliance auditing

## Architecture

### Before: Per-Session TEE VMs

```
Session 1 → Confidential VM 1 (dedicated)
Session 2 → Confidential VM 2 (dedicated)  
Session 3 → Confidential VM 3 (dedicated)
```

**Problems:**
- Expensive: N sessions = N VMs
- Slow: 2-5 min VM startup per session
- Complex: VM lifecycle management

### After: Shared TEE Service

```
Session 1 ──┐
Session 2 ──┼──→ Shared Confidential VM (single)
Session 3 ──┘
```

**Advantages:**
- Cost: 1 VM for all sessions
- Fast: Instant session creation
- Simple: No VM management

## How It Works

### Trust Model

Security comes from:

1. **Attestation**: The shared TEE proves it's running trusted code in a confidential environment
2. **Encryption**: All data is encrypted; only authorized users can decrypt results
3. **Multi-tenancy**: Sessions are logically isolated within the shared TEE
4. **Access Control**: Query approval workflows enforce policy

The TEE doesn't need to be "owned" by specific users - it just needs to prove it's executing trusted code.

### Components

#### 1. Collaboration Sessions (formerly "TEEs")

Collaboration sessions are now lightweight database records that:
- Track participants and permissions
- Store configuration (cross-party joins, approval requirements)
- Reference datasets and queries
- Don't map to physical VMs

**Database changes:**
- `tees` table renamed to `collaboration_sessions`
- Removed: `gcp_project_id`, `gcp_zone`, `gcp_instance_id`, `attestation_token`
- Added: `closed_at` (replaces `terminated_at`)
- Status: `CREATING` removed (instant activation), `TERMINATED` → `CLOSED`

#### 2. Shared TEE Service

A single GCP Confidential VM that:
- Runs continuously (long-lived service)
- Provides attestation tokens on demand
- Executes queries for all sessions
- Enforces multi-tenant isolation

**Configuration:**
```bash
# Environment variables
TEE_SERVICE_ENDPOINT=https://tee.example.com  # Shared TEE endpoint
TEE_INSTANCE_ID=shared-tee-001                # Shared instance identifier
```

#### 3. GCP Service Layer

Updated to interact with shared TEE:
- `get_shared_tee_attestation()`: Fetch attestation from shared service
- `execute_query()`: Submit queries with session_id for isolation
- Removed: `create_confidential_vm()`, `terminate_instance()`

## API Changes

### Endpoint Updates

**Old:**
```
POST /api/tee/environments      # Create TEE (provisions VM)
GET  /api/tee/environments      # List TEEs
DELETE /api/tee/environments/:id # Delete TEE (terminates VM)
```

**New:**
```
POST /api/tee/sessions          # Create session (instant)
GET  /api/tee/sessions          # List sessions
DELETE /api/tee/sessions/:id    # Close session (no VM termination)
```

### Request Changes

**Creating a session (simplified):**

Before:
```json
{
  "name": "Research Project",
  "gcp_project_id": "my-project",    // ❌ Not needed
  "gcp_zone": "us-central1-a",       // ❌ Not needed
  "participant_emails": [...]
}
```

After:
```json
{
  "name": "Research Project",
  "participant_emails": [...]         // ✅ Just the essentials
}
```

## Migration Guide

### Database Migration

Run the migration script:

```bash
cd /Users/dbrown/Development/permissible/web_api
python scripts/migrations/migrate_to_shared_tee.py
```

This will:
1. Rename `tees` → `collaboration_sessions`
2. Remove VM-specific columns
3. Update status values
4. Update foreign keys

### Configuration

Set environment variables:

```bash
# Shared TEE configuration
export TEE_SERVICE_ENDPOINT="http://localhost:8080"
export TEE_INSTANCE_ID="shared-tee-001"

# Existing GCP config still needed for storage/KMS
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
```

### Deploying Shared TEE

The shared TEE service needs to be deployed once:

1. **Create Confidential VM:**
```bash
gcloud compute instances create shared-tee-001 \
  --zone=us-central1-a \
  --machine-type=n2d-standard-4 \
  --confidential-compute \
  --maintenance-policy=TERMINATE \
  --boot-disk-size=50GB \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud
```

2. **Install TEE Runtime:**
- Python query executor
- Attestation service
- Multi-tenant isolation

3. **Start Service:**
```bash
# On the TEE VM
python3 /opt/tee-runtime/service.py --port 8080
```

### Code Updates Required

Update client code:

**Before:**
```python
# Old: Create TEE per session
response = requests.post('/api/tee/environments', json={
    'name': 'My TEE',
    'gcp_project_id': 'project',
    'gcp_zone': 'us-central1-a'
})
```

**After:**
```python
# New: Create lightweight session
response = requests.post('/api/tee/sessions', json={
    'name': 'My Session'
})
```

## Security Considerations

### Attestation

The shared TEE provides attestation tokens that prove:
- Code integrity (running approved software)
- Confidential computing enabled
- Secure boot and vTPM active
- Instance identity

Users verify this attestation before uploading data.

### Multi-Tenant Isolation

The shared TEE enforces isolation between sessions:
- **Process isolation**: Separate execution contexts per session
- **Data encryption**: Session-specific KMS keys
- **Access control**: Query results only to authorized participants
- **Audit logging**: All operations tracked by session_id

### Trust Boundaries

```
[User A Data] --encrypted--> [Shared TEE] --encrypted--> [User A Results]
[User B Data] --encrypted--> [Shared TEE] --encrypted--> [User B Results]
                                   ↑
                            Verified Attestation
```

Users trust:
1. The attestation (TEE is genuine)
2. The code running in TEE (audited)
3. Encryption (only they can decrypt their results)

They don't need to trust:
- Other users
- The platform operator (can't see plaintext)

## Cost Analysis

### Before: Per-Session VMs

```
Cost per VM: $0.20/hour (n2d-standard-4)
10 sessions x 8 hours/day = $16/day
Monthly: ~$480
```

### After: Shared TEE

```
Cost: 1 VM x 24 hours x 30 days = $144/month
Savings: 70% reduction (at 10 concurrent sessions)
```

Savings increase with more sessions!

## Performance Comparison

| Operation | Before (Per-Session) | After (Shared) | Improvement |
|-----------|---------------------|----------------|-------------|
| Create Session | 2-5 minutes | <1 second | 99% faster |
| Query Execution | Same | Same | No change |
| Resource Usage | N VMs | 1 VM | N:1 reduction |

## Monitoring

### Shared TEE Health

Monitor:
- Attestation validity (refresh every 24h)
- Service uptime
- Query execution queue
- Resource utilization

### Alerts

Set up alerts for:
- Attestation verification failures
- Service downtime
- High query latency
- Memory/CPU thresholds

## Future Enhancements

Possible improvements:
1. **Auto-scaling**: Multiple shared TEEs behind load balancer
2. **Regional deployment**: TEEs in multiple zones for redundancy
3. **Query optimization**: Caching, query planning
4. **Enhanced isolation**: Hardware enclaves (SGX/SEV-SNP)

## Troubleshooting

### Session Creation Fails

```bash
# Check shared TEE is running
curl $TEE_SERVICE_ENDPOINT/health

# Verify attestation
curl $TEE_SERVICE_ENDPOINT/attestation
```

### Attestation Verification Fails

```bash
# Check TEE instance ID matches
echo $TEE_INSTANCE_ID

# Regenerate attestation
ssh shared-tee-001 "python3 /opt/tee-runtime/generate_attestation.py"
```

### Query Execution Hangs

```bash
# Check TEE service logs
ssh shared-tee-001 "journalctl -u tee-service -f"

# Monitor query queue
curl $TEE_SERVICE_ENDPOINT/status
```

## References

- [GCP Confidential Computing](https://cloud.google.com/confidential-computing)
- [TEE Implementation Summary](./TEE_IMPLEMENTATION_SUMMARY.md)
- [API Documentation](./api/tee.md)
