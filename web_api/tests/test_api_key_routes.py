"""
Tests for API Key routes (CRUD operations)
"""
import pytest
from app.models.api_key import APIKey
from app.models.user import User
from app.extensions import db
from flask import url_for


class TestAPIKeyRoutes:
    """Test suite for API Key management routes"""
    
    def test_list_keys_unauthenticated(self, client):
        """Test that unauthenticated users cannot access API keys page"""
        response = client.get('/api-keys/')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location or 'auth' in response.location
    
    def test_list_keys_empty(self, authenticated_client, app):
        """Test listing API keys when user has none"""
        response = authenticated_client.get('/api-keys/')
        
        assert response.status_code == 200
        assert b'No API keys yet' in response.data
    
    def test_list_keys_with_keys(self, authenticated_client, app, regular_user):
        """Test listing API keys when user has keys"""
        with app.app_context():
            # Create some API keys for the user
            for i in range(3):
                api_key = APIKey(
                    user_id=regular_user['id'],
                    key=APIKey.generate_key(),
                    name=f'Test Key {i}'
                )
                db.session.add(api_key)
            db.session.commit()
        
        response = authenticated_client.get('/api-keys/')
        
        assert response.status_code == 200
        assert b'Test Key 0' in response.data
        assert b'Test Key 1' in response.data
        assert b'Test Key 2' in response.data
    
    def test_create_key_unauthenticated(self, client):
        """Test that unauthenticated users cannot create API keys"""
        response = client.post('/api-keys/create', data={'name': 'Test Key'})
        
        # Should redirect to login
        assert response.status_code == 302
    
    def test_create_key_success(self, authenticated_client, app, regular_user):
        """Test successfully creating an API key"""
        response = authenticated_client.post(
            '/api-keys/create',
            data={'name': 'My Production Key'},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'API Key created successfully' in response.data
        
        # Verify key was created in database
        with app.app_context():
            user = User.query.get(regular_user['id'])
            keys = user.api_keys.filter_by(is_active=True).all()
            
            assert len(keys) == 1
            assert keys[0].name == 'My Production Key'
            assert len(keys[0].key) > 40
    
    def test_create_key_without_name(self, authenticated_client):
        """Test creating an API key without a name"""
        response = authenticated_client.post(
            '/api-keys/create',
            data={'name': ''},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Please provide a name' in response.data or b'provide a name' in response.data
    
    def test_create_key_whitespace_name(self, authenticated_client):
        """Test creating an API key with only whitespace in name"""
        response = authenticated_client.post(
            '/api-keys/create',
            data={'name': '   '},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Please provide a name' in response.data or b'provide a name' in response.data
    
    def test_create_key_max_limit(self, authenticated_client, app, regular_user):
        """Test that users cannot create more than 10 API keys"""
        with app.app_context():
            # Create 10 API keys
            for i in range(10):
                api_key = APIKey(
                    user_id=regular_user['id'],
                    key=APIKey.generate_key(),
                    name=f'Key {i}'
                )
                db.session.add(api_key)
            db.session.commit()
        
        # Try to create an 11th key
        response = authenticated_client.post(
            '/api-keys/create',
            data={'name': 'One Too Many'},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'maximum number of active API keys' in response.data or b'10' in response.data
    
    def test_create_key_shows_full_key_once(self, authenticated_client):
        """Test that the full API key is shown in the response"""
        response = authenticated_client.post(
            '/api-keys/create',
            data={'name': 'Test Key'},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        # Should contain a warning about saving the key
        assert b"won't be able to see it again" in response.data or b"Save it now" in response.data
    
    def test_delete_key_unauthenticated(self, client, api_key_for_user):
        """Test that unauthenticated users cannot delete API keys"""
        response = client.post(f'/api-keys/delete/{api_key_for_user["id"]}')
        
        # Should redirect to login
        assert response.status_code == 302
    
    def test_delete_key_success(self, authenticated_client, app, api_key_for_user):
        """Test successfully deleting an API key"""
        response = authenticated_client.post(
            f'/api-keys/delete/{api_key_for_user["id"]}',
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'deleted' in response.data
        
        # Verify key was deactivated
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            assert api_key.is_active is False
    
    def test_delete_key_wrong_user(self, app, regular_user, admin_user, client):
        """Test that users cannot delete other users' API keys"""
        # Create API key for admin user
        with app.app_context():
            api_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(api_key)
            db.session.commit()
            key_id = api_key.id
        
        # Login as regular user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user['id'])
        
        # Try to delete admin's key (without following redirects)
        response = client.post(f'/api-keys/delete/{key_id}')
        
        # Should redirect or show error
        assert response.status_code in [302, 403, 200]
        
        # Verify key was NOT deleted
        with app.app_context():
            api_key = APIKey.query.get(key_id)
            assert api_key.is_active is True
    
    def test_delete_nonexistent_key(self, authenticated_client):
        """Test deleting a non-existent API key"""
        response = authenticated_client.post('/api-keys/delete/99999')
        
        # Should return 404
        assert response.status_code == 404
    
    def test_rename_key_unauthenticated(self, client, api_key_for_user):
        """Test that unauthenticated users cannot rename API keys"""
        response = client.post(
            f'/api-keys/rename/{api_key_for_user["id"]}',
            data={'name': 'New Name'}
        )
        
        # Should redirect to login
        assert response.status_code == 302
    
    def test_rename_key_success(self, authenticated_client, app, api_key_for_user):
        """Test successfully renaming an API key"""
        response = authenticated_client.post(
            f'/api-keys/rename/{api_key_for_user["id"]}',
            data={'name': 'Renamed Key'},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'renamed successfully' in response.data
        assert b'Renamed Key' in response.data
        
        # Verify in database
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            assert api_key.name == 'Renamed Key'
    
    def test_rename_key_empty_name(self, authenticated_client, api_key_for_user):
        """Test renaming an API key with empty name"""
        response = authenticated_client.post(
            f'/api-keys/rename/{api_key_for_user["id"]}',
            data={'name': ''},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert b'Please provide a name' in response.data or b'provide a name' in response.data
    
    def test_rename_key_wrong_user(self, app, regular_user, admin_user, client):
        """Test that users cannot rename other users' API keys"""
        # Create API key for admin user
        with app.app_context():
            api_key = APIKey(
                user_id=admin_user['id'],
                key=APIKey.generate_key(),
                name='Admin Key'
            )
            db.session.add(api_key)
            db.session.commit()
            key_id = api_key.id
        
        # Login as regular user
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user['id'])
        
        # Try to rename admin's key (without following redirects)
        response = client.post(
            f'/api-keys/rename/{key_id}',
            data={'name': 'Hacked Name'}
        )
        
        # Should redirect or show error
        assert response.status_code in [302, 403, 200]
        
        # Verify key was NOT renamed
        with app.app_context():
            api_key = APIKey.query.get(key_id)
            assert api_key.name == 'Admin Key'
    
    def test_rename_nonexistent_key(self, authenticated_client):
        """Test renaming a non-existent API key"""
        response = authenticated_client.post(
            '/api-keys/rename/99999',
            data={'name': 'New Name'}
        )
        
        # Should return 404
        assert response.status_code == 404
    
    def test_only_active_keys_shown(self, authenticated_client, app, regular_user):
        """Test that only active keys are shown in the list"""
        with app.app_context():
            # Create active key
            active_key = APIKey(
                user_id=regular_user['id'],
                key=APIKey.generate_key(),
                name='Active Key'
            )
            db.session.add(active_key)
            
            # Create inactive key
            inactive_key = APIKey(
                user_id=regular_user['id'],
                key=APIKey.generate_key(),
                name='Inactive Key',
                is_active=False
            )
            db.session.add(inactive_key)
            db.session.commit()
        
        response = authenticated_client.get('/api-keys/')
        
        assert response.status_code == 200
        assert b'Active Key' in response.data
        assert b'Inactive Key' not in response.data
