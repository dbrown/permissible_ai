"""
Admin routes - user management and admin request handling
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User, AdminRequest
from app.utils.decorators import admin_required

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/users')
@login_required
@admin_required
def users():
    """View all users"""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=all_users)


@bp.route('/requests')
@login_required
@admin_required
def requests():
    """View all admin requests"""
    pending = AdminRequest.get_pending()
    approved = AdminRequest.get_recent_approved()
    rejected = AdminRequest.get_recent_rejected()
    
    return render_template(
        'admin_requests.html',
        pending=pending,
        approved=approved,
        rejected=rejected
    )


@bp.route('/requests/create', methods=['POST'])
@login_required
def create_request():
    """Create an admin request"""
    if current_user.is_admin:
        flash('You are already an administrator.', 'info')
        return redirect(url_for('main.dashboard'))
    
    # Check for existing pending request
    if current_user.has_pending_admin_request():
        flash('You already have a pending admin request.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    # Create new request
    admin_request = AdminRequest(user_id=current_user.id)
    current_user.is_pending_admin = True
    
    db.session.add(admin_request)
    db.session.commit()
    
    flash('Admin request submitted successfully. An administrator will review your request.', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/requests/<int:request_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_request(request_id):
    """Approve an admin request"""
    admin_request = AdminRequest.query.get_or_404(request_id)
    
    if admin_request.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('admin.requests'))
    
    admin_request.approve(current_user)
    flash(f'Admin request approved for {admin_request.user.email}.', 'success')
    
    return redirect(url_for('admin.requests'))


@bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_request(request_id):
    """Reject an admin request"""
    admin_request = AdminRequest.query.get_or_404(request_id)
    
    if admin_request.status != 'pending':
        flash('This request has already been processed.', 'warning')
        return redirect(url_for('admin.requests'))
    
    admin_request.reject(current_user)
    flash(f'Admin request rejected for {admin_request.user.email}.', 'info')
    
    return redirect(url_for('admin.requests'))
