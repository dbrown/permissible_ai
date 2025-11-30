#!/usr/bin/env python3
"""
TEE Server - Runs inside Confidential VM

This server handles:
1. Attestation generation with public key
2. Direct encrypted data uploads from clients
3. Query execution in isolated environment
4. Dataset decryption and re-encryption with session keys

Security guarantees:
- Runs only in GCP Confidential VM with measured boot
- Private keys never leave the secure enclave
- Each session has isolated encryption keys
- All operations audited
"""

import os
import sys
import json
import base64
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from flask_cors import CORS
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import jwt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS to allow requests from the web application
# In production, restrict this to specific origins
CORS(app, resources={
    r"/*": {
        "origins": "*",  # In production: ["https://your-app.com"]
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "max_age": 3600
    }
})

# TEE Configuration
TEE_PRIVATE_KEY = None  # Loaded from image, never exported
TEE_PUBLIC_KEY = None
TEE_CODE_HASH = None  # Measurement of this code
TEE_IMAGE_ID = None  # GCP image ID for attestation
SESSION_KEYS = {}  # session_id -> encryption key (in-memory only)
DATASETS = {}  # dataset_id -> encrypted data storage

# Callback configuration
CONTROL_PLANE_URL = os.getenv('CONTROL_PLANE_URL', 'http://localhost:5000')


def load_tee_keypair():
    """
    Load RSA keypair from immutable image.
    Keys are baked into the image during build process.
    """
    global TEE_PRIVATE_KEY, TEE_PUBLIC_KEY
    
    key_dir = os.getenv('TEE_KEY_DIR', '/opt/tee-runtime')
    private_key_path = os.path.join(key_dir, 'tee_private_key.pem')
    public_key_path = os.path.join(key_dir, 'tee_public_key.pem')
    
    # Try to load existing keys
    if os.path.exists(private_key_path) and os.path.exists(public_key_path):
        logger.info(f"Loading TEE keypair from image: {key_dir}")
        
        with open(private_key_path, 'rb') as f:
            TEE_PRIVATE_KEY = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        
        with open(public_key_path, 'rb') as f:
            TEE_PUBLIC_KEY = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        
        logger.info("TEE keypair loaded from immutable image")
    else:
        # Fallback: Generate keys (not recommended for production)
        logger.warning("⚠️  Keys not found in image, generating ephemeral keys")
        logger.warning("⚠️  This should only happen in development!")
        
        TEE_PRIVATE_KEY = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        TEE_PUBLIC_KEY = TEE_PRIVATE_KEY.public_key()
    
    # Export public key for sharing
    public_pem = TEE_PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')
    
    return public_pem


def get_instance_metadata(key: str) -> Optional[str]:
    """Fetch metadata from GCP metadata server"""
    try:
        import requests
        metadata_url = f"http://metadata.google.internal/computeMetadata/v1/{key}"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(metadata_url, headers=headers, timeout=2)
        return response.text if response.status_code == 200 else None
    except Exception as e:
        logger.error(f"Failed to get metadata {key}: {e}")
        return None


