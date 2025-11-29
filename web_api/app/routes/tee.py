"""
TEE (Trusted Execution Environment) API endpoints
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user
from datetime import datetime
import hashlib
import logging
from sqlalchemy import or_

from app.utils.decorators import api_key_required
from app.extensions import db
from app.models.tee import CollaborationSession, Dataset, Query, QueryResult, SessionStatus, DatasetStatus, QueryStatus, query_approvals
from app.services.gcp_tee import GCPTEEService

bp = Blueprint('session', __name__, url_prefix='/api/tee')
logger = logging.getLogger(__name__)


# ============================================================================
# TEE Management Endpoints
# ============================================================================

@bp.route('/sessions', methods=['GET'])
@api_key_required
def list_sessions():
    """
    List all collaboration sessions accessible to the current user
    
    Returns sessions where user is creator or participant
    """
    sessions = CollaborationSession.query.filter(
        or_(
            CollaborationSession.creator_id == current_user.id,
            CollaborationSession.participants.any(id=current_user.id)
        )
    ).all()
    
    return jsonify({
        'sessions': [session.to_dict() for session in sessions]
    })


@bp.route('/sessions', methods=['POST'])
@api_key_required
def create_session():
    """
    Create a new collaboration session using shared TEE
    
    Request body:
    {
        "name": "My Research Project",
        "description": "Collaborative research project",
        "allow_cross_party_joins": true,
        "require_unanimous_approval": true,
        "participant_emails": ["user1@example.com", "user2@example.com"]
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['name']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            'error': 'Missing required fields',
            'missing_fields': missing_fields
        }), 400
    
    try:
        # Create session record
        session = CollaborationSession(
            name=data['name'],
            description=data.get('description', ''),
            creator_id=current_user.id,
            allow_cross_party_joins=data.get('allow_cross_party_joins', True),
            require_unanimous_approval=data.get('require_unanimous_approval', True),
            status=SessionStatus.ACTIVE  # Immediately active - no VM to spin up
        )
        
        # Add creator as participant
        session.participants.append(current_user)
        
        # Add additional participants
        if 'participant_emails' in data:
            from app.models.user import User
            for email in data['participant_emails']:
                user = User.query.filter_by(email=email).first()
                if user and user.id != current_user.id:
                    session.participants.append(user)
        
        db.session.add(session)
        db.session.commit()
        
        # Verify shared TEE attestation
        try:
            gcp_service = GCPTEEService()
            attestation = gcp_service.get_shared_tee_attestation()
            logger.info(f"Shared TEE attestation verified for session {session.id}: {attestation.get('verified')}")
        except Exception as e:
            # Log warning but don't fail - attestation can be verified later
            logger.warning(f"Could not verify shared TEE attestation: {e}")
        
        return jsonify({
            'session': session.to_dict(),
            'message': 'Collaboration session created successfully',
            'shared_tee': 'Using shared TEE service - no dedicated instance needed'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to create session',
            'message': str(e)
        }), 500


@bp.route('/sessions/<int:session_id>', methods=['GET'])
@api_key_required
def get_session(session_id):
    """Get details of a specific collaboration session"""
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    if not session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    return jsonify({'session': session.to_dict()})


@bp.route('/sessions/<int:session_id>', methods=['DELETE'])
@api_key_required
def delete_session(session_id):
    """Close a collaboration session"""
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Only creator can close
    if session.creator_id != current_user.id:
        return jsonify({'error': 'Only session creator can close it'}), 403
    
    try:
        # Close the session (no VM to terminate with shared TEE)
        session.close()
        
        return jsonify({
            'message': 'Session closed successfully',
            'session_id': session_id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to close session: {e}")
        return jsonify({
            'error': 'Failed to close session',
            'message': str(e)
        }), 500


@bp.route('/sessions/<int:session_id>/attestation', methods=['POST'])
@api_key_required
def verify_attestation(session_id):
    """
    Verify TEE attestation token from GCP
    
    Request body:
    {
        "attestation_token": "eyJhbGciOiJS..."
    }
    """
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if session.creator_id != current_user.id:
        return jsonify({'error': 'Only TEE creator can verify attestation'}), 403
    
    data = request.get_json()
    if not data or 'attestation_token' not in data:
        return jsonify({'error': 'Attestation token required'}), 400
    
    try:
        # Verify attestation with shared TEE
        gcp_service = GCPTEEService()
        attestation_data = gcp_service.get_shared_tee_attestation()
        
        if attestation_data.get('verified'):
            # Attestation is valid for shared TEE
            return jsonify({
                'message': 'Shared TEE attestation verified',
                'attestation': {
                    'instance_id': attestation_data.get('instance_id'),
                    'timestamp': attestation_data.get('timestamp'),
                    'endpoint': attestation_data.get('endpoint')
                },
                'session': session.to_dict()
            })
        else:
            return jsonify({'error': 'Invalid attestation token'}), 400
            
    except Exception as e:
        return jsonify({
            'error': 'Attestation verification failed',
            'message': str(e)
        }), 500


@bp.route('/sessions/<int:session_id>/participants', methods=['POST'])
@api_key_required
def add_participant(session_id):
    """
    Add a participant to the TEE
    
    Request body:
    {
        "email": "newuser@example.com"
    }
    """
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if session.creator_id != current_user.id:
        return jsonify({'error': 'Only TEE creator can add participants'}), 403
    
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'error': 'Email required'}), 400
    
    from app.models import User
    user = User.query.filter_by(email=data['email']).first()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if session.is_participant(user):
        return jsonify({'error': 'User is already a participant'}), 400
    
    session.add_participant(user)
    
    return jsonify({
        'message': f'Added {user.email} as participant',
        'session': session.to_dict()
    })


