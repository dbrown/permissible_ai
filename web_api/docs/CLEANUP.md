# TEE Cleanup Utilities

## Overview

To prevent runaway GCP costs from test TEEs left running, we provide automatic and manual cleanup tools.

## Automatic Cleanup

Both example scripts now automatically clean up old test TEEs before creating new ones:

- `scripts/examples/example_tee_workflow.py` - Full workflow demo
- `scripts/test_tee_status.py` - Quick status test

The automatic cleanup will delete:
- TEEs with "test" in the name
- TEEs in "error" status
- TEEs in "creating" status (prevents retries)

## Manual Cleanup

Use the cleanup script for manual cleanup:

```bash
# Dry run - see what would be deleted without actually deleting
python scripts/cleanup_tees.py --dry-run

# Clean up test and error TEEs (with confirmation prompt)
python scripts/cleanup_tees.py

# Delete ALL TEEs (use with caution!)
python scripts/cleanup_tees.py --all
```

### What Gets Deleted Automatically

The cleanup script will automatically delete TEEs that:
1. Have status "error"
2. Have "test" in their name (case-insensitive)
3. Are stuck in "creating" status for more than 10 minutes

### Cost Savings

Each Confidential VM (n2d-standard-2) costs approximately:
- **$0.10/hour** (~$72/month if left running)

Always clean up test TEEs after use!

## API Endpoint

You can also delete TEEs via the API:

```bash
curl -X DELETE http://localhost:5000/api/tee/environments/{tee_id} \
  -H "Authorization: Bearer YOUR_API_KEY"
```

This will:
1. Terminate the GCP Confidential VM instance
2. Delete the TEE record from the database

## Best Practices

1. **Always clean up after testing** - Use the cleanup script or API
2. **Use descriptive names** - Avoid "test" in production TEE names
3. **Monitor regularly** - Run `--dry-run` periodically to check for orphaned TEEs
4. **Set up alerts** - Configure GCP budget alerts for unexpected costs
