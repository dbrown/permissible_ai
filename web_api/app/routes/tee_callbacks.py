"""
TEE Callback routes - Receive status updates from TEE server

These endpoints are called by the TEE server to notify the control plane
about dataset upload completion, query results, etc.
"""
import logging
import os
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.tee import Dataset, Query, DatasetStatus, QueryStatus
import requests

logger = logging.getLogger(__name__)

bp = Blueprint('tee_callbacks', __name__, url_prefix='/api/tee')


@bp.route('/attestation-proxy', methods=['GET', 'OPTIONS'])
def attestation_proxy():
    """
    CORS-enabled proxy for TEE attestation endpoint
    Allows browser clients to fetch attestation from TEE server
    """
    # Handle preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        from flask import current_app
        tee_endpoint = current_app.config.get('TEE_SERVICE_ENDPOINT')
        
        if not tee_endpoint:
            raise ValueError("TEE_SERVICE_ENDPOINT not configured in Flask app")
            
        logger.info(f"Proxying attestation request to: {tee_endpoint}/attestation")
        response = requests.get(f"{tee_endpoint}/attestation", timeout=10)
        response.raise_for_status()
        
        result = jsonify(response.json())
        result.headers['Access-Control-Allow-Origin'] = '*'
        return result
        
    except Exception as e:
        logger.error(f"Attestation proxy error: {e}")
        # Return more detailed error for debugging
        error_msg = f"{type(e).__name__}: {str(e)}"
        if 'tee_endpoint' in locals() and tee_endpoint:
             error_msg += f" (Endpoint: {tee_endpoint})"
             
        error_response = jsonify({'error': error_msg})
        error_response.headers['Access-Control-Allow-Origin'] = '*'
        return error_response, 500


@bp.route('/callback', methods=['POST'])
def tee_callback():
    """
    Receive status updates from TEE server
    
    Payload:
    {
        "entity_type": "dataset" | "query",
        "entity_id": 123,
        "status": "available" | "failed" | "completed",
        "metadata": {...},
        "timestamp": "2024-01-01T00:00:00"
    }
    """
    try:
        data = request.json
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        status = data.get('status')
        metadata = data.get('metadata', {})
        
        logger.info(f"TEE callback: {entity_type} {entity_id} -> {status}")
        
        # TODO: Verify callback signature from TEE private key
        
        if entity_type == 'dataset':
            dataset = Dataset.query.get(entity_id)
            if not dataset:
                return jsonify({'error': 'Dataset not found'}), 404
            
            # Update dataset status
            if status == 'available':
                dataset.status = DatasetStatus.AVAILABLE
                dataset.checksum = metadata.get('checksum')
                dataset.file_size_bytes = metadata.get('file_size')
            elif status == 'failed':
                dataset.status = DatasetStatus.FAILED
                dataset.error_message = metadata.get('error')
            
            db.session.commit()
            logger.info(f"Updated dataset {entity_id} status to {status}")
            
        elif entity_type == 'query':
            query = Query.query.get(entity_id)
            if not query:
                return jsonify({'error': 'Query not found'}), 404
            
            # Update query status
            if status == 'completed':
                query.status = QueryStatus.COMPLETED
                query.completed_at = metadata.get('executed_at')
                # Store result reference
                # ... create QueryResult record ...
            elif status == 'failed':
                query.status = QueryStatus.ERROR
                query.error_message = metadata.get('error')
            
            db.session.commit()
            logger.info(f"Updated query {entity_id} status to {status}")
        
        else:
            return jsonify({'error': f'Unknown entity type: {entity_type}'}), 400
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"TEE callback error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
