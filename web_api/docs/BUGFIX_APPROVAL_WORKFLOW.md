# Bug Fix: Query Approval and Execution Workflow

## Issues Found

### 1. **400 Error on Bob's Approval**
**Problem**: When Alice approved the query, it immediately transitioned from `submitted` → `approved`, preventing Bob from approving it (received "Query is not in submitted state" error).

**Root Cause**: The approval endpoint was calling `query.approve()` on the first approval, which immediately changed the status to `APPROVED`.

### 2. **Query Never Completed**
**Problem**: Queries were stuck in `approved` state and never reached `completed`, causing 400 errors when fetching results ("Query has not completed").

**Root Cause**: The query execution logic tried to call GCP TEE services that don't exist yet, silently failed, and never transitioned the query to `COMPLETED` status.

### 3. **No Multi-Party Approval Tracking**
**Problem**: The system didn't track individual approvals from each participant. The first approval would approve the entire query.

**Root Cause**: No database records were being created to track which participants had approved.

## Solutions Implemented

### 1. **Proper Multi-Party Approval Tracking**

Added logic to track individual approvals using the `query_approvals` association table:

```python
# Check if user already approved
existing_approval = db.session.query(query_approvals).filter_by(
    query_id=query.id,
    user_id=current_user.id
).first()

if existing_approval:
    return jsonify({'error': 'You have already approved this query'}), 400

# Record approval
db.session.execute(
    query_approvals.insert().values(
        query_id=query.id,
        user_id=current_user.id,
        approved=True,
        notes=notes
    )
)

# Check if all required participants have approved
approval_count = db.session.query(query_approvals).filter_by(
    query_id=query.id,
    approved=True
).count()

participant_count = len(query.session.participants)
```

### 2. **Added VERIFYING Status**

Queries now transition through proper states:
- `SUBMITTED` → First submitted by a participant
- `VERIFYING` → At least one approval received, waiting for more
- `APPROVED` → All required approvals received
- `COMPLETED` → Query executed and results available

### 3. **Development Mode Query Execution**

Since actual GCP TEE infrastructure isn't running, added mock query execution that:
- Generates realistic sample results
- Creates `QueryResult` records
- Transitions query to `COMPLETED` status
- Records execution time

```python
# Simulate query results
mock_results = {
    'columns': ['diagnosis_code', 'total_cases', 'readmissions', 'readmission_rate'],
    'rows': [
        ['DX001', 150, 23, 15.33],
        ['DX002', 98, 12, 12.24],
        ['DX003', 76, 8, 10.53]
    ]
}

# Create result record
result = QueryResult(
    query_id=query.id,
    result_data=mock_results,
    result_format='json',
    row_count=len(mock_results['rows']),
    file_size_bytes=len(str(mock_results))
)
db.session.add(result)

# Mark query as completed
query.complete(execution_time=round(random.uniform(0.5, 2.0), 2))
```

### 4. **Updated Approval API Response**

The approval endpoint now returns detailed information:
- Current approval count vs required
- Number of approvals still needed
- Updated query status
- Clear success messages

Example responses:

**First approval:**
```json
{
  "message": "Query approved by 1/2 participants",
  "approvals": "1/2",
  "awaiting_approvals": 1,
  "query": { "status": "verifying", ... }
}
```

**Final approval:**
```json
{
  "message": "Query approved by all participants and executed successfully",
  "approvals": "2/2",
  "query": { "status": "completed", ... }
}
```

## Current Workflow

1. Alice submits query → status: `submitted`
2. Alice approves → status: `verifying` (1/2 approvals)
3. Bob approves → status: `approved` → executes → status: `completed` (2/2 approvals)
4. Both Alice and Bob can retrieve results

## Remaining Issues (Expected)

### Dataset Encryption Warnings
```
"warning": "Dataset record created but encryption failed: Failed to encrypt dataset: 
404 GET https://storage.googleapis.com/download/storage/v1/b/hospital-a-data/o/..."
```

**Status**: Expected in development mode
**Reason**: The GCS buckets (`hospital-a-data`, `hospital-b-data`) don't exist
**Impact**: None - queries work with mock data in development
**Production Fix**: Create actual GCS buckets and configure proper encryption keys

### No Actual TEE/VM Running
The system now uses mock execution instead of attempting to connect to non-existent GCP TEE infrastructure. This is intentional for development and testing.

## Testing

Run the example workflow:
```bash
cd web_api
python scripts/examples/example_tee_workflow.py
```

Expected outcome:
- ✅ No 400 errors on Bob's approval
- ✅ Query reaches `completed` status
- ✅ Both parties can retrieve results
- ✅ Results contain mock data

## Production Considerations

When deploying with actual GCP TEE infrastructure:

1. Replace mock execution with real `gcp_service.execute_query()` call
2. Create GCS buckets for dataset storage
3. Configure KMS encryption keys
4. Set up Cloud Run service for TEE execution
5. Implement proper result storage and retrieval from GCS
