# TEE API Documentation

## Overview

The Trusted Execution Environment (TEE) API enables multiple parties to securely collaborate on sensitive data analysis using Google Cloud Platform's Confidential Computing. The API provides:

- **Multi-party data collaboration** without exposing raw data
- **TEE attestation verification** to ensure secure execution
- **Query verification workflow** to prevent privacy violations
- **Encrypted dataset management** with KMS integration
- **Results distribution** to all authorized parties

## Authentication

All TEE API endpoints require API key authentication. Include your API key in one of three ways:

```bash
# Authorization header (recommended)
curl -H "Authorization: Bearer YOUR_API_KEY" https://api.example.com/api/tee/...

# X-API-Key header
curl -H "X-API-Key: YOUR_API_KEY" https://api.example.com/api/tee/...

# Query parameter (less secure)
curl https://api.example.com/api/tee/...?api_key=YOUR_API_KEY
```

## Base URL

All TEE endpoints are prefixed with `/api/tee`

## Core Concepts

### Trusted Execution Environment (TEE)
A secure, isolated compute environment running on GCP Confidential VMs where data processing occurs. No participant can access raw data from other parties.

### Dataset
Encrypted data uploaded by a participant. Each dataset is encrypted with GCP KMS and only accessible within the TEE.

### Query
A data analysis operation submitted for execution. Queries must be approved by participants whose data they access.

### Results
Outputs from executed queries, distributed to all TEE participants.

---

## API Endpoints

### TEE Management

#### List TEEs
```http
GET /api/tee/environments
```

Returns all TEEs where the authenticated user is creator or participant.

**Response:**
```json
{
  "tees": [
    {
      "id": 1,
      "name": "Healthcare Research Collaboration",
      "description": "Multi-hospital patient outcomes study",
      "creator": {
        "id": 5,
        "email": "researcher@hospital-a.org",
        "name": "Dr. Alice"
      },
      "gcp_instance_id": "tee-1-healthcare-research",
      "attestation_verified": true,
      "attestation_verified_at": "2024-11-28T10:30:00Z",
      "status": "active",
      "participants": [
        {"id": 5, "email": "researcher@hospital-a.org", "name": "Dr. Alice"},
        {"id": 7, "email": "analyst@hospital-b.org", "name": "Dr. Bob"}
      ],
      "allow_cross_party_joins": true,
      "require_unanimous_approval": true,
      "created_at": "2024-11-28T09:00:00Z",
      "activated_at": "2024-11-28T10:30:00Z",
      "dataset_count": 3,
      "query_count": 5
    }
  ]
}
```

#### Create TEE
```http
POST /api/tee/environments
```

Create a new Trusted Execution Environment.

**Request Body:**
```json
{
  "name": "Financial Analysis TEE",
  "description": "Cross-bank fraud detection study",
  "gcp_project_id": "my-gcp-project",
  "gcp_zone": "us-central1-a",
  "allow_cross_party_joins": true,
  "require_unanimous_approval": true,
  "participant_emails": ["analyst@bank-b.com", "researcher@bank-c.com"]
}
```

**Response:** `201 Created`
```json
{
  "tee": { /* TEE object */ },
  "message": "TEE creation initiated"
}
```

#### Get TEE Details
```http
GET /api/tee/environments/{tee_id}
```

**Response:**
```json
{
  "tee": { /* Complete TEE object */ }
}
```

#### Verify TEE Attestation
```http
POST /api/tee/environments/{tee_id}/attestation
```

Verify the TEE's attestation token to ensure it's running in a genuine Confidential VM. Only the TEE creator can perform this action.

**Request Body:**
```json
{
  "attestation_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "message": "Attestation verified successfully",
  "tee": { /* Updated TEE object with attestation_verified: true */ }
}
```

#### Add Participant
```http
POST /api/tee/environments/{tee_id}/participants
```

Add a new participant to the TEE. Only the creator can add participants.

**Request Body:**
```json
{
  "email": "newuser@organization.com"
}
```

**Response:**
```json
{
  "message": "Added newuser@organization.com as participant",
  "tee": { /* Updated TEE object */ }
}
```

#### Terminate TEE
```http
POST /api/tee/environments/{tee_id}/terminate
```

Terminate the TEE and shut down the Confidential VM. Only the creator can terminate.

**Response:**
```json
{
  "message": "TEE terminated successfully",
  "tee": { /* Updated TEE object with status: "terminated" */ }
}
```

---

### Dataset Management

#### List Datasets
```http
GET /api/tee/environments/{tee_id}/datasets
```

List all datasets in a TEE.

