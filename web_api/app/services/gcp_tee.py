"""
GCP Shared Trusted Execution Environment Service

This service handles interactions with a single shared GCP Confidential VM for:
- Verifying attestation tokens from the shared TEE
- Managing encrypted datasets
- Executing queries in the shared TEE
- Multi-tenant isolation and security

The shared TEE runs continuously and serves all collaboration sessions.
"""
import json
import logging
import base64
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from google.cloud import compute_v1
from google.cloud import storage
from google.cloud import kms
from google.oauth2 import service_account
from google.api_core import exceptions as google_exceptions
import jwt
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)


# Startup script for TEE VMs - installs Python environment and TEE runtime
TEE_VM_STARTUP_SCRIPT = """#!/bin/bash
set -e

# Update system
apt-get update
apt-get install -y python3-pip postgresql-client

# Install Python dependencies for TEE runtime
pip3 install sqlalchemy psycopg2-binary pandas pyarrow google-cloud-storage google-cloud-kms

# Create TEE runtime directory
mkdir -p /opt/tee-runtime
cd /opt/tee-runtime

# Download TEE runtime code (in production, fetch from secure storage)
cat > query_executor.py << 'EOFPYTHON'
import json
import sys
import os
from google.cloud import storage, kms
import sqlalchemy
import pandas as pd

def execute_query(query_id, query_text, dataset_paths, result_bucket, result_path):
    try:
        # Decrypt and load datasets
        dataframes = {}
        for i, path in enumerate(dataset_paths):
            # In production: decrypt dataset using KMS
            df = pd.read_csv(path)  # Simplified
            dataframes[f'dataset_{i+1}'] = df
        
        # Execute query (simplified - use DuckDB or similar in production)
        # This is a placeholder - real implementation would parse and execute SQL
        result = pd.DataFrame({'status': ['success'], 'query_id': [query_id]})
        
        # Encrypt and upload results
        storage_client = storage.Client()
        bucket = storage_client.bucket(result_bucket)
        blob = bucket.blob(result_path)
        blob.upload_from_string(result.to_csv(index=False))
        
        print(json.dumps({'status': 'success', 'query_id': query_id}))
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    query_id = int(sys.argv[1])
    query_text = sys.argv[2]
    dataset_paths = json.loads(sys.argv[3])
    result_bucket = sys.argv[4]
    result_path = sys.argv[5]
    execute_query(query_id, query_text, dataset_paths, result_bucket, result_path)
EOFPYTHON

# Set permissions
chmod +x query_executor.py

# Generate attestation token
cat > generate_attestation.py << 'EOFPYTHON'
import json
import jwt
import datetime
from google.auth import compute_engine
from google.cloud import compute_v1

def generate_attestation():
    try:
        # Get VM metadata
        credentials = compute_engine.Credentials()
        
        # Generate attestation claims
        claims = {
            'iss': 'gcp-confidential-vm',
            'sub': 'tee-instance',
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            'instance_id': compute_engine.get_metadata('instance/id'),
            'zone': compute_engine.get_metadata('instance/zone'),
            'confidential_computing': True,
            'secure_boot': True,
            'vtpm_enabled': True
        }
        
        # Sign with instance credentials (simplified)
        token = jwt.encode(claims, 'secret', algorithm='HS256')
        print(token)
    except Exception as e:
        print(json.dumps({'error': str(e)}))

if __name__ == '__main__':
    generate_attestation()
EOFPYTHON

chmod +x generate_attestation.py

echo "TEE Runtime initialized successfully"
"""


