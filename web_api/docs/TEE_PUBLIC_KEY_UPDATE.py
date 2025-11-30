"""
Add /public-key endpoint to TEE attestation service

This update enables client-side encryption by exposing the TEE's public key.
The public key is extracted from the same keypair used for signing attestations.

Deploy this to the TEE VM at: /opt/tee-runtime/attestation_service.py
"""

# Add this route to the existing attestation_service.py on the TEE VM:

@app.route('/public-key', methods=['GET'])
def get_public_key():
    """
    Return the TEE's RSA public key for client-side encryption
    
    This key is used by clients to encrypt data before uploading.
    Only this TEE instance can decrypt data encrypted with this key.
    
    Returns:
        JSON containing:
        - public_key_pem: PEM-encoded RSA public key
        - key_id: Unique identifier for this key (based on hash)
        - algorithm: Encryption algorithm to use
        - instance_id: TEE instance identifier
        - timestamp: Key generation timestamp
    """
    try:
        from cryptography.hazmat.primitives import serialization, hashes
        import hashlib
        import base64
        
        # Get the public key from the same keypair used for attestation signing
        # This ensures the key is bound to the attested TEE instance
        public_key = PRIVATE_KEY.public_key()
        
        # Export as PEM format
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Generate key ID (hash of public key for identification)
        key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        key_id = hashlib.sha256(key_bytes).hexdigest()[:16]
        
        # Get instance metadata
        import datetime
        response_data = {
            'public_key_pem': public_key_pem,
            'key_id': key_id,
            'algorithm': 'RSA-OAEP-SHA256',
            'key_size': 2048,  # or 4096 if using larger keys
            'instance_id': INSTANCE_ID,
            'instance_name': INSTANCE_NAME,
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'usage': 'Encrypt data with this public key. Only this TEE can decrypt.'
        }
        
        logger.info(f"Public key requested. Key ID: {key_id}")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Failed to export public key: {e}")
        return jsonify({'error': 'Failed to export public key'}), 500


# Add this route for receiving encrypted uploads:

@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_encrypted_dataset():
    """
    Accept client-encrypted dataset uploads
    
    Expected payload (JSON):
    {
        "dataset_id": 123,
        "session_id": 456,
        "encrypted_data": "base64_encoded_ciphertext",
        "encrypted_key": "base64_encoded_wrapped_aes_key",
        "iv": "base64_encoded_initialization_vector",
        "algorithm": "AES-256-GCM",
        "filename": "data.csv",
        "file_size": 1048576
    }
    
    Authorization: Bearer <upload_token>
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import base64
        import hashlib
        
        # Verify authorization token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization'}), 401
        
        upload_token = auth_header.split(' ', 1)[1]
        # TODO: Verify JWT token signature and claims
        
        data = request.json
        dataset_id = data['dataset_id']
        session_id = data['session_id']
        
        logger.info(f"Receiving encrypted upload for dataset {dataset_id}, session {session_id}")
        
        # Step 1: Decrypt the AES key using TEE's RSA private key
        encrypted_aes_key = base64.b64decode(data['encrypted_key'])
        aes_key = PRIVATE_KEY.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        logger.info(f"Decrypted AES key for dataset {dataset_id}")
        
        # Step 2: Decrypt the data using the AES key
        encrypted_data_bytes = base64.b64decode(data['encrypted_data'])
        iv = base64.b64decode(data['iv'])
        
        aesgcm = AESGCM(aes_key)
        plaintext_data = aesgcm.decrypt(iv, encrypted_data_bytes, None)
        
        logger.info(f"Decrypted {len(plaintext_data)} bytes for dataset {dataset_id}")
        
        # Step 3: Re-encrypt with session-specific key for isolation
        session_key = get_or_create_session_key(session_id)
        session_iv = os.urandom(12)
        session_aesgcm = AESGCM(session_key)
        session_encrypted = session_aesgcm.encrypt(session_iv, plaintext_data, None)
        
        # Step 4: Store encrypted dataset
        checksum = hashlib.sha256(plaintext_data).hexdigest()
        
        # Store in memory or encrypted storage
        DATASETS[dataset_id] = {
            'session_id': session_id,
            'encrypted_data': session_encrypted,
            'iv': session_iv,
            'filename': data['filename'],
            'file_size': len(plaintext_data),
            'uploaded_at': datetime.datetime.utcnow().isoformat(),
            'checksum': checksum
        }
        
        logger.info(f"Dataset {dataset_id} stored securely. Checksum: {checksum}")
        
        # Step 5: Notify control plane
        notify_control_plane(dataset_id, 'available', {
            'checksum': checksum,
            'file_size': len(plaintext_data)
        })
        
        # Return response with CORS headers
        response = jsonify({
            'status': 'success',
            'dataset_id': dataset_id,
            'checksum': checksum,
            'message': 'Dataset encrypted and stored in TEE'
        })
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 201
        
    except Exception as e:
        logger.error(f"Upload failed for dataset {dataset_id}: {e}", exc_info=True)
        
        # Notify control plane of failure
        try:
            notify_control_plane(dataset_id, 'failed', {'error': str(e)})
        except:
            pass
        
        error_response = jsonify({'error': f'Upload failed: {str(e)}'})
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response, 500


def get_or_create_session_key(session_id):
    """Get or create session-specific encryption key"""
    if session_id not in SESSION_KEYS:
        SESSION_KEYS[session_id] = AESGCM.generate_key(bit_length=256)
        logger.info(f"Generated new session key for session {session_id}")
    return SESSION_KEYS[session_id]


def notify_control_plane(dataset_id, status, metadata):
    """Notify control plane of dataset status"""
    try:
        import requests
        
        payload = {
            'entity_type': 'dataset',
            'entity_id': dataset_id,
            'status': status,
            'metadata': metadata,
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        
        control_plane_url = os.getenv('CONTROL_PLANE_URL', 'http://localhost:5000')
        response = requests.post(
            f"{control_plane_url}/api/tee/callback",
            json=payload,
            timeout=5
        )
        logger.info(f"Notified control plane: dataset {dataset_id} -> {status}")
        
    except Exception as e:
        logger.error(f"Failed to notify control plane: {e}")


# Add these global variables at the top of the file:
SESSION_KEYS = {}  # session_id -> AES key (in-memory only)
DATASETS = {}  # dataset_id -> encrypted dataset storage

# Deployment Instructions:
# 1. SSH to TEE VM: gcloud compute ssh shared-tee-dev --zone=us-central1-a
# 2. Backup existing file: sudo cp /opt/tee-runtime/attestation_service.py /opt/tee-runtime/attestation_service.py.bak
# 3. Add the routes above to the Flask app
# 4. Set CONTROL_PLANE_URL environment variable
# 5. Restart service: sudo systemctl restart tee-attestation
# 6. Verify: curl http://localhost:8080/public-key
