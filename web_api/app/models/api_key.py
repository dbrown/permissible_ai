"""
API Key model
"""
from datetime import datetime
import secrets
from app.extensions import db


class APIKey(db.Model):
    """API Key model for external API access"""
    __tablename__ = 'api_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_used = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    def __repr__(self):
        return f'<APIKey {self.name} - {self.key[:8]}...>'
    
    @staticmethod
    def generate_key():
        """Generate a secure random API key"""
        return secrets.token_urlsafe(48)
    
    def mark_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.utcnow()
        db.session.commit()
    
    def deactivate(self):
        """Deactivate the API key"""
        self.is_active = False
        db.session.commit()
    
    @classmethod
    def get_by_key(cls, key):
        """Get an active API key"""
        return cls.query.filter_by(key=key, is_active=True).first()
    
    @classmethod
    def get_user_by_api_key(cls, key):
        """Get user associated with an active API key"""
        api_key = cls.get_by_key(key)
        if api_key:
            api_key.mark_used()
            return api_key.user
        return None
