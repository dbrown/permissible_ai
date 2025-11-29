# API Key Usage Examples with curl

This file contains example curl commands for using the Permissible API with API keys.

## Setup

First, set your API key as an environment variable:

```bash
export API_KEY="your-api-key-here"
export BASE_URL="http://localhost:5000"
```

## Health Check (No Authentication Required)

```bash
curl $BASE_URL/api/health
```

## Get Current User Info

Using Authorization header (Recommended):
```bash
curl -H "Authorization: Bearer $API_KEY" $BASE_URL/api/me
```

Using X-API-Key header:
```bash
curl -H "X-API-Key: $API_KEY" $BASE_URL/api/me
```

Using query parameter (less secure):
```bash
curl "$BASE_URL/api/me?api_key=$API_KEY"
```

## List All Users (Admin Only)

```bash
curl -H "Authorization: Bearer $API_KEY" $BASE_URL/api/users
```

## Pretty JSON Output

Add `| jq` to any command for formatted JSON output:

```bash
curl -H "Authorization: Bearer $API_KEY" $BASE_URL/api/me | jq
```

## Check API Key Status

```bash
# Should return 200 with user info
curl -i -H "Authorization: Bearer $API_KEY" $BASE_URL/api/me

# Invalid key should return 401
curl -i -H "Authorization: Bearer invalid-key" $BASE_URL/api/me
```

## Production Usage

For production, replace `$BASE_URL` with your actual domain:

```bash
export BASE_URL="https://your-domain.com"
curl -H "Authorization: Bearer $API_KEY" $BASE_URL/api/me
```

## Testing Multiple Keys

You can test different API keys easily:

```bash
# Set different keys for different environments
export API_KEY_DEV="dev-key-here"
export API_KEY_PROD="prod-key-here"

# Use the appropriate key
curl -H "Authorization: Bearer $API_KEY_DEV" $BASE_URL/api/me
```

## Automated Scripts

In scripts, check for HTTP status codes:

```bash
#!/bin/bash
response=$(curl -s -w "%{http_code}" -H "Authorization: Bearer $API_KEY" $BASE_URL/api/me)
http_code="${response: -3}"

if [ "$http_code" -eq 200 ]; then
    echo "✅ Authentication successful"
else
    echo "❌ Authentication failed with status $http_code"
fi
```
