"""
Main application routes - dashboard and public pages
"""
from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required
from app.models import AdminRequest

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
    pending_requests = []
    
    # If user is admin, show pending admin requests
    if current_user.is_admin:
        pending_requests = AdminRequest.get_pending()
    
    return render_template(
        'dashboard.html',
        user=current_user,
        pending_requests=pending_requests
    )