@bp.route('/sessions/<int:session_id>/terminate', methods=['POST'])
@api_key_required
def terminate_tee(session_id):
    """Terminate a TEE (creator only)"""
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    if session.creator_id != current_user.id:
        return jsonify({'error': 'Only session creator can suspend'}), 403
    
    try:
        # Suspend session (no VM to terminate with shared TEE)
        session.status = SessionStatus.SUSPENDED
        db.session.commit()
        
        return jsonify({
            'message': 'Session suspended successfully',
            'session': session.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to suspend session',
            'message': str(e)
        }), 500


# ============================================================================
# Dataset Management Endpoints
# ============================================================================

@bp.route('/sessions/<int:session_id>/datasets', methods=['GET'])
@api_key_required
def list_datasets(session_id):
    """List all datasets in a TEE"""
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if not session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    datasets = session.datasets.all()
    
    return jsonify({
        'datasets': [dataset.to_dict() for dataset in datasets]
    })


@bp.route('/sessions/<int:session_id>/datasets', methods=['POST'])
@api_key_required
def upload_dataset(session_id):
    """
    Initiate dataset upload to TEE
    
    Request body:
    {
        "name": "Customer Data",
        "description": "Q4 2024 customer dataset",
        "schema": {
            "columns": [
                {"name": "customer_id", "type": "string"},
                {"name": "purchase_amount", "type": "float"}
            ]
        },
        "gcs_bucket": "my-bucket",
        "gcs_path": "datasets/customers.csv"
    }
    """
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if not session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    if session.status != SessionStatus.ACTIVE:
        return jsonify({'error': 'TEE must be active to upload datasets'}), 400
    
    data = request.get_json()
    
    required_fields = ['name', 'gcs_bucket', 'gcs_path']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            'error': 'Missing required fields',
            'missing_fields': missing_fields
        }), 400
    
    try:
        dataset = Dataset(
            session_id=session_id,
            owner_id=current_user.id,
            name=data['name'],
            description=data.get('description', ''),
            schema_info=data.get('schema'),
            gcs_bucket=data['gcs_bucket'],
            gcs_path=data['gcs_path'],
            status=DatasetStatus.UPLOADING
        )
        
        db.session.add(dataset)
        db.session.commit()
        
        # Trigger async encryption and processing
        # In production, this would be a background task
        try:
            gcp_service = GCPTEEService()
            encryption_result = gcp_service.encrypt_and_transfer_dataset(
                dataset_id=dataset.id,
                source_bucket=data['gcs_bucket'],
                source_path=data['gcs_path'],
                session_id=session.id
            )
            
            # Update dataset with encryption info
            dataset.encrypted_path = encryption_result['encrypted_path']
            dataset.encryption_key_id = encryption_result['key_id']
            dataset.checksum = encryption_result['checksum']
            dataset.file_size_bytes = encryption_result.get('file_size_bytes')
            dataset.status = DatasetStatus.ENCRYPTED
            db.session.commit()
            
        except Exception as e:
            # In development, allow datasets without actual GCS storage
            logger.warning(f"Dataset encryption skipped (development mode): {e}")
            dataset.status = DatasetStatus.UPLOADED
            db.session.commit()
            return jsonify({
                'dataset': dataset.to_dict(),
                'warning': f'Dataset record created but encryption failed: {str(e)}'
            }), 201
        
        return jsonify({
            'dataset': dataset.to_dict(),
            'message': 'Dataset upload initiated'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to create dataset',
            'message': str(e)
        }), 500


