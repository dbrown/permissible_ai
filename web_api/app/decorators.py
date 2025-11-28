"""
Utility decorators for the application
"""
from functools import wraps
from flask import flash, redirect, url_for, request, jsonify
from flask_login import current_user


def admin_required(f):
    """
    Decorator to require admin privileges for a route
    
    Usage:
        @app.route('/admin/dashboard')
        @login_required
        @admin_required
        def admin_dashboard():
            return render_template('admin_dashboard.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin:
            flash('Admin privileges required to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function


def api_key_required(f):
    """
    Decorator to require API key authentication for API routes
    
    Checks for API key in:
    1. Authorization header (Bearer token)
    2. X-API-Key header
    3. api_key query parameter
    
    Usage:
        @app.route('/api/endpoint')
        @api_key_required
        def api_endpoint():
            # current_user will be set to the user associated with the API key
            return jsonify({'data': 'something'})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app.models import APIKey
        from flask_login import login_user
        
        api_key = None
        
        # Check Authorization header (Bearer token)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            api_key = auth_header.replace('Bearer ', '')
        
        # Check X-API-Key header
        if not api_key:
            api_key = request.headers.get('X-API-Key')
        
        # Check query parameter
        if not api_key:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({
                'error': 'API key required',
                'message': 'Please provide an API key via Authorization header, X-API-Key header, or api_key query parameter'
            }), 401
        
        # Validate API key and get user
        user = APIKey.get_user_by_api_key(api_key)
        if not user:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid or has been deactivated'
            }), 401
        
        # Log in the user for this request
        login_user(user)
        
        return f(*args, **kwargs)
    return decorated_function
