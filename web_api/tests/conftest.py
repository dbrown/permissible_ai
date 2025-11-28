"""
Pytest configuration and fixtures for testing
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User, APIKey, AdminRequest
from datetime import datetime


@pytest.fixture(scope='function')
def app():
    """Create and configure a test application instance"""
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the app"""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create a test CLI runner"""
    return app.test_cli_runner()


@pytest.fixture
def regular_user(app):
    """Create a regular (non-admin) user for testing"""
    with app.app_context():
        user = User(
            google_id='test_google_id_123',
            email='user@example.com',
            name='Test User',
            picture='https://example.com/pic.jpg',
            is_admin=False
        )
        db.session.add(user)
        db.session.commit()
        
        # Refresh to get the ID
        db.session.refresh(user)
        user_id = user.id
        
    # Return a dictionary with user data that can be used outside the context
    return {
        'id': user_id,
        'google_id': 'test_google_id_123',
        'email': 'user@example.com',
        'name': 'Test User',
        'is_admin': False
    }


@pytest.fixture
def admin_user(app):
    """Create an admin user for testing"""
    with app.app_context():
        user = User(
            google_id='admin_google_id_456',
            email='admin@example.com',
            name='Admin User',
            picture='https://example.com/admin.jpg',
            is_admin=True
        )
        db.session.add(user)
        db.session.commit()
        
        # Refresh to get the ID
        db.session.refresh(user)
        user_id = user.id
        
    return {
        'id': user_id,
        'google_id': 'admin_google_id_456',
        'email': 'admin@example.com',
        'name': 'Admin User',
        'is_admin': True
    }


@pytest.fixture
def api_key_for_user(app, regular_user):
    """Create an API key for the regular user"""
    with app.app_context():
        api_key = APIKey(
            user_id=regular_user['id'],
            key=APIKey.generate_key(),
            name='Test API Key'
        )
        db.session.add(api_key)
        db.session.commit()
        
        db.session.refresh(api_key)
        api_key_data = {
            'id': api_key.id,
            'key': api_key.key,
            'name': api_key.name,
            'user_id': api_key.user_id,
            'is_active': api_key.is_active
        }
        
    return api_key_data


@pytest.fixture
def authenticated_client(client, regular_user, app):
    """Create a client with an authenticated session"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(regular_user['id'])
    return client


@pytest.fixture
def admin_authenticated_client(client, admin_user, app):
    """Create a client with an authenticated admin session"""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_user['id'])
    return client
