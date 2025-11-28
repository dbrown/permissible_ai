"""
API Key management routes
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import APIKey
from app.extensions import db

bp = Blueprint('api_keys', __name__, url_prefix='/api-keys')


@bp.route('/')
@login_required
def list_keys():
    """List user's API keys"""
    api_keys = current_user.api_keys.filter_by(is_active=True).order_by(
        APIKey.created_at.desc()
    ).all()
    return render_template('api_keys.html', api_keys=api_keys)


@bp.route('/create', methods=['POST'])
@login_required
def create_key():
    """Create a new API key"""
    name = request.form.get('name', '').strip()
    
    if not name:
        flash('Please provide a name for your API key.', 'error')
        return redirect(url_for('api_keys.list_keys'))
    
    # Check if user already has 10 active keys (reasonable limit)
    active_keys_count = current_user.api_keys.filter_by(is_active=True).count()
    if active_keys_count >= 10:
        flash('You have reached the maximum number of active API keys (10).', 'error')
        return redirect(url_for('api_keys.list_keys'))
    
    # Generate new API key
    key = APIKey.generate_key()
    api_key = APIKey(
        user_id=current_user.id,
        key=key,
        name=name
    )
    
    db.session.add(api_key)
    db.session.commit()
    
    # Show the key once (it won't be shown again)
    flash(f'API Key created successfully! Save it now, you won\'t be able to see it again: {key}', 'success')
    return redirect(url_for('api_keys.list_keys'))


@bp.route('/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_key(key_id):
    """Delete (deactivate) an API key"""
    api_key = APIKey.query.get_or_404(key_id)
    
    # Verify ownership
    if api_key.user_id != current_user.id:
        flash('You do not have permission to delete this API key.', 'error')
        return redirect(url_for('api_keys.list_keys'))
    
    # Deactivate the key (soft delete)
    api_key.deactivate()
    
    flash(f'API key "{api_key.name}" has been deleted.', 'success')
    return redirect(url_for('api_keys.list_keys'))


@bp.route('/rename/<int:key_id>', methods=['POST'])
@login_required
def rename_key(key_id):
    """Rename an API key"""
    api_key = APIKey.query.get_or_404(key_id)
    
    # Verify ownership
    if api_key.user_id != current_user.id:
        flash('You do not have permission to rename this API key.', 'error')
        return redirect(url_for('api_keys.list_keys'))
    
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Please provide a name for your API key.', 'error')
        return redirect(url_for('api_keys.list_keys'))
    
    api_key.name = new_name
    db.session.commit()
    
    flash(f'API key renamed successfully to "{new_name}".', 'success')
    return redirect(url_for('api_keys.list_keys'))