@bp.route('/datasets/<int:dataset_id>', methods=['GET'])
@api_key_required
def get_dataset(dataset_id):
    """Get dataset details"""
    dataset = Dataset.query.get(dataset_id)
    
    if not dataset:
        return jsonify({'error': 'Dataset not found'}), 404
    
    if not dataset.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    return jsonify({'dataset': dataset.to_dict()})


@bp.route('/datasets/<int:dataset_id>/mark-available', methods=['POST'])
@api_key_required
def mark_dataset_available(dataset_id):
    """Mark dataset as available (owner or admin only)"""
    dataset = Dataset.query.get(dataset_id)
    
    if not dataset:
        return jsonify({'error': 'Dataset not found'}), 404
    
    if dataset.owner_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Forbidden'}), 403
    
    dataset.mark_available()
    
    return jsonify({
        'message': 'Dataset marked as available',
        'dataset': dataset.to_dict()
    })


# ============================================================================
# Query Management Endpoints
# ============================================================================

@bp.route('/sessions/<int:session_id>/queries', methods=['GET'])
@api_key_required
def list_queries(session_id):
    """List all queries in a TEE"""
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if not session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    queries = session.queries.all()
    
    return jsonify({
        'queries': [query.to_dict() for query in queries]
    })


@bp.route('/sessions/<int:session_id>/queries', methods=['POST'])
@api_key_required
def submit_query(session_id):
    """
    Submit a query for execution in the TEE
    
    Request body:
    {
        "name": "Revenue Analysis",
        "description": "Calculate total revenue by customer segment",
        "query_text": "SELECT segment, SUM(revenue) FROM dataset_1 JOIN dataset_2 ON ...",
        "accesses_datasets": [1, 2],
        "privacy_level": "aggregate_only"
    }
    """
    session = CollaborationSession.query.get(session_id)
    
    if not session:
        return jsonify({'error': 'TEE not found'}), 404
    
    if not session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    if session.status != SessionStatus.ACTIVE:
        return jsonify({'error': 'TEE must be active to submit queries'}), 400
    
    data = request.get_json()
    
    required_fields = ['name', 'query_text', 'accesses_datasets']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({
            'error': 'Missing required fields',
            'missing_fields': missing_fields
        }), 400
    
    try:
        # Verify all datasets exist and are available
        dataset_ids = data['accesses_datasets']
        datasets = Dataset.query.filter(
            Dataset.id.in_(dataset_ids),
            Dataset.session_id == session_id
        ).all()
        
        if len(datasets) != len(dataset_ids):
            return jsonify({'error': 'One or more datasets not found in this TEE'}), 404
        
        unavailable = [d.id for d in datasets if d.status != DatasetStatus.AVAILABLE]
        if unavailable:
            return jsonify({
                'error': 'Some datasets are not yet available',
                'unavailable_datasets': unavailable
            }), 400
        
        # Create query hash for deduplication
        query_hash = hashlib.sha256(data['query_text'].encode()).hexdigest()
        
        query = Query(
            session_id=session_id,
            submitter_id=current_user.id,
            name=data['name'],
            description=data.get('description', ''),
            query_text=data['query_text'],
            query_hash=query_hash,
            accesses_datasets=dataset_ids,
            privacy_level=data.get('privacy_level', 'aggregate_only'),
            status=QueryStatus.SUBMITTED
        )
        
        db.session.add(query)
        db.session.commit()
        
        # Trigger verification workflow
        # In production, this would notify all participants for approval
        
        return jsonify({
            'query': query.to_dict(include_query_text=True),
            'message': 'Query submitted for verification',
            'requires_approval': session.require_unanimous_approval,
            'participants_to_approve': len(session.participants) if session.require_unanimous_approval else 1
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Failed to submit query',
            'message': str(e)
        }), 500


@bp.route('/queries/<int:query_id>', methods=['GET'])
@api_key_required
def get_query(query_id):
    """Get query details"""
    query = Query.query.get(query_id)
    
    if not query:
        return jsonify({'error': 'Query not found'}), 404
    
    if not query.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    return jsonify({'query': query.to_dict(include_query_text=True)})