**Response:**
```json
{
  "datasets": [
    {
      "id": 1,
      "tee_id": 1,
      "name": "Hospital A Patient Data",
      "description": "De-identified patient records Q4 2024",
      "owner": {
        "id": 5,
        "email": "researcher@hospital-a.org",
        "name": "Dr. Alice"
      },
      "schema": {
        "columns": [
          {"name": "patient_id", "type": "string"},
          {"name": "diagnosis_code", "type": "string"},
          {"name": "treatment_outcome", "type": "string"},
          {"name": "age_group", "type": "string"}
        ]
      },
      "file_size_bytes": 52428800,
      "row_count": 15000,
      "status": "available",
      "uploaded_at": "2024-11-28T09:15:00Z",
      "available_at": "2024-11-28T09:45:00Z"
    }
  ]
}
```

#### Upload Dataset
```http
POST /api/tee/environments/{tee_id}/datasets
```

Initiate upload of a dataset to the TEE.

**Request Body:**
```json
{
  "name": "Quarterly Sales Data",
  "description": "Q4 2024 sales transactions",
  "schema": {
    "columns": [
      {"name": "transaction_id", "type": "string"},
      {"name": "amount", "type": "float"},
      {"name": "category", "type": "string"},
      {"name": "timestamp", "type": "datetime"}
    ]
  },
  "gcs_bucket": "my-company-datasets",
  "gcs_path": "sales/2024-q4.csv"
}
```

**Response:** `201 Created`
```json
{
  "dataset": { /* Dataset object */ },
  "message": "Dataset upload initiated"
}
```

**Process:**
1. Dataset record created with status `uploading`
2. Data is encrypted using GCP KMS
3. Encrypted data transferred to TEE storage
4. Status changes to `encrypted`, then `available`

#### Get Dataset Details
```http
GET /api/tee/datasets/{dataset_id}
```

**Response:**
```json
{
  "dataset": { /* Complete dataset object */ }
}
```

#### Mark Dataset Available
```http
POST /api/tee/datasets/{dataset_id}/mark-available
```

Manually mark a dataset as available (owner or admin only).

**Response:**
```json
{
  "message": "Dataset marked as available",
  "dataset": { /* Updated dataset */ }
}
```

---

### Query Management

#### List Queries
```http
GET /api/tee/environments/{tee_id}/queries
```

List all queries in a TEE.

**Response:**
```json
{
  "queries": [
    {
      "id": 1,
      "tee_id": 1,
      "name": "Cross-hospital readmission analysis",
      "description": "Calculate 30-day readmission rates by diagnosis",
      "submitter": {
        "id": 5,
        "email": "researcher@hospital-a.org",
        "name": "Dr. Alice"
      },
      "accesses_datasets": [1, 2],
      "privacy_level": "aggregate_only",
      "status": "completed",
      "submitted_at": "2024-11-28T11:00:00Z",
      "approved_at": "2024-11-28T11:30:00Z",
      "executed_at": "2024-11-28T11:35:00Z",
      "completed_at": "2024-11-28T11:45:00Z",
      "execution_time_seconds": 285.3
    }
  ]
}
```

#### Submit Query
```http
POST /api/tee/environments/{tee_id}/queries
```

Submit a query for execution in the TEE.

**Request Body:**
```json
{
  "name": "Revenue by Region",
  "description": "Calculate total revenue aggregated by customer region",
  "query_text": "SELECT region, SUM(amount) as total_revenue FROM dataset_1 JOIN dataset_2 ON dataset_1.customer_id = dataset_2.customer_id GROUP BY region",
  "accesses_datasets": [1, 2],
  "privacy_level": "aggregate_only"
}
```

**Response:** `201 Created`
```json
{
  "query": { /* Query object with status: "submitted" */ },
  "message": "Query submitted for verification",
  "requires_approval": true,
  "participants_to_approve": 3
}
```

**Privacy Levels:**
- `aggregate_only` - Only returns aggregated statistics
- `k_anonymized` - Returns data with k-anonymity guarantees
- `differential_privacy` - Applies differential privacy mechanisms
- `full_access` - Returns detailed results (requires stronger approval)

#### Get Query Details
```http
GET /api/tee/queries/{query_id}
```

**Response:**
```json
{
  "query": { /* Complete query object including query_text */ }
}
```

#### Approve Query
```http
POST /api/tee/queries/{query_id}/approve
```

Approve a query for execution. Participants whose datasets are accessed must approve.

**Request Body:**
```json
{
  "notes": "Verified - query only returns aggregated data, no individual records"
}
```

**Response:**
```json
{
  "message": "Query approved and execution started",
  "query": { /* Updated query with status: "executing" */ }
}
```

#### Reject Query
```http
POST /api/tee/queries/{query_id}/reject
```

Reject a query to prevent execution.

