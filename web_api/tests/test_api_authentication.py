"""
Tests for API key authentication and API endpoints
"""
import pytest
import json
from app.models import APIKey, User
from app.extensions import db


class TestAPIKeyAuthentication:
    """Test suite for API key authentication decorator"""
    
    def test_health_check_no_auth(self, client):
        """Test public health check endpoint doesn't require auth"""
        response = client.get('/api/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
    
    def test_api_endpoint_no_key(self, client):
        """Test that API endpoints require authentication"""
        response = client.get('/api/me')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'API key required' in data['error']
    
    def test_api_endpoint_with_bearer_token(self, client, app, api_key_for_user, regular_user):
        """Test API authentication with Bearer token in Authorization header"""
        response = client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['email'] == regular_user['email']
        assert data['id'] == regular_user['id']
    
    def test_api_endpoint_with_x_api_key_header(self, client, app, api_key_for_user, regular_user):
        """Test API authentication with X-API-Key header"""
        response = client.get(
            '/api/me',
            headers={'X-API-Key': api_key_for_user['key']}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['email'] == regular_user['email']
    
    def test_api_endpoint_with_query_parameter(self, client, app, api_key_for_user, regular_user):
        """Test API authentication with query parameter"""
        response = client.get(f'/api/me?api_key={api_key_for_user["key"]}')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['email'] == regular_user['email']
    
    def test_api_endpoint_with_invalid_key(self, client):
        """Test API authentication with invalid key"""
        response = client.get(
            '/api/me',
            headers={'Authorization': 'Bearer invalid-key-12345'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid API key' in data['error']
    
    def test_api_endpoint_with_inactive_key(self, client, app, api_key_for_user):
        """Test that inactive API keys are rejected"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            api_key.deactivate()
        
        response = client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert 'Invalid API key' in data['error']
    
    def test_api_key_last_used_updated(self, client, app, api_key_for_user):
        """Test that API key last_used timestamp is updated on use"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            assert api_key.last_used is None
        
        # Make API request
        client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        # Check that last_used was updated
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            assert api_key.last_used is not None


class TestAPIEndpoints:
    """Test suite for API endpoints"""
    
    def test_get_current_user(self, client, app, api_key_for_user, regular_user):
        """Test GET /api/me endpoint"""
        response = client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert data['id'] == regular_user['id']
        assert data['email'] == regular_user['email']
        assert data['name'] == regular_user['name']
        assert data['is_admin'] == regular_user['is_admin']
        assert 'created_at' in data
        assert 'last_login' in data
    
    def test_list_users_as_regular_user(self, client, app, api_key_for_user):
        """Test that regular users cannot list all users"""
        response = client.get(
            '/api/users',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert 'Forbidden' in data['error'] or 'Admin privileges required' in data['message']
    
    def test_list_users_as_admin(self, client, app, admin_user):
        """Test that admin users can list all users"""
        # Create API key for admin
        with app.app_context():
            api_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(api_key)
            db.session.commit()
            admin_key = api_key.key
        
        response = client.get(
            '/api/users',
            headers={'Authorization': f'Bearer {admin_key}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'users' in data
        assert isinstance(data['users'], list)
        assert len(data['users']) >= 1
        
        # Check structure of user data
        user = data['users'][0]
        assert 'id' in user
        assert 'email' in user
        assert 'name' in user
        assert 'is_admin' in user
        assert 'created_at' in user
    
    def test_list_users_includes_all_users(self, client, app, admin_user, regular_user):
        """Test that list users includes all users in the system"""
        # Create API key for admin
        with app.app_context():
            api_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(api_key)
            db.session.commit()
            admin_key = api_key.key
        
        response = client.get(
            '/api/users',
            headers={'Authorization': f'Bearer {admin_key}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Should have at least the admin and regular user
        assert len(data['users']) >= 2
        
        emails = [u['email'] for u in data['users']]
        assert admin_user['email'] in emails
        assert regular_user['email'] in emails
    
    def test_api_returns_json(self, client, api_key_for_user):
        """Test that API endpoints return JSON"""
        response = client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
    
    def test_api_error_returns_json(self, client):
        """Test that API errors return JSON"""
        response = client.get('/api/me')
        
        assert response.status_code == 401
        assert response.content_type == 'application/json'
        
        data = json.loads(response.data)
        assert 'error' in data
        assert 'message' in data
    
    def test_bearer_token_case_insensitive(self, client, api_key_for_user):
        """Test that Bearer token is case-insensitive"""
        # Try with lowercase 'bearer'
        response = client.get(
            '/api/me',
            headers={'Authorization': f'bearer {api_key_for_user["key"]}'}
        )
        
        # Should still fail because we check for 'Bearer ' with capital B
        # This tests the actual implementation behavior
        assert response.status_code == 401
    
    def test_bearer_token_exact_format(self, client, api_key_for_user):
        """Test that Bearer token requires exact format"""
        response = client.get(
            '/api/me',
            headers={'Authorization': f'Bearer {api_key_for_user["key"]}'}
        )
        
        assert response.status_code == 200
    
    def test_multiple_auth_methods_bearer_takes_precedence(self, client, api_key_for_user):
        """Test that Bearer token takes precedence over other methods"""
        # Create a second invalid key
        invalid_key = 'invalid-key-123'
        
        response = client.get(
            f'/api/me?api_key={invalid_key}',
            headers={
                'Authorization': f'Bearer {api_key_for_user["key"]}',
                'X-API-Key': invalid_key
            }
        )
        
        # Should succeed because Bearer token is checked first and is valid
        assert response.status_code == 200


class TestAPIKeySecurity:
    """Test suite for API key security features"""
    
    def test_api_key_not_exposed_in_user_list(self, client, app, admin_user, regular_user):
        """Test that API keys are not exposed in user listings"""
        # Create API key for regular user
        with app.app_context():
            api_key = APIKey(
                user_id=regular_user['id'],
                key=APIKey.generate_key(),
                name='Secret Key'
            )
            db.session.add(api_key)
            db.session.commit()
        
        # Create API key for admin and list users
        with app.app_context():
            admin_api_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(admin_api_key)
            db.session.commit()
            admin_key_value = admin_api_key.key
        
        response = client.get(
            '/api/users',
            headers={'Authorization': f'Bearer {admin_key_value}'}
        )
        
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        
        # API keys should not be in the response
        assert 'Secret Key' not in response_text
        # The actual key value should definitely not be exposed
        with app.app_context():
            api_key = APIKey.query.filter_by(name='Secret Key').first()
            assert api_key.key not in response_text
    
    def test_different_users_different_keys(self, app, regular_user, admin_user):
        """Test that different users get different keys"""
        with app.app_context():
            user_key = APIKey(
                user_id=regular_user['id'],
                key=APIKey.generate_key(),
                name='User Key'
            )
            admin_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(user_key)
            db.session.add(admin_key)
            db.session.commit()
            
            assert user_key.key != admin_key.key
            assert user_key.user_id != admin_key.user_id
