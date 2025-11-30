"""
Authentication routes - handles OAuth login/logout
"""
from flask import Blueprint, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import oauth, db
from app.models.user import User

bp = Blueprint('auth', __name__, url_prefix='/auth')

# Configure Google OAuth
google = oauth.register(
    name='google',
    client_id=None,  # Will be set from app config
    client_secret=None,  # Will be set from app config
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


@bp.before_app_request
def configure_oauth():
    """Configure OAuth with app config values"""
    from flask import current_app
    if not google.client_id:
        google.client_id = current_app.config['GOOGLE_CLIENT_ID']
        google.client_secret = current_app.config['GOOGLE_CLIENT_SECRET']


@bp.route('/login')
def login():
    """Initiate Google OAuth login"""
    redirect_uri = url_for('auth.authorize', _external=True)
    return google.authorize_redirect(redirect_uri)


@bp.route('/authorize')
def authorize():
    """Handle Google OAuth callback"""
    try:
        token = google.authorize_access_token()
        user_info = token.get('userinfo')
        
        if not user_info:
            flash('Authentication failed. Please try again.', 'error')
            return redirect(url_for('main.index'))
        
        # Extract user information
        google_id = user_info['sub']
        email = user_info['email']
        name = user_info.get('name', '')
        picture = user_info.get('picture', '')
        
        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            # Check if this is the first user (becomes admin automatically)
            is_first_user = User.query.count() == 0
            
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                picture=picture,
                is_admin=is_first_user
            )
            db.session.add(user)
            db.session.commit()
            
            if is_first_user:
                flash('Welcome! You are the first user and have been granted administrator privileges.', 'success')
            else:
                flash(f'Welcome, {name}! Your account has been created.', 'success')
        else:
            # Update user information
            user.name = name
            user.picture = picture
            user.update_last_login()
            flash(f'Welcome back, {name}!', 'success')
        
        # Log the user in
        login_user(user, remember=True)
        
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        flash(f'Authentication failed: {str(e)}', 'error')
        return redirect(url_for('main.index'))


@bp.route('/logout')
@login_required
def logout():
    """Log out the current user"""
    from flask import current_app
    
    # Log for debugging
    current_app.logger.info(f'User {current_user.id} logging out')
    
    # Flash message BEFORE clearing session
    flash('You have been logged out successfully.', 'info')
    
    # Explicitly log out the user (this removes the user from the session)
    logout_user()
    
    # Clear all remaining session data
    session.clear()
    
    # Redirect to index with explicit no-cache headers
    response = redirect(url_for('main.index'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Clear remember me cookie if it exists
    response.set_cookie('remember_token', '', expires=0)
    response.set_cookie('session', '', expires=0)
    
    return response


@bp.route('/test-login/<email>')
def test_login(email):
    """
    Development-only route to log in as a test user without OAuth.
    
    Usage:
        /auth/test-login/alice@hospital-a.org
        /auth/test-login/bob@hospital-b.org
    
    Only works in development mode for security reasons.
    """
    from flask import current_app
    
    # Only allow in development mode
    if not current_app.config.get('DEBUG'):
        flash('Test login is only available in development mode.', 'error')
        return redirect(url_for('main.index'))
    
    # Find the user by email
    user = User.query.filter_by(email=email).first()
    
    if not user:
        flash(f'Test user {email} not found. Run scripts/setup_test_users.py to create test users.', 'error')
        return redirect(url_for('main.index'))
    
    # Log the user in
    login_user(user, remember=True)
    flash(f'Logged in as test user: {user.name} ({user.email})', 'success')
    
    return redirect(url_for('main.dashboard'))
