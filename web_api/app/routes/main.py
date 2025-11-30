"""
Main application routes - dashboard and public pages
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models.user import AdminRequest

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    from app.models.tee import CollaborationSession, Query, QueryStatus
    from sqlalchemy import or_
    
    pending_requests = []
    
    # If user is admin, show pending admin requests
    if current_user.is_admin:
        pending_requests = AdminRequest.get_pending()
    
    # Get user's collaboration sessions
    user_sessions = CollaborationSession.query.filter(
        or_(
            CollaborationSession.creator_id == current_user.id,
            CollaborationSession.participants.any(id=current_user.id)
        )
    ).order_by(CollaborationSession.created_at.desc()).limit(5).all()
    
    # Get queries awaiting approval from current user
    from app.models.tee import query_approvals
    from app.extensions import db
    
    pending_queries = []
    for session in user_sessions:
        for query in session.queries.filter(
            Query.status.in_([QueryStatus.SUBMITTED, QueryStatus.VERIFYING])
        ).all():
            # Check if user hasn't approved yet
            existing_approval = db.session.query(query_approvals).filter_by(
                query_id=query.id,
                user_id=current_user.id
            ).first()
            
            if not existing_approval:
                pending_queries.append(query)
    
    return render_template(
        'dashboard.html',
        user=current_user,
        pending_requests=pending_requests,
        user_sessions=user_sessions,
        pending_queries=pending_queries
    )
