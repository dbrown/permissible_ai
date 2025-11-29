#!/bin/bash
#
# Deploy Shared TEE Infrastructure
# 
# This script creates a GCP Confidential VM for testing attestation
# and secure query execution in a development environment.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="shared-tee-dev"
MACHINE_TYPE="n2d-standard-2"  # AMD SEV-SNP for confidential computing
SERVICE_ACCOUNT="${TEE_SERVICE_ACCOUNT:-}"
NETWORK="${GCP_NETWORK:-default}"

echo "=========================================="
echo "Shared TEE Deployment Script"
echo "=========================================="
echo ""

# Validate prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: GOOGLE_CLOUD_PROJECT environment variable not set${NC}"
    echo "Set it with: export GOOGLE_CLOUD_PROJECT=your-project-id"
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud CLI not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verify authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${RED}ERROR: Not authenticated with gcloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Set project
echo -e "${YELLOW}Setting project to: ${PROJECT_ID}${NC}"
gcloud config set project "$PROJECT_ID"
echo ""

# Enable required APIs
echo -e "${YELLOW}Enabling required GCP APIs...${NC}"
gcloud services enable compute.googleapis.com
gcloud services enable cloudkms.googleapis.com
gcloud services enable storage-api.googleapis.com
echo -e "${GREEN}✓ APIs enabled${NC}"
echo ""

# Check if instance already exists
if gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &> /dev/null; then
    echo -e "${YELLOW}Instance $INSTANCE_NAME already exists${NC}"
    read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deleting existing instance...${NC}"
        gcloud compute instances delete "$INSTANCE_NAME" --zone="$ZONE" --quiet
        echo -e "${GREEN}✓ Instance deleted${NC}"
    else
        echo "Exiting without changes"
        exit 0
    fi
fi

# Create startup script
echo -e "${YELLOW}Creating TEE startup script...${NC}"
cat > /tmp/tee-startup.sh << 'STARTUP_SCRIPT_EOF'
#!/bin/bash
set -e

echo "=== TEE Runtime Setup ==="
echo "Starting at: $(date)"

# Update system
apt-get update
apt-get install -y python3-pip python3-venv postgresql-client curl jq

# Create TEE runtime directory
mkdir -p /opt/tee-runtime
cd /opt/tee-runtime

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install flask gunicorn sqlalchemy psycopg2-binary pandas pyarrow google-cloud-storage google-cloud-kms pyjwt cryptography

# Create attestation service
cat > attestation_service.py << 'ATTESTATION_EOF'
"""
Shared TEE Attestation Service

Provides attestation tokens and handles query execution
for multiple collaboration sessions.
"""
import os
import json
import jwt
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get instance metadata
def get_instance_metadata(key):
    """Fetch instance metadata from GCE metadata server"""
    try:
        import requests
        metadata_server = "http://metadata.google.internal/computeMetadata/v1"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(f"{metadata_server}/{key}", headers=headers)
        return response.text
    except Exception as e:
        logger.error(f"Failed to get metadata {key}: {e}")
        return None

def compute_runtime_hash():
    """Compute cryptographic hash of all runtime files for integrity verification"""
    import hashlib
    
    files_to_hash = [
        '/opt/tee-runtime/attestation_service.py',
        '/etc/systemd/system/tee-attestation.service'
    ]
    
    hashes = {}
    combined = ""
    
    for filepath in files_to_hash:
        try:
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    file_content = f.read()
                    file_hash = hashlib.sha256(file_content).hexdigest()
                    hashes[filepath] = f"sha256:{file_hash}"
                    combined += file_hash
        except Exception as e:
            logger.warning(f"Could not hash {filepath}: {e}")
    
    # Combined hash of all files
    runtime_hash = hashlib.sha256(combined.encode()).hexdigest()
    
    return {
        'runtime_hash': f"sha256:{runtime_hash}",
        'files': hashes,
        'timestamp': datetime.utcnow().isoformat()
    }

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'shared-tee-attestation'
    })

