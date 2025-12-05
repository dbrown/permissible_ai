"""
Dataset Web UI routes - browser-based interface for dataset management
"""
import logging
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.tee import Dataset, DatasetStatus
from app.services.gcp_tee import GCPTEEService

logger = logging.getLogger(__name__)
bp = Blueprint('datasets_web', __name__, url_prefix='/datasets')


@bp.route('/')
@login_required
def list_datasets():
    """List all datasets owned by the user"""
    datasets = Dataset.query.filter_by(owner_id=current_user.id).order_by(Dataset.uploaded_at.desc()).all()
    
    # Fetch metadata from TEE
    dataset_ids = [d.id for d in datasets]
    tee_service = GCPTEEService()
    dataset_info = tee_service.get_datasets_info(dataset_ids)
    
    return render_template('datasets/index.html', datasets=datasets, dataset_info=dataset_info)


@bp.route('/public')
def public_files():
    """List all public files in the system"""
    datasets = Dataset.query.filter_by(is_public=True).order_by(Dataset.uploaded_at.desc()).all()
    return render_template('datasets/public_explorer.html', datasets=datasets)


@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_dataset():
    """Upload a new dataset (independent of session)"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        is_public = request.form.get('is_public') == 'on'
        
        if not name:
            flash('Dataset name is required', 'error')
            return redirect(url_for('datasets_web.upload_dataset'))
        
        # Create dataset record
        dataset = Dataset(
            name=name,
            description=description,
            owner_id=current_user.id,
            status=DatasetStatus.PENDING,
            is_public=is_public
        )
        
        db.session.add(dataset)
        db.session.commit()
        
        # Get TEE upload URL/Token
        # Note: In the independent flow, we might not have a session_id to pass.
        # The TEE server needs to be able to accept uploads with just a dataset_id.
        try:
            gcp_service = GCPTEEService()
            # We need to ensure the TEE service supports this. 
            # For now, we assume the existing mechanism works or we'll need to update it.
            # The current flow likely generates a token.
            pass
        except Exception as e:
            logger.error(f"Failed to initialize TEE service: {e}")
            # Continue anyway for now as the client-side upload might handle the connection
        
        flash(f'Dataset "{name}" created. Proceeding to upload...', 'success')
        # Redirect to the upload page which will handle the JS upload to TEE
        return redirect(url_for('datasets_web.perform_upload', dataset_id=dataset.id))
    
    return render_template('datasets/upload.html')


@bp.route('/<int:dataset_id>/upload')
@login_required
def perform_upload(dataset_id):
    """Page that executes the JS upload to TEE"""
    dataset = Dataset.query.get_or_404(dataset_id)
    
    if dataset.owner_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('datasets_web.list_datasets'))
    
    # Get TEE endpoint
    tee_endpoint = current_app.config.get('TEE_SERVICE_ENDPOINT', '')
    
    # Generate a short-lived upload token for this dataset
    # Note: session_id is None for independent uploads
    upload_token = jwt.encode(
        {
            'dataset_id': dataset.id,
            'session_id': None,
            'user_id': current_user.id,
            'exp': datetime.utcnow() + timedelta(hours=1)
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
        
    return render_template('datasets/perform_upload.html', 
                          dataset=dataset,
                          tee_endpoint=tee_endpoint,
                          upload_token=upload_token)


@bp.route('/<int:dataset_id>/delete', methods=['POST'])
@login_required
def delete_dataset(dataset_id):
    """Delete a dataset"""
    dataset = Dataset.query.get_or_404(dataset_id)
    
    if dataset.owner_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('datasets_web.list_datasets'))
    
    # Check if used in any sessions
    if len(dataset.sessions) > 0:
        flash('Cannot delete dataset that is part of active sessions', 'error')
        return redirect(url_for('datasets_web.list_datasets'))
        
    db.session.delete(dataset)
    db.session.commit()
    flash('Dataset deleted', 'success')
    return redirect(url_for('datasets_web.list_datasets'))
