"""
Tests for API Key model
"""
import pytest
from app.models.api_key import APIKey
from app.models.user import User
from app.extensions import db


class TestAPIKeyModel:
    """Test suite for APIKey model"""
    
    def test_generate_key(self):
        """Test API key generation"""
        key = APIKey.generate_key()
        
        assert key is not None
        assert len(key) > 40  # URL-safe base64 of 48 bytes
        assert isinstance(key, str)
    
    def test_generate_unique_keys(self):
        """Test that generated keys are unique"""
        keys = [APIKey.generate_key() for _ in range(100)]
        
        # All keys should be unique
        assert len(keys) == len(set(keys))
    
    def test_create_api_key(self, app, regular_user):
        """Test creating an API key"""
        with app.app_context():
            user = User.query.get(regular_user['id'])
            
            key_value = APIKey.generate_key()
            api_key = APIKey(
                user_id=user.id,
                key=key_value,
                name='Test Key'
            )
            
            db.session.add(api_key)
            db.session.commit()
            
            # Verify the key was created
            assert api_key.id is not None
            assert api_key.key == key_value
            assert api_key.name == 'Test Key'
            assert api_key.user_id == user.id
            assert api_key.is_active is True
            assert api_key.last_used is None
            assert api_key.created_at is not None
    
    def test_api_key_user_relationship(self, app, regular_user):
        """Test relationship between APIKey and User"""
        with app.app_context():
            user = User.query.get(regular_user['id'])
            
            api_key = APIKey(
                user_id=user.id,
                key=APIKey.generate_key(),
                name='Test Key'
            )
            
            db.session.add(api_key)
            db.session.commit()
            
            # Test relationship from APIKey to User
            assert api_key.user.id == user.id
            assert api_key.user.email == regular_user['email']
            
            # Test relationship from User to APIKey
            user_keys = user.api_keys.all()
            assert len(user_keys) == 1
            assert user_keys[0].id == api_key.id
    
    def test_get_by_key(self, app, api_key_for_user):
        """Test retrieving an API key by its value"""
        with app.app_context():
            found_key = APIKey.get_by_key(api_key_for_user['key'])
            
            assert found_key is not None
            assert found_key.id == api_key_for_user['id']
            assert found_key.name == api_key_for_user['name']
    
    def test_get_by_key_inactive(self, app, api_key_for_user):
        """Test that inactive keys are not returned"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            api_key.is_active = False
            db.session.commit()
            
            found_key = APIKey.get_by_key(api_key_for_user['key'])
            assert found_key is None
    
    def test_get_by_key_nonexistent(self, app):
        """Test retrieving a non-existent key"""
        with app.app_context():
            found_key = APIKey.get_by_key('nonexistent-key')
            assert found_key is None
    
    def test_mark_used(self, app, api_key_for_user):
        """Test marking an API key as used"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            
            # Initially last_used should be None
            assert api_key.last_used is None
            
            # Mark as used
            api_key.mark_used()
            
            # Verify last_used was updated
            assert api_key.last_used is not None
    
    def test_deactivate(self, app, api_key_for_user):
        """Test deactivating an API key"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            
            # Initially should be active
            assert api_key.is_active is True
            
            # Deactivate
            api_key.deactivate()
            
            # Verify it's deactivated
            assert api_key.is_active is False
    
    def test_get_user_by_api_key(self, app, api_key_for_user, regular_user):
        """Test getting user by API key"""
        with app.app_context():
            user = APIKey.get_user_by_api_key(api_key_for_user['key'])
            
            assert user is not None
            assert user.id == regular_user['id']
            assert user.email == regular_user['email']
    
    def test_get_user_by_api_key_marks_used(self, app, api_key_for_user):
        """Test that getting user by API key marks it as used"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            assert api_key.last_used is None
            
            # Get user by API key
            APIKey.get_user_by_api_key(api_key_for_user['key'])
            
            # Verify last_used was updated
            db.session.refresh(api_key)
            assert api_key.last_used is not None
    
    def test_get_user_by_inactive_key(self, app, api_key_for_user):
        """Test that inactive keys don't return users"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            api_key.deactivate()
            
            user = APIKey.get_user_by_api_key(api_key_for_user['key'])
            assert user is None
    
    def test_cascade_delete(self, app, regular_user):
        """Test that API keys are deleted when user is deleted"""
        with app.app_context():
            user = User.query.get(regular_user['id'])
            
            # Create multiple API keys
            for i in range(3):
                api_key = APIKey(
                    user_id=user.id,
                    key=APIKey.generate_key(),
                    name=f'Test Key {i}'
                )
                db.session.add(api_key)
            
            db.session.commit()
            
            # Verify keys exist
            assert user.api_keys.count() == 3
            
            # Delete user
            db.session.delete(user)
            db.session.commit()
            
            # Verify all keys were deleted
            remaining_keys = APIKey.query.filter_by(user_id=regular_user['id']).count()
            assert remaining_keys == 0
    
    def test_repr(self, app, api_key_for_user):
        """Test string representation of APIKey"""
        with app.app_context():
            api_key = APIKey.query.get(api_key_for_user['id'])
            repr_str = repr(api_key)
            
            assert 'APIKey' in repr_str
            assert api_key.name in repr_str
            assert api_key.key[:8] in repr_str