@app.route('/runtime-hash', methods=['GET'])
def get_runtime_hash():
    """Get cryptographic hash of runtime code for integrity verification"""
    try:
        return jsonify(compute_runtime_hash())
    except Exception as e:
        logger.error(f"Failed to compute runtime hash: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/attestation', methods=['GET'])
def get_attestation():
    """Generate attestation token for this TEE instance"""
    try:
        # Get instance metadata
        instance_id = get_instance_metadata('instance/id')
        instance_name = get_instance_metadata('instance/name')
        zone = get_instance_metadata('instance/zone')
        project = get_instance_metadata('project/project-id')
        
        # Check confidential computing features
        # In real implementation, verify SEV-SNP attestation report
        confidential_enabled = True  # Verify from SEV report
        
        # Compute runtime hash for integrity verification
        runtime_info = compute_runtime_hash()
        
        # Create attestation claims
        claims = {
            'iss': 'gcp-confidential-vm',
            'sub': 'shared-tee-service',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1),
            'instance_id': instance_id,
            'instance_name': instance_name,
            'zone': zone,
            'project': project,
            'confidential_computing': confidential_enabled,
            'secure_boot': True,
            'vtpm_enabled': True,
            'runtime_version': '1.0.0',
            'runtime_hash': runtime_info['runtime_hash'],
            'file_hashes': runtime_info['files']
        }
        
        # Sign token (in production, use instance private key)
        # For development, using symmetric key - REPLACE IN PRODUCTION
        secret_key = os.getenv('ATTESTATION_SECRET', 'dev-secret-change-in-production')
        token = jwt.encode(claims, secret_key, algorithm='HS256')
        
        logger.info(f"Generated attestation token for instance {instance_id}")
        
        return jsonify({
            'attestation_token': token,
            'instance_id': instance_id,
            'instance_name': instance_name,
            'zone': zone,
            'timestamp': datetime.utcnow().isoformat(),
            'verified': True
        })
        
    except Exception as e:
        logger.error(f"Failed to generate attestation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/execute-query', methods=['POST'])
def execute_query():
    """Execute a query in isolated environment"""
    try:
        data = request.get_json()
        
        query_id = data.get('query_id')
        session_id = data.get('session_id')
        query_text = data.get('query_text')
        dataset_paths = data.get('dataset_paths', [])
        
        logger.info(f"Executing query {query_id} for session {session_id}")
        
        # In production, execute query in isolated container/process
        # For development, return mock results
        mock_results = {
            'query_id': query_id,
            'session_id': session_id,
            'status': 'completed',
            'results': {
                'columns': ['diagnosis_code', 'total_cases', 'readmissions', 'readmission_rate'],
                'rows': [
                    ['DX001', 150, 23, 15.33],
                    ['DX002', 98, 12, 12.24],
                    ['DX003', 76, 8, 10.53]
                ]
            },
            'execution_time': 1.23,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(mock_results)
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/status', methods=['GET'])
def status():
    """Get TEE service status and metrics"""
    try:
        instance_id = get_instance_metadata('instance/id')
        
        # Check for SSH access in auth logs
        ssh_warning = None
        try:
            import subprocess
            result = subprocess.run(
                ['journalctl', '-u', 'sshd', '--since', '1 hour ago', '--no-pager'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if 'Accepted' in result.stdout or 'session opened' in result.stdout:
                ssh_warning = "SSH access detected in last hour - users should verify integrity"
        except Exception as e:
            logger.warning(f"Could not check SSH logs: {e}")
        
        status_info = {
            'service': 'shared-tee',
            'status': 'running',
            'instance_id': instance_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if ssh_warning:
            status_info['warning'] = ssh_warning
            
        return jsonify(status_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/audit-events', methods=['GET'])
def audit_events():
    """Get recent audit events for transparency"""
    try:
        import subprocess
        
        # Get SSH login attempts
        ssh_result = subprocess.run(
            ['journalctl', '-u', 'sshd', '-n', '50', '--no-pager', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Get service restarts
        service_result = subprocess.run(
            ['journalctl', '-u', 'tee-attestation', '-n', '50', '--no-pager', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        events = {
            'ssh_events': ssh_result.stdout if ssh_result.returncode == 0 else [],
            'service_events': service_result.stdout if service_result.returncode == 0 else [],
            'timestamp': datetime.utcnow().isoformat(),
            'note': 'Full audit logs available in Cloud Logging'
        }
        
        return jsonify(events)
    except Exception as e:
        logger.error(f"Failed to get audit events: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
ATTESTATION_EOF

# Create systemd service
cat > /etc/systemd/system/tee-attestation.service << 'SERVICE_EOF'
[Unit]
Description=Shared TEE Attestation Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tee-runtime
Environment="PATH=/opt/tee-runtime/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PORT=8080"
ExecStart=/opt/tee-runtime/venv/bin/python3 /opt/tee-runtime/attestation_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Enable and start service
systemctl daemon-reload
systemctl enable tee-attestation.service
systemctl start tee-attestation.service

# Wait for service to start
sleep 5

# Check service status
if systemctl is-active --quiet tee-attestation.service; then
    echo "✓ TEE Attestation Service started successfully"
    
    # Test the service
    curl -s http://localhost:8080/health | jq . || echo "Health check response received"
else
    echo "✗ Failed to start TEE Attestation Service"
    systemctl status tee-attestation.service
    exit 1
fi

echo "=== TEE Runtime Setup Complete ==="
echo "Completed at: $(date)"
STARTUP_SCRIPT_EOF

echo -e "${GREEN}✓ Startup script created${NC}"
echo ""

# Create the Confidential VM
echo -e "${YELLOW}Creating Confidential VM: ${INSTANCE_NAME}${NC}"
echo "  Project: $PROJECT_ID"
echo "  Zone: $ZONE"
echo "  Machine Type: $MACHINE_TYPE"
echo ""

SERVICE_ACCOUNT_FLAG=""
if [ -n "$SERVICE_ACCOUNT" ]; then
    SERVICE_ACCOUNT_FLAG="--service-account=$SERVICE_ACCOUNT"
fi

gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --confidential-compute-type=SEV \
    --maintenance-policy=TERMINATE \
    --shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-balanced \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --network="$NETWORK" \
    --tags=tee-service,http-server,https-server \
    --metadata-from-file=startup-script=/tmp/tee-startup.sh \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    $SERVICE_ACCOUNT_FLAG

echo ""
echo -e "${GREEN}✓ VM created successfully${NC}"
echo ""

# Wait for VM to be ready
echo -e "${YELLOW}Waiting for VM to be ready (this may take 2-3 minutes)...${NC}"
sleep 30

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Instance Details:"
echo "  Name: $INSTANCE_NAME"
echo "  Zone: $ZONE"
echo "  External IP: $EXTERNAL_IP"
echo ""
echo "Next Steps:"
echo ""
echo "1. Create firewall rule for TEE service:"
echo "   gcloud compute firewall-rules create allow-tee-service \\"
echo "     --network=$NETWORK \\"
echo "     --allow=tcp:8080 \\"
echo "     --source-ranges=YOUR_IP/32 \\"
echo "     --target-tags=tee-service"
echo ""
echo "2. Set environment variable in your Flask app:"
echo "   export TEE_SERVICE_ENDPOINT=http://${EXTERNAL_IP}:8080"
echo ""
echo "3. Test the attestation endpoint:"
echo "   curl http://${EXTERNAL_IP}:8080/health"
echo "   curl http://${EXTERNAL_IP}:8080/attestation"
echo ""
echo "4. SSH into the VM to check logs:"
echo "   gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "   sudo journalctl -u tee-attestation -f"
echo ""
echo "5. Verify confidential computing:"
echo "   gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE \\"
echo "     --format='get(confidentialInstanceConfig)'"
echo ""

# Clean up temp file
rm -f /tmp/tee-startup.sh

echo "=========================================="