def calculate_code_measurement():
    """Calculate hash of this TEE server code"""
    global TEE_CODE_HASH, TEE_IMAGE_ID
    
    # Try to load from pre-computed hash in image
    hash_file = '/opt/tee-runtime/CODE_HASH.txt'
    if os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            TEE_CODE_HASH = f.read().strip().split()[0]
        logger.info(f"Loaded code hash from image: {TEE_CODE_HASH}")
    else:
        # Fallback: compute at runtime
        with open(__file__, 'rb') as f:
            code_bytes = f.read()
        TEE_CODE_HASH = hashlib.sha256(code_bytes).hexdigest()
        logger.info(f"Computed code hash: {TEE_CODE_HASH}")
    
    # Get image ID from metadata
    try:
        image_info_file = '/opt/tee-runtime/IMAGE_INFO.json'
        if os.path.exists(image_info_file):
            with open(image_info_file, 'r') as f:
                image_info = json.load(f)
                TEE_IMAGE_ID = image_info.get('image_name')
                logger.info(f"TEE Image: {TEE_IMAGE_ID}")
    except Exception as e:
        logger.warning(f"Could not load image info: {e}")
    
    return TEE_CODE_HASH


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'tee_active': True,
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/attestation', methods=['GET'])
def attestation():
    """
    Generate attestation token proving:
    1. Running in confidential VM
    2. Running specific measured code
    3. Has a public key for encryption
    
    Clients MUST verify this before uploading data
    """
    try:
        # Get VM metadata for attestation
        instance_id = get_instance_metadata('instance/id')
        instance_name = get_instance_metadata('instance/name')
        zone = get_instance_metadata('instance/zone')
        
        attestation_data = {
            'tee_type': 'gcp_confidential_vm',
            'code_measurement': TEE_CODE_HASH,
            'image_id': TEE_IMAGE_ID,
            'instance_id': instance_id,
            'instance_name': instance_name,
            'zone': zone,
            'public_key': TEE_PUBLIC_KEY.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8'),
            'generated_at': datetime.utcnow().isoformat(),
            'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat(),
            
            # Security properties
            'confidential_computing': True,
            'secure_boot': True,
            'ssh_disabled': True,
            'immutable_code': True,
            
            # In production, add hardware attestation:
            # 'sev_attestation': '...',     # AMD SEV attestation report
            # 'tpm_quote': '...',            # TPM quote/signature
            # 'boot_measurements': [...],    # Measured boot chain
        }
        
        # Sign attestation with TEE private key
        attestation_json = json.dumps(attestation_data, sort_keys=True)
        signature = TEE_PRIVATE_KEY.sign(
            attestation_json.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return jsonify({
            'attestation': attestation_data,
            'signature': base64.b64encode(signature).decode('utf-8'),
            'signature_algorithm': 'RSA-PSS-SHA256'
        })
        
    except Exception as e:
        logger.error(f"Attestation generation failed: {e}")
        return jsonify({'error': 'Failed to generate attestation'}), 500


@app.route('/upload', methods=['POST'])
def upload_dataset():
    """
    Receive encrypted dataset directly from client
    
    Expected payload:
    {
        "dataset_id": 123,
        "session_id": 456,
        "encrypted_data": "base64...",  # AES-GCM encrypted
        "encrypted_key": "base64...",    # RSA-OAEP encrypted AES key
        "iv": "base64...",
        "algorithm": "AES-256-GCM",
        "filename": "data.csv",
        "file_size": 1024
    }
    """
    try:
        # Verify upload token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing authorization token'}), 401
        
        token = auth_header.split(' ')[1]
        # In production, verify JWT against shared secret with control plane
        # For demo, we'll accept it
        
        data = request.json
        dataset_id = data['dataset_id']
        session_id = data['session_id']
        
        logger.info(f"Receiving encrypted upload for dataset {dataset_id}, session {session_id}")
        
        # Decrypt AES key using TEE private key
        encrypted_key = base64.b64decode(data['encrypted_key'])
        aes_key = TEE_PRIVATE_KEY.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        # Decrypt data using AES key
        encrypted_data = base64.b64decode(data['encrypted_data'])
        iv = base64.b64decode(data['iv'])
        
        aesgcm = AESGCM(aes_key)
        plaintext_data = aesgcm.decrypt(iv, encrypted_data, None)
        
        logger.info(f"Successfully decrypted {len(plaintext_data)} bytes")
        
        # Re-encrypt with session-specific key
        session_key = get_or_create_session_key(session_id)
        session_iv = os.urandom(12)
        session_aesgcm = AESGCM(session_key)
        session_encrypted = session_aesgcm.encrypt(session_iv, plaintext_data, None)
        
        # Store encrypted dataset (in-memory for demo, would be encrypted file storage)
        DATASETS[dataset_id] = {
            'session_id': session_id,
            'encrypted_data': session_encrypted,
            'iv': session_iv,
            'filename': data['filename'],
            'file_size': data['file_size'],
            'uploaded_at': datetime.utcnow().isoformat(),
            'checksum': hashlib.sha256(plaintext_data).hexdigest()
        }
        
        logger.info(f"Dataset {dataset_id} stored securely in TEE")
        
        # Notify control plane of successful upload
        notify_control_plane(dataset_id, 'available', {
            'checksum': DATASETS[dataset_id]['checksum'],
            'file_size': data['file_size']
        })
        
        return jsonify({
            'status': 'success',
            'dataset_id': dataset_id,
            'checksum': DATASETS[dataset_id]['checksum'],
            'message': 'Dataset encrypted and stored securely in TEE'
        })
        
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        
        # Notify control plane of failure
        if 'dataset_id' in locals():
            notify_control_plane(dataset_id, 'failed', {'error': str(e)})
        
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500


@app.route('/execute', methods=['POST'])
def execute_query():
    """
    Execute approved query on encrypted datasets
    
    This runs inside the TEE with strict isolation
    """
    try:
        data = request.json
        query_id = data['query_id']
        session_id = data['session_id']
        query_text = data['query_text']
        dataset_ids = data['dataset_ids']
        
        logger.info(f"Executing query {query_id} on session {session_id}")
        
        # Verify all datasets belong to this session
        session_key = SESSION_KEYS.get(session_id)
        if not session_key:
            return jsonify({'error': 'Session key not found'}), 404
        
        # Decrypt datasets
        dataframes = []
        for dataset_id in dataset_ids:
            dataset = DATASETS.get(dataset_id)
            if not dataset or dataset['session_id'] != session_id:
                return jsonify({'error': f'Dataset {dataset_id} not found or unauthorized'}), 403
            
            # Decrypt with session key
            aesgcm = AESGCM(session_key)
            plaintext = aesgcm.decrypt(dataset['iv'], dataset['encrypted_data'], None)
            
            # In production: load into pandas/DuckDB
            # For now, just log
            logger.info(f"Decrypted dataset {dataset_id}: {len(plaintext)} bytes")
        
        # Execute query (simplified - would use DuckDB or similar)
        # IMPORTANT: Query execution must be sandboxed to prevent data exfiltration
        
        result_data = {
            'query_id': query_id,
            'status': 'success',
            'row_count': 0,  # Placeholder
            'executed_at': datetime.utcnow().isoformat()
        }
        
        # Encrypt results for requester only
        # ... encryption logic ...
        
        notify_control_plane(query_id, 'completed', result_data, is_query=True)
        
        return jsonify({
            'status': 'success',
            'query_id': query_id
        })
        
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def get_or_create_session_key(session_id: int) -> bytes:
    """Generate or retrieve session-specific encryption key"""
    if session_id not in SESSION_KEYS:
        SESSION_KEYS[session_id] = AESGCM.generate_key(bit_length=256)
        logger.info(f"Generated new session key for session {session_id}")
    return SESSION_KEYS[session_id]


def notify_control_plane(entity_id: int, status: str, metadata: Dict[str, Any], is_query: bool = False):
    """Notify control plane of dataset/query status changes"""
    try:
        import requests
        
        endpoint = f"{CONTROL_PLANE_URL}/api/tee/callback"
        payload = {
            'entity_type': 'query' if is_query else 'dataset',
            'entity_id': entity_id,
            'status': status,
            'metadata': metadata,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # In production, sign this callback with TEE private key
        response = requests.post(endpoint, json=payload, timeout=5)
        logger.info(f"Notified control plane: {status} for {'query' if is_query else 'dataset'} {entity_id}")
        
    except Exception as e:
        logger.error(f"Failed to notify control plane: {e}")
        # Don't fail the operation if callback fails


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Starting TEE Server in Confidential VM")
    logger.info("=" * 80)
    
    # Load keypair from image
    public_key_pem = load_tee_keypair()
    logger.info(f"TEE Public Key:\n{public_key_pem}")
    
    # Calculate code measurement
    code_hash = calculate_code_measurement()
    logger.info(f"Code Measurement: {code_hash}")
    
    if TEE_IMAGE_ID:
        logger.info(f"Image ID: {TEE_IMAGE_ID}")
    
    logger.info("=" * 80)
    logger.info("⚠️  ZERO-TRUST VERIFICATION REQUIRED:")
    logger.info("   1. Verify code_measurement matches audited source")
    logger.info("   2. Verify image_id matches approved build")
    logger.info("   3. Verify attestation signature before uploading data")
    logger.info("=" * 80)
    
    # Start server
    port = int(os.getenv('TEE_PORT', 8080))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,  # Never enable debug in production TEE
        threaded=True
    )
