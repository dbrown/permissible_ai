"""
API endpoints that require API key authentication
"""
from flask import Blueprint, jsonify
from flask_login import current_user
from app.utils.decorators import api_key_required
from app.models.user import User

bp = Blueprint('api', __name__, url_prefix='/api')


@bp.route('/me')
@api_key_required
def get_current_user():
    """Get information about the authenticated user"""
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'name': current_user.name,
        'is_admin': current_user.is_admin,
        'created_at': current_user.created_at.isoformat(),
        'last_login': current_user.last_login.isoformat()
    })


@bp.route('/health')
def health_check():
    """Public health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'message': 'Permissible API is running'
    })


@bp.route('/users')
@api_key_required
def list_users():
    """
    List all users (admin only)
    
    This is an example of an admin-only API endpoint
    """
    if not current_user.is_admin:
        return jsonify({
            'error': 'Forbidden',
            'message': 'Admin privileges required'
        }), 403
    
    users = User.query.all()
    return jsonify({
        'users': [{
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_admin': user.is_admin,
            'created_at': user.created_at.isoformat()
        } for user in users]
    })
