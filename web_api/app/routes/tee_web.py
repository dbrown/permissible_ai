"""
TEE Web UI routes - browser-based interface for collaboration sessions
"""
import logging
import os
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app.extensions import db
from app.models.tee import (
    CollaborationSession, Dataset, Query, QueryResult, 
    SessionStatus, DatasetStatus, QueryStatus, 
    query_approvals
)
from app.models.user import User
from app.services.gcp_tee import GCPTEEService

logger = logging.getLogger(__name__)
bp = Blueprint('tee_web', __name__, url_prefix='/collaborations')


@bp.route('/')
@login_required
def sessions():
    """List all collaboration sessions accessible to the user"""
    user_sessions = CollaborationSession.query.filter(
        or_(
            CollaborationSession.creator_id == current_user.id,
            CollaborationSession.participants.any(id=current_user.id)
        )
    ).order_by(CollaborationSession.created_at.desc()).all()
    
    return render_template('tee/sessions.html', sessions=user_sessions)


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_session():
    """Create a new collaboration session"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        participant_emails = request.form.get('participant_emails', '')
        allow_cross_party_joins = request.form.get('allow_cross_party_joins') == 'on'
        require_unanimous = request.form.get('require_unanimous_approval') == 'on'
        
        if not name:
            flash('Session name is required', 'error')
            return redirect(url_for('tee_web.create_session'))
        
        # Create session
        session = CollaborationSession(
            name=name,
            description=description,
            creator_id=current_user.id,
            allow_cross_party_joins=allow_cross_party_joins,
            require_unanimous_approval=require_unanimous,
            status=SessionStatus.ACTIVE
        )
        
        # Add creator as participant
        session.participants.append(current_user)
        
        # Add other participants
        if participant_emails:
            emails = [e.strip() for e in participant_emails.split(',') if e.strip()]
            for email in emails:
                user = User.query.filter_by(email=email).first()
                if user and user.id != current_user.id:
                    session.participants.append(user)
                elif not user:
                    flash(f'User {email} not found - skipped', 'warning')
        
        db.session.add(session)
        db.session.commit()
        
        flash(f'Collaboration session "{name}" created successfully!', 'success')
        return redirect(url_for('tee_web.session_detail', session_id=session.id))
    
    return render_template('tee/create_session.html')


@bp.route('/<int:session_id>')
@login_required
def session_detail(session_id):
    """View collaboration session details"""
    session = CollaborationSession.query.get_or_404(session_id)
    
    if not session.is_participant(current_user):
        flash('You do not have access to this collaboration session', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    # Get datasets
    datasets = session.datasets.all()
    
    # Get queries with approval status
    queries = session.queries.order_by(Query.submitted_at.desc()).all()
    
    # Get approval counts for each query
    query_approvals_data = {}
    for query in queries:
        approvals = db.session.query(query_approvals).filter_by(
            query_id=query.id,
            approved=True
        ).all()
        
        user_approved = db.session.query(query_approvals).filter_by(
            query_id=query.id,
            user_id=current_user.id,
            approved=True
        ).first() is not None
        
        query_approvals_data[query.id] = {
            'count': len(approvals),
            'required': len(session.participants),
            'user_approved': user_approved,
            'approvers': [db.session.get(User, a[1]) for a in approvals]
        }
    
    return render_template(
        'tee/session_detail.html',
        session=session,
        datasets=datasets,
        queries=queries,
        query_approvals_data=query_approvals_data
    )


@bp.route('/<int:session_id>/datasets/upload', methods=['GET', 'POST'])
@login_required
def upload_dataset(session_id):
    """Upload a dataset to a collaboration session (client-side encryption)"""
    session = CollaborationSession.query.get_or_404(session_id)
    
    if not session.is_participant(current_user):
        flash('You do not have access to this collaboration session', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    # Validate session is active
    if session.status != SessionStatus.ACTIVE:
        flash('TEE session must be active to upload datasets', 'error')
        return redirect(url_for('tee_web.session_detail', session_id=session_id))
    
    if request.method == 'POST':
        # This is just creating the metadata record - actual upload happens client-side
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Dataset name is required', 'error')
            return redirect(url_for('tee_web.upload_dataset', session_id=session_id))
        
        # Create dataset metadata record (status will be updated by TEE via callback)
        dataset = Dataset(
            session_id=session.id,
            owner_id=current_user.id,
            name=name,
            description=description,
            status=DatasetStatus.PENDING  # Waiting for client upload
        )
        
        db.session.add(dataset)
        db.session.commit()
        
        # Return the dataset ID so client can complete the upload
        return redirect(url_for('tee_web.upload_dataset_client', 
                              session_id=session.id, 
                              dataset_id=dataset.id))
    
    # Get TEE endpoint for client-side upload
    tee_endpoint = os.getenv('TEE_SERVICE_ENDPOINT', 'http://localhost:8080')
    
    return render_template('tee/upload_dataset.html', 
                         session=session,
                         tee_endpoint=tee_endpoint)


@bp.route('/<int:session_id>/datasets/<int:dataset_id>/upload-client', methods=['GET'])
@login_required
def upload_dataset_client(session_id, dataset_id):
    """Client-side encrypted upload page"""
    session = CollaborationSession.query.get_or_404(session_id)
    dataset = Dataset.query.get_or_404(dataset_id)
    
    if not session.is_participant(current_user):
        flash('You do not have access to this collaboration session', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    if dataset.owner_id != current_user.id:
        flash('You can only upload your own datasets', 'error')
        return redirect(url_for('tee_web.session_detail', session_id=session_id))
    
    # Get TEE endpoint and generate upload token
    tee_endpoint = os.getenv('TEE_SERVICE_ENDPOINT', 'http://localhost:8080')
    
    # Generate a short-lived upload token for this dataset
    upload_token = jwt.encode(
        {
            'dataset_id': dataset.id,
            'session_id': session.id,
            'user_id': current_user.id,
            'exp': datetime.utcnow() + timedelta(hours=1)
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return render_template('tee/upload_dataset_client.html',
                         session=session,
                         dataset=dataset,
                         tee_endpoint=tee_endpoint,
                         upload_token=upload_token)


@bp.route('/<int:session_id>/queries/submit', methods=['GET', 'POST'])
@login_required
def submit_query(session_id):
    """Submit a query for execution"""
    session = CollaborationSession.query.get_or_404(session_id)
    
    if not session.is_participant(current_user):
        flash('You do not have access to this collaboration session', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    datasets = session.datasets.filter_by(status=DatasetStatus.AVAILABLE).all()
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        query_text = request.form.get('query_text')
        dataset_ids = request.form.getlist('datasets')
        privacy_level = request.form.get('privacy_level', 'aggregate_only')
        
        if not all([name, query_text, dataset_ids]):
            flash('Query name, SQL, and datasets are required', 'error')
            return redirect(url_for('tee_web.submit_query', session_id=session_id))
        
        # Create query
        import hashlib
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        
        query = Query(
            session_id=session.id,
            submitter_id=current_user.id,
            name=name,
            description=description,
            query_text=query_text,
            query_hash=query_hash,
            accesses_datasets=[int(d) for d in dataset_ids],
            privacy_level=privacy_level,
            status=QueryStatus.SUBMITTED
        )
        
        db.session.add(query)
        db.session.commit()
        
        flash(f'Query "{name}" submitted for approval!', 'success')
        return redirect(url_for('tee_web.query_detail', query_id=query.id))
    
    return render_template(
        'tee/submit_query.html',
        session=session,
        datasets=datasets
    )


@bp.route('/queries/<int:query_id>')
@login_required
def query_detail(query_id):
    """View query details and approval status"""
    query = Query.query.get_or_404(query_id)
    
    if not query.session.is_participant(current_user):
        flash('You do not have access to this query', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    # Get approval details
    approvals = db.session.query(query_approvals).filter_by(query_id=query.id).all()
    
    approval_details = []
    for approval in approvals:
        user = db.session.get(User, approval[1])
        approval_details.append({
            'user': user,
            'approved': approval[2],
            'approved_at': approval[3],
            'notes': approval[4]
        })
    
    user_approved = any(a['user'].id == current_user.id and a['approved'] for a in approval_details)
    
    # Get datasets accessed
    accessed_datasets = []
    if query.accesses_datasets:
        accessed_datasets = Dataset.query.filter(Dataset.id.in_(query.accesses_datasets)).all()
    
    # Get results if completed
    results = None
    if query.status == QueryStatus.COMPLETED:
        results = query.results.first()
    
    return render_template(
        'tee/query_detail.html',
        query=query,
        approval_details=approval_details,
        user_approved=user_approved,
        accessed_datasets=accessed_datasets,
        results=results
    )


@bp.route('/queries/<int:query_id>/approve', methods=['POST'])
@login_required
def approve_query(query_id):
    """Approve a query"""
    query = Query.query.get_or_404(query_id)
    
    if not query.session.is_participant(current_user):
        flash('You do not have access to this query', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    if query.status not in [QueryStatus.SUBMITTED, QueryStatus.VERIFYING]:
        flash('Query is not in a state that can be approved', 'warning')
        return redirect(url_for('tee_web.query_detail', query_id=query.id))
    
    # Check if already approved
    existing = db.session.query(query_approvals).filter_by(
        query_id=query.id,
        user_id=current_user.id
    ).first()
    
    if existing:
        flash('You have already approved this query', 'warning')
        return redirect(url_for('tee_web.query_detail', query_id=query.id))
    
    notes = request.form.get('notes', '')
    
    # Record approval
    db.session.execute(
        query_approvals.insert().values(
            query_id=query.id,
            user_id=current_user.id,
            approved=True,
            notes=notes
        )
    )
    
    # Check approval count
    approval_count = db.session.query(query_approvals).filter_by(
        query_id=query.id,
        approved=True
    ).count()
    
    participant_count = len(query.session.participants)
    
    # Update status
    if query.status == QueryStatus.SUBMITTED:
        query.status = QueryStatus.VERIFYING
    
    db.session.commit()
    
    # If all approved, execute
    if query.session.require_unanimous_approval and approval_count >= participant_count:
        query.approve()
        
        # Execute query (mock for development)
        import random
        mock_results = {
            'columns': ['metric', 'value', 'count'],
            'rows': [
                ['Metric A', round(random.uniform(50, 100), 2), random.randint(100, 500)],
                ['Metric B', round(random.uniform(50, 100), 2), random.randint(100, 500)],
                ['Metric C', round(random.uniform(50, 100), 2), random.randint(100, 500)]
            ]
        }
        
        result = QueryResult(
            query_id=query.id,
            result_data=mock_results,
            result_format='json',
            row_count=len(mock_results['rows']),
            file_size_bytes=len(str(mock_results))
        )
        db.session.add(result)
        query.complete(execution_time=round(random.uniform(0.5, 2.0), 2))
        
        flash('Query fully approved and executed!', 'success')
    else:
        flash(f'Query approved ({approval_count}/{participant_count} approvals)', 'success')
    
    return redirect(url_for('tee_web.query_detail', query_id=query.id))


@bp.route('/queries/<int:query_id>/reject', methods=['POST'])
@login_required
def reject_query(query_id):
    """Reject a query"""
    query = Query.query.get_or_404(query_id)
    
    if not query.session.is_participant(current_user):
        flash('You do not have access to this query', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    if query.status != QueryStatus.SUBMITTED:
        flash('Query is not in a state that can be rejected', 'warning')
        return redirect(url_for('tee_web.query_detail', query_id=query.id))
    
    reason = request.form.get('reason', 'No reason provided')
    query.reject(reason)
    
    flash('Query rejected', 'success')
    return redirect(url_for('tee_web.query_detail', query_id=query.id))


@bp.route('/queries/<int:query_id>/results')
@login_required
def query_results(query_id):
    """View query results"""
    query = Query.query.get_or_404(query_id)
    
    if not query.session.is_participant(current_user):
        flash('You do not have access to this query', 'error')
        return redirect(url_for('tee_web.sessions'))
    
    if query.status != QueryStatus.COMPLETED:
        flash('Query has not completed yet', 'warning')
        return redirect(url_for('tee_web.query_detail', query_id=query.id))
    
    results = query.results.all()
    
    return render_template(
        'tee/query_results.html',
        query=query,
        results=results
    )
