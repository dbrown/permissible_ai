"""
Application factory and initialization
"""
from flask import Flask
from app.config import config
from app.extensions import db, login_manager, oauth


def create_app(config_name='default'):
    """
    Application factory pattern
    
    Args:
        config_name: Configuration to use (development, production, testing)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Register user loader
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes import auth, main, admin, api_keys, api, tee
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api_keys.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(tee.bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