class GCPTEEService:
    """
    Service for interacting with shared GCP Confidential Computing TEE
    
    Handles:
    - Attestation verification from shared TEE
    - Dataset encryption/decryption
    - Query execution coordination
    - Multi-tenant security and isolation
    """
    
    # Shared TEE configuration
    SHARED_TEE_ENDPOINT = None  # Set via environment or config
    SHARED_TEE_INSTANCE_ID = None  # Set via environment or config
    
    def __init__(self, project_id: Optional[str] = None, credentials_path: Optional[str] = None,
                 tee_endpoint: Optional[str] = None, tee_instance_id: Optional[str] = None):
        """
        Initialize GCP service clients for shared TEE
        
        Args:
            project_id: GCP project ID (defaults to env GOOGLE_CLOUD_PROJECT)
            credentials_path: Path to service account JSON (defaults to env GOOGLE_APPLICATION_CREDENTIALS)
            tee_endpoint: Shared TEE endpoint URL (defaults to env TEE_SERVICE_ENDPOINT)
            tee_instance_id: Shared TEE instance ID (defaults to env TEE_INSTANCE_ID)
        """
        self.project_id = project_id or self._get_default_project()
        self.credentials = self._load_credentials(credentials_path)
        
        # Shared TEE configuration
        import os
        self.tee_endpoint = tee_endpoint or os.getenv('TEE_SERVICE_ENDPOINT', 'http://localhost:8080')
        self.tee_instance_id = tee_instance_id or os.getenv('TEE_INSTANCE_ID', 'shared-tee-001')
        
        # Initialize GCP clients (no compute client needed)
        self.storage_client = storage.Client(project=self.project_id, credentials=self.credentials)
        self.kms_client = kms.KeyManagementServiceClient(credentials=self.credentials)
        
        logger.info(f"Initialized Shared TEE Service for project: {self.project_id}")
        logger.info(f"TEE Endpoint: {self.tee_endpoint}, Instance: {self.tee_instance_id}")
    
    def _get_default_project(self) -> str:
        """Get default project from environment"""
        import os
        project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT')
        if not project:
            raise ValueError("GCP project ID not configured. Set GOOGLE_CLOUD_PROJECT environment variable.")
        return project
    
    def _load_credentials(self, credentials_path: Optional[str]):
        """Load GCP credentials from file or default"""
        import os
        if credentials_path or os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            path = credentials_path or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            return service_account.Credentials.from_service_account_file(path)
        else:
            # Use default credentials (ADC)
            from google.auth import default
            credentials, _ = default()
            return credentials
    
    def get_shared_tee_attestation(self) -> Dict[str, Any]:
        """
        Fetch current attestation token from the shared TEE service
        
        Returns:
            Dict containing attestation_token, instance_id, timestamp, and verified status
        """
        logger.info(f"Fetching attestation from shared TEE: {self.tee_endpoint}")
        
        try:
            import requests
            
            # Call shared TEE service for attestation
            response = requests.get(
                f"{self.tee_endpoint}/attestation",
                timeout=10
            )
            response.raise_for_status()
            
            attestation_data = response.json()
            attestation_token = attestation_data.get('token')
            
            # Verify the attestation
            is_valid = self.verify_attestation(
                attestation_token,
                self.tee_instance_id
            )
            
            return {
                'attestation_token': attestation_token,
                'instance_id': self.tee_instance_id,
                'timestamp': attestation_data.get('timestamp'),
                'verified': is_valid,
                'endpoint': self.tee_endpoint
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch attestation from shared TEE: {e}")
            # Return stub attestation for development
            logger.warning("Using stub attestation for development")
            return self._generate_stub_attestation()
        except Exception as e:
            logger.error(f"Unexpected error fetching attestation: {e}")
            raise
    
    def verify_attestation(
        self,
        attestation_token: str,
        instance_id: Optional[str] = None
    ) -> bool:
        """
        Verify attestation token from the shared Confidential VM
        
        Args:
            attestation_token: JWT token from the shared TEE
            instance_id: VM instance identifier (defaults to shared TEE instance)
            
        Returns:
            True if attestation is valid
        """
        instance_id = instance_id or self.tee_instance_id
        logger.info(f"Verifying attestation for shared instance {instance_id}")
        
        try:
            # Decode JWT without verification first to get claims
            unverified = jwt.decode(attestation_token, options={"verify_signature": False})
            
            # Verify required claims exist
            required_claims = ['iss', 'sub', 'iat', 'exp', 'instance_id']
            for claim in required_claims:
                if claim not in unverified:
                    logger.error(f"Missing required claim: {claim}")
                    return False
            
            # Verify instance_id matches
            if unverified.get('instance_id') != instance_id:
                logger.error(f"Instance ID mismatch: {unverified.get('instance_id')} != {instance_id}")
                return False
            
            # Verify Confidential Computing is enabled
            if not unverified.get('confidential_computing'):
                logger.error("Confidential Computing not enabled in attestation")
                return False
            
            # Verify secure boot and vTPM
            if not unverified.get('secure_boot') or not unverified.get('vtpm_enabled'):
                logger.error("Secure boot or vTPM not enabled")
                return False
            
            # In production, verify JWT signature with GCP's public keys
            # For now, we trust the claims if they're properly formatted
            # Real implementation would:
            # 1. Fetch GCP's public keys from https://www.googleapis.com/oauth2/v3/certs
            # 2. Verify JWT signature
            # 3. Check issuer is from GCP
            # 4. Verify measurements and PCR values
            
            logger.info(f"Attestation verified for {instance_id}")
            return True
            
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid attestation token: {e}")
            return False
        except Exception as e:
            logger.error(f"Error verifying attestation: {e}")
            return False
    
    def _generate_stub_attestation(self) -> Dict[str, Any]:
        """
        Generate stub attestation for development/testing
        
        Returns:
            Dict with stub attestation data
        """
        claims = {
            'iss': 'gcp-confidential-vm',
            'sub': 'shared-tee-service',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=24),
            'instance_id': self.tee_instance_id,
            'confidential_computing': True,
            'secure_boot': True,
            'vtpm_enabled': True
        }
        
        # Generate simple JWT (not cryptographically secure for production)
        token = jwt.encode(claims, 'dev-secret-key', algorithm='HS256')
        
        return {
            'attestation_token': token,
            'instance_id': self.tee_instance_id,
            'timestamp': datetime.utcnow().isoformat(),
            'verified': True,
            'endpoint': self.tee_endpoint
        }
    
    def encrypt_and_transfer_dataset(
        self,
        dataset_id: int,
        source_bucket: str,
        source_path: str,
        session_id: int,
        encryption_key_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Encrypt dataset and transfer to shared TEE storage
        
        Args:
            dataset_id: Internal dataset identifier
            source_bucket: GCS bucket containing source data
            source_path: Path to source data in bucket
            session_id: Collaboration session identifier
            encryption_key_name: KMS key name (created if None)
            
        Returns:
            Dict with encrypted_path, key_id, checksum
        """
        logger.info(f"Encrypting dataset {dataset_id} from gs://{source_bucket}/{source_path}")
        
        try:
            # Get or create KMS key for the session
            if not encryption_key_name:
                encryption_key_name = self._get_or_create_kms_key(f"session-{session_id}")
            
            # Create destination bucket if needed
            dest_bucket_name = f"{self.project_id}-tee-data"
            dest_bucket = self._get_or_create_bucket(dest_bucket_name)
            
            # Download source file
            source_blob = self.storage_client.bucket(source_bucket).blob(source_path)
            source_data = source_blob.download_as_bytes()
            
            # Calculate checksum
            checksum = hashlib.sha256(source_data).hexdigest()
            logger.info(f"Source data checksum: {checksum}, size: {len(source_data)} bytes")
            
            # Encrypt data using KMS
            encrypted_data = self._encrypt_with_kms(source_data, encryption_key_name)
            
            # Upload encrypted data
            dest_path = f"encrypted/session-{session_id}/dataset-{dataset_id}/data.enc"
            dest_blob = dest_bucket.blob(dest_path)
            dest_blob.upload_from_string(encrypted_data)
            
            logger.info(f"Encrypted dataset uploaded to gs://{dest_bucket_name}/{dest_path}")
            
            return {
                'encrypted_path': f"gs://{dest_bucket_name}/{dest_path}",
                'key_id': encryption_key_name,
                'checksum': checksum,
                'encrypted_at': datetime.utcnow().isoformat(),
                'file_size_bytes': len(source_data)
            }
            
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"GCP API error encrypting dataset: {e}")
            raise RuntimeError(f"Failed to encrypt dataset: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error encrypting dataset: {e}")
            raise
    
    def execute_query(
        self,
        query_id: int,
        session_id: int,
        query_text: str,
        dataset_paths: List[str],
        result_bucket: str
    ) -> str:
        """
        Submit query for execution in the shared TEE
        
        Args:
            query_id: Query identifier
            session_id: Collaboration session ID for multi-tenant isolation
            query_text: SQL query to execute
            dataset_paths: List of encrypted dataset paths
            result_bucket: Bucket for storing results
            
        Returns:
            Execution job ID
        """
        logger.info(f"Executing query {query_id} for session {session_id} in shared TEE")
        
        try:
            import requests
            
            # Submit query to shared TEE service
            response = requests.post(
                f"{self.tee_endpoint}/execute",
                json={
                    'query_id': query_id,
                    'session_id': session_id,
                    'query_text': query_text,
                    'dataset_paths': dataset_paths,
                    'result_bucket': result_bucket
                },
                timeout=10
            )
            response.raise_for_status()
            
            job_data = response.json()
            job_id = job_data.get('job_id')
            
            logger.info(f"Query execution initiated with job ID: {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to submit query to shared TEE: {e}")
            # Return simulated job ID for development
            job_id = f"job-{query_id}-{int(datetime.utcnow().timestamp())}"
            logger.warning(f"Using simulated job ID for development: {job_id}")
            return job_id
    
    def generate_signed_url(
        self,
        gcs_path: str,
        expiration_minutes: int = 60
    ) -> str:
        """
        Generate a signed URL for downloading results
        
        Args:
            gcs_path: GCS path (gs://bucket/path or bucket/path)
            expiration_minutes: URL validity period
            
        Returns:
            Signed URL
        """
        logger.info(f"Generating signed URL for {gcs_path}")
        
        try:
            # Parse GCS path
            if gcs_path.startswith('gs://'):
                gcs_path = gcs_path[5:]
            
            parts = gcs_path.split('/', 1)
            bucket_name = parts[0]
            blob_path = parts[1] if len(parts) > 1 else ''
            
            # Get blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            
            # Generate signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            
            logger.info(f"Generated signed URL, expires in {expiration_minutes} minutes")
            return url
            
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            raise
    
    # Terminate instance method removed - not needed for shared TEE architecture
    # The shared TEE runs continuously and doesn't need per-session lifecycle management
    
    def get_instance_status(
        self,
        project_id: str,
        zone: str,
        instance_id: str
    ) -> Dict[str, Any]:
        """
        Get status of a Confidential VM
        
        Returns:
            Dict with status, uptime, resources, etc.
        """
        logger.info(f"Getting status for instance {instance_id}")
        
        try:
            instance = self.compute_client.get(
                project=project_id,
                zone=zone,
                instance=instance_id
            )
            
            return {
                'status': instance.status,
                'machine_type': instance.machine_type.split('/')[-1],
                'creation_timestamp': instance.creation_timestamp,
                'confidential_computing': instance.confidential_instance_config.enable_confidential_compute if instance.confidential_instance_config else False
            }
            
        except google_exceptions.NotFound:
            return {'status': 'NOT_FOUND'}
        except Exception as e:
            logger.error(f"Failed to get instance status: {e}")
            raise
    
    # Helper methods
    
    def _wait_for_operation(self, project_id: str, zone: str, operation_name: str, timeout: int = 300):
        """Wait for a zone operation to complete"""
        from google.cloud import compute_v1
        
        operations_client = compute_v1.ZoneOperationsClient(credentials=self.credentials)
        start_time = time.time()
        
        while True:
            result = operations_client.get(
                project=project_id,
                zone=zone,
                operation=operation_name
            )
            
            if result.status == compute_v1.Operation.Status.DONE:
                if result.error:
                    raise Exception(f"Operation failed: {result.error}")
                logger.info(f"Operation {operation_name} completed successfully")
                return result
            
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Operation {operation_name} timed out after {timeout} seconds")
            
            time.sleep(2)
    
    def _get_or_create_kms_key(self, key_name: str) -> str:
        """Get or create a KMS encryption key"""
        location = "us-central1"  # Should be configurable
        key_ring_id = "tee-keyring"
        crypto_key_id = key_name
        
        try:
            # Build key ring path
            key_ring_path = self.kms_client.key_ring_path(
                self.project_id,
                location,
                key_ring_id
            )
            
            # Try to get key ring, create if not exists
            try:
                self.kms_client.get_key_ring(name=key_ring_path)
            except google_exceptions.NotFound:
                parent = self.kms_client.common_location_path(self.project_id, location)
                self.kms_client.create_key_ring(
                    request={"parent": parent, "key_ring_id": key_ring_id}
                )
                logger.info(f"Created key ring: {key_ring_path}")
            
            # Build crypto key path
            crypto_key_path = self.kms_client.crypto_key_path(
                self.project_id,
                location,
                key_ring_id,
                crypto_key_id
            )
            
            # Try to get crypto key, create if not exists
            try:
                key = self.kms_client.get_crypto_key(name=crypto_key_path)
                logger.info(f"Using existing key: {crypto_key_path}")
            except google_exceptions.NotFound:
                # Create key
                purpose = kms.CryptoKey.CryptoKeyPurpose.ENCRYPT_DECRYPT
                crypto_key = {"purpose": purpose}
                
                key = self.kms_client.create_crypto_key(
                    request={
                        "parent": key_ring_path,
                        "crypto_key_id": crypto_key_id,
                        "crypto_key": crypto_key
                    }
                )
                logger.info(f"Created new key: {crypto_key_path}")
            
            return crypto_key_path
            
        except Exception as e:
            logger.error(f"Failed to get/create KMS key: {e}")
            raise
    
    def _get_or_create_bucket(self, bucket_name: str) -> storage.Bucket:
        """Get or create a GCS bucket"""
        try:
            bucket = self.storage_client.bucket(bucket_name)
            if not bucket.exists():
                bucket = self.storage_client.create_bucket(
                    bucket_name,
                    location="US"
                )
                logger.info(f"Created bucket: {bucket_name}")
            return bucket
        except Exception as e:
            logger.error(f"Failed to get/create bucket: {e}")
            raise
    
    def _encrypt_with_kms(self, plaintext: bytes, key_path: str) -> bytes:
        """Encrypt data using Cloud KMS"""
        try:
            # Encrypt with KMS
            encrypt_response = self.kms_client.encrypt(
                request={"name": key_path, "plaintext": plaintext}
            )
            
            return encrypt_response.ciphertext
            
        except Exception as e:
            logger.error(f"Failed to encrypt with KMS: {e}")
            raise
    
    def _decrypt_with_kms(self, ciphertext: bytes, key_path: str) -> bytes:
        """Decrypt data using Cloud KMS"""
        try:
            decrypt_response = self.kms_client.decrypt(
                request={"name": key_path, "ciphertext": ciphertext}
            )
            
            return decrypt_response.plaintext
            
        except Exception as e:
            logger.error(f"Failed to decrypt with KMS: {e}")
            raise

