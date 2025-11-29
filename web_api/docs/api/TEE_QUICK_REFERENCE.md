# TEE API Quick Reference Guide

## Overview

The TEE (Trusted Execution Environment) API enables secure multi-party data collaboration using Google Cloud Platform's Confidential Computing.

## Key Concepts

### What is a TEE?
A **Trusted Execution Environment** is an isolated, secure compute environment running on GCP Confidential VMs where:
- Multiple parties can analyze data together
- No party can see other parties' raw data
- All processing is verified through attestation
- Results are distributed to all participants

### Workflow
```
1. Create TEE → 2. Verify Attestation → 3. Upload Datasets → 
4. Submit Query → 5. Participants Approve → 6. Execute → 7. Get Results
```

## Authentication

All endpoints require API key authentication:
```bash
curl -H "Authorization: Bearer YOUR_API_KEY" https://api.example.com/api/tee/...
```

Get your API key at: `/api-keys/` after logging in.

## Common Operations

### 1. Create a TEE

```bash
POST /api/tee/environments
{
  "name": "Research Collaboration",
  "gcp_project_id": "my-gcp-project",
  "gcp_zone": "us-central1-a",
  "participant_emails": ["partner@company.com"]
}
```

### 2. Verify TEE Attestation

```bash
POST /api/tee/environments/{tee_id}/attestation
{
  "attestation_token": "eyJhbGc..."
}
```

### 3. Upload Dataset

```bash
POST /api/tee/environments/{tee_id}/datasets
{
  "name": "My Dataset",
  "gcs_bucket": "my-bucket",
  "gcs_path": "data.csv",
  "schema": {
    "columns": [
      {"name": "customer_id", "type": "string"},
      {"name": "amount", "type": "float"}
    ]
  }
}
```

### 4. Submit Query

```bash
POST /api/tee/environments/{tee_id}/queries
{
  "name": "Revenue Analysis",
  "query_text": "SELECT SUM(amount) FROM dataset_1 GROUP BY region",
  "accesses_datasets": [1],
  "privacy_level": "aggregate_only"
}
```

### 5. Approve Query

```bash
POST /api/tee/queries/{query_id}/approve
{
  "notes": "Verified - only aggregated data"
}
```

### 6. Get Results

```bash
GET /api/tee/queries/{query_id}/results
```

## Privacy Levels

- `aggregate_only` - Only aggregated statistics (recommended)
- `k_anonymized` - K-anonymity guarantees (k≥10)
- `differential_privacy` - DP mechanisms applied
- `full_access` - Detailed results (requires strict approval)

## Status Values

### TEE Status
- `creating` - VM provisioning
- `active` - Ready for use ✓
- `suspended` - Temporarily paused
- `terminated` - Shut down
- `error` - Failed

### Dataset Status
- `uploading` - Initial upload
- `uploaded` - Upload complete
- `encrypted` - Encryption applied
- `available` - Ready for queries ✓
- `error` - Failed

### Query Status
- `submitted` - Awaiting review
- `verifying` - Under review
- `approved` - Ready to execute
- `executing` - Running
- `completed` - Results available ✓
- `rejected` - Not approved
- `error` - Execution failed

## Security Best Practices

### ✅ DO
- Always verify attestation before uploading sensitive data
- Use `aggregate_only` privacy level when possible
- Require unanimous approval for sensitive queries
- Review query text carefully before approving
- Use descriptive names for TEEs and datasets
- Monitor `last_used` timestamps on API keys

### ❌ DON'T
- Upload raw PII without encryption
- Approve queries you haven't reviewed
- Share API keys with others
- Reuse TEEs for unrelated projects
- Skip attestation verification

## Error Handling

```python
response = requests.post(url, headers=headers, json=data)

if response.status_code == 201:
    # Success - resource created
    resource = response.json()
elif response.status_code == 400:
    # Bad request - check parameters
    print(response.json()['error'])
elif response.status_code == 403:
    # Forbidden - insufficient permissions
    print("Not authorized")
elif response.status_code == 404:
    # Not found
    print("Resource not found")
else:
    # Other error
    print(f"Error {response.status_code}")
```

## Python SDK Example

```python
import requests

class TEEClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}
    
    def create_tee(self, name, gcp_project, gcp_zone, participants=None):
        return requests.post(
            f"{self.base_url}/environments",
            headers=self.headers,
            json={
                "name": name,
                "gcp_project_id": gcp_project,
                "gcp_zone": gcp_zone,
                "participant_emails": participants or []
            }
        ).json()
    
    def upload_dataset(self, tee_id, name, bucket, path, schema):
        return requests.post(
            f"{self.base_url}/environments/{tee_id}/datasets",
            headers=self.headers,
            json={
                "name": name,
                "gcs_bucket": bucket,
                "gcs_path": path,
                "schema": schema
            }
        ).json()
    
    def submit_query(self, tee_id, name, query_text, dataset_ids):
        return requests.post(
            f"{self.base_url}/environments/{tee_id}/queries",
            headers=self.headers,
            json={
                "name": name,
                "query_text": query_text,
                "accesses_datasets": dataset_ids,
                "privacy_level": "aggregate_only"
            }
        ).json()
    
    def get_results(self, query_id):
        return requests.get(
            f"{self.base_url}/queries/{query_id}/results",
            headers=self.headers
        ).json()

# Usage
client = TEEClient("http://localhost:5000/api/tee", "your-api-key")
tee = client.create_tee("My TEE", "my-project", "us-central1-a")
```

## Troubleshooting

### TEE creation fails
- Check GCP project ID is correct
- Verify GCP zone supports Confidential Computing
- Ensure GCP APIs are enabled
- Check service account permissions

### Dataset upload stuck
- Verify GCS bucket permissions
- Check file exists at specified path
- Ensure bucket is in same GCP project
- Review Cloud KMS permissions

### Query not executing
- Confirm all participants approved
- Check all accessed datasets are `available`
- Verify TEE status is `active`
- Review query syntax

### Can't access results
- Ensure query status is `completed`
- Verify you're a TEE participant
- Check network connectivity
- Try regenerating signed URL

## Resources

- Full documentation: [TEE_API_DOCUMENTATION.md](TEE_API_DOCUMENTATION.md)
- Example workflow: [example_tee_workflow.py](example_tee_workflow.py)
- GCP Confidential Computing: https://cloud.google.com/confidential-computing
- Support: support@permissible.ai