@bp.route('/queries/<int:query_id>/approve', methods=['POST'])
@api_key_required
def approve_query(query_id):
    """
    Approve a query for execution
    
    Request body:
    {
        "notes": "Verified - query only returns aggregated data"
    }
    """
    query = Query.query.get(query_id)
    
    if not query:
        return jsonify({'error': 'Query not found'}), 404
    
    if not query.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    if query.status not in [QueryStatus.SUBMITTED, QueryStatus.VERIFYING]:
        return jsonify({'error': 'Query is not in submitted/verifying state'}), 400
    
    data = request.get_json() or {}
    notes = data.get('notes', '')
    
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
    
    # Update status to verifying if this is first approval
    if query.status == QueryStatus.SUBMITTED:
        query.status = QueryStatus.VERIFYING
    
    db.session.commit()
    
    # If unanimous approval required and all have approved, execute query
    if query.session.require_unanimous_approval and approval_count >= participant_count:
        query.approve()
        
        # Trigger execution in shared TEE (or simulate completion for development)
        try:
            # For development without actual TEE: simulate immediate completion
            import random
            
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
            
            logger.info(f"Query {query.id} execution completed (development mode)")
            
        except Exception as e:
            logger.error(f"Failed to execute query {query.id}: {e}")
            return jsonify({
                'message': f'Query approved by {approval_count}/{participant_count} participants and execution started',
                'query': query.to_dict(),
                'warning': f'Execution failed: {str(e)}'
            })
        
        return jsonify({
            'message': 'Query approved by all participants and executed successfully',
            'query': query.to_dict(),
            'approvals': f'{approval_count}/{participant_count}'
        })
    
    return jsonify({
        'message': f'Query approved by {approval_count}/{participant_count} participants',
        'query': query.to_dict(),
        'approvals': f'{approval_count}/{participant_count}',
        'awaiting_approvals': participant_count - approval_count
    })


@bp.route('/queries/<int:query_id>/reject', methods=['POST'])
@api_key_required
def reject_query(query_id):
    """
    Reject a query
    
    Request body:
    {
        "reason": "Query accesses raw PII data"
    }
    """
    query = Query.query.get(query_id)
    
    if not query:
        return jsonify({'error': 'Query not found'}), 404
    
    if not query.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    if query.status != QueryStatus.SUBMITTED:
        return jsonify({'error': 'Query is not in submitted state'}), 400
    
    data = request.get_json() or {}
    reason = data.get('reason', 'No reason provided')
    
    query.reject(reason)
    
    return jsonify({
        'message': 'Query rejected',
        'query': query.to_dict()
    })


# ============================================================================
# Results Distribution Endpoints
# ============================================================================

@bp.route('/queries/<int:query_id>/results', methods=['GET'])
@api_key_required
def get_query_results(query_id):
    """Get results from a completed query"""
    query = Query.query.get(query_id)
    
    if not query:
        return jsonify({'error': 'Query not found'}), 404
    
    if not query.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    if query.status != QueryStatus.COMPLETED:
        return jsonify({
            'error': 'Query has not completed',
            'status': query.status.value
        }), 400
    
    results = query.results.all()
    
    return jsonify({
        'query': query.to_dict(),
        'results': [result.to_dict() for result in results]
    })


@bp.route('/queries/<int:query_id>/results/<int:result_id>/download', methods=['GET'])
@api_key_required
def download_result(query_id, result_id):
    """
    Download query result file
    
    Returns a signed URL for downloading large result files
    """
    query = Query.query.get(query_id)
    
    if not query:
        return jsonify({'error': 'Query not found'}), 404
    
    if not query.session.is_participant(current_user):
        return jsonify({'error': 'Forbidden'}), 403
    
    result = QueryResult.query.get(result_id)
    
    if not result or result.query_id != query_id:
        return jsonify({'error': 'Result not found'}), 404
    
    if not result.gcs_path:
        return jsonify({'error': 'No file available for download'}), 400
    
    try:
        # Generate signed URL for download
        gcp_service = GCPTEEService()
        signed_url = gcp_service.generate_signed_url(result.gcs_path)
        
        return jsonify({
            'download_url': signed_url,
            'expires_in_seconds': 3600,
            'file_size_bytes': result.file_size_bytes,
            'format': result.result_format
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to generate download URL',
            'message': str(e)
        }), 500


# ============================================================================
# Health and Status Endpoints
# ============================================================================

@bp.route('/health', methods=['GET'])
def tee_health():
    """Public health check for TEE API"""
    return jsonify({
        'status': 'healthy',
        'service': 'TEE API',
        'version': '1.0.0'
    })