**Request Body:**
```json
{
  "reason": "Query accesses raw PII data without sufficient anonymization"
}
```

**Response:**
```json
{
  "message": "Query rejected",
  "query": { /* Updated query with status: "rejected" */ }
}
```

---

### Results Distribution

#### Get Query Results
```http
GET /api/tee/queries/{query_id}/results
```

Retrieve results from a completed query. Available to all TEE participants.

**Response:**
```json
{
  "query": { /* Query object */ },
  "results": [
    {
      "id": 1,
      "query_id": 1,
      "result_format": "json",
      "row_count": 50,
      "file_size_bytes": 8192,
      "created_at": "2024-11-28T11:45:00Z",
      "result_data": {
        "columns": ["region", "total_revenue"],
        "rows": [
          ["North", 1500000.00],
          ["South", 2300000.00],
          ["East", 1800000.00],
          ["West", 2100000.00]
        ]
      }
    }
  ]
}
```

#### Download Result File
```http
GET /api/tee/queries/{query_id}/results/{result_id}/download
```

Get a signed URL to download large result files.

**Response:**
```json
{
  "download_url": "https://storage.googleapis.com/results/query-1-result.csv?X-Goog-Expires=...",
  "expires_in_seconds": 3600,
  "file_size_bytes": 52428800,
  "format": "csv"
}
```

---

## Query Lifecycle

```
SUBMITTED → VERIFYING → APPROVED → EXECUTING → COMPLETED
                      ↓
                  REJECTED
```

1. **SUBMITTED** - Query created, awaiting participant review
2. **VERIFYING** - Participants reviewing query for privacy compliance
3. **APPROVED** - All required approvals received
4. **REJECTED** - One or more participants rejected
5. **EXECUTING** - Running in TEE
6. **COMPLETED** - Results available
7. **ERROR** - Execution failed

## Dataset Lifecycle

```
UPLOADING → UPLOADED → ENCRYPTED → AVAILABLE
```

## TEE Status Values

- `creating` - GCP Confidential VM being provisioned
- `active` - Running and accepting queries
- `suspended` - Temporarily paused
- `terminated` - Shut down
- `error` - Creation or operation failed

## Security Considerations

### Attestation
Always verify TEE attestation before uploading sensitive data. Attestation proves:
- Code running in genuine Confidential VM
- Boot integrity verified
- Memory encrypted with AMD SEV or Intel TDX

### Query Approval
The `require_unanimous_approval` setting determines approval requirements:
- `true` - ALL participants must approve
- `false` - Only dataset owners must approve

### Data Access
- Participants can only see aggregated results, not raw data
- Each query specifies which datasets it accesses
- Dataset owners control their data access

### Encryption
- All datasets encrypted at rest with GCP KMS
- Data only decrypted inside the TEE
- Results encrypted before distribution

## Error Responses

```json
{
  "error": "Short error description",
  "message": "Detailed error message"
}
```

**Common Status Codes:**
- `400` - Bad Request (missing/invalid parameters)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `500` - Internal Server Error

## Rate Limits

Currently no rate limits enforced. Production deployments should implement:
- 100 requests/minute per API key
- 10 TEE creations per day
- 50 dataset uploads per day per TEE
- 100 queries per day per TEE

## Examples

### Complete Workflow Example

```bash
# 1. Create TEE
curl -X POST https://api.example.com/api/tee/environments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Joint Analysis",
    "gcp_project_id": "my-project",
    "gcp_zone": "us-central1-a",
    "participant_emails": ["partner@company.com"]
  }'

# 2. Verify attestation (after VM boots)
curl -X POST https://api.example.com/api/tee/environments/1/attestation \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"attestation_token": "eyJhbGc..."}'

# 3. Upload dataset
curl -X POST https://api.example.com/api/tee/environments/1/datasets \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Dataset",
    "gcs_bucket": "my-bucket",
    "gcs_path": "data.csv",
    "schema": {"columns": [{"name": "id", "type": "int"}]}
  }'

# 4. Submit query
curl -X POST https://api.example.com/api/tee/environments/1/queries \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Analysis",
    "query_text": "SELECT COUNT(*) FROM dataset_1",
    "accesses_datasets": [1],
    "privacy_level": "aggregate_only"
  }'

# 5. Approve query (partner does this)
curl -X POST https://api.example.com/api/tee/queries/1/approve \
  -H "Authorization: Bearer PARTNER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Verified"}'

# 6. Get results (both parties can access)
curl https://api.example.com/api/tee/queries/1/results \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Support

For questions or issues:
- Email: support@permissible.ai
- Documentation: https://docs.permissible.ai
- GitHub: https://github.com/permissible-ai
